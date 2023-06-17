import csv
import os
import tempfile

from costemailer import costquerier
from costemailer import CURRENCY_SYMBOLS_MAP
from costemailer import DEFAULT_ORDER
from costemailer import DEFAULT_REPORT_ISO_DAYS
from costemailer import DEFAULT_REPORT_TYPE
from costemailer import get_email_content
from costemailer import PRODUCTION_ENDPOINT
from costemailer.charting import plot_data
from costemailer.email import email
from costemailer.email import email_subject
from costemailer.reporting import get_daily_cost
from costemailer.reporting import get_monthly_cost
from jinja2 import Template


def email_report(email_item, images, img_paths, **kwargs):  # noqa: C901
    report_type = email_item.get("report_type", DEFAULT_REPORT_TYPE)
    report_schedule = email_item.get("schedule", DEFAULT_REPORT_ISO_DAYS)
    report_filter = email_item.get("filter", {})
    report_title_suffix = email_item.get("title_suffix")
    filtered_subscriptions = report_filter.get("subscriptions", [])
    print(f"User info: {email_item}.")
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    azure_subscriptions = email_item.get("azure.subscriptions", [])
    cost_order = email_item.get("order", DEFAULT_ORDER)

    if filtered_subscriptions:
        if azure_subscriptions:
            azure_subscriptions = list(set(azure_subscriptions).intersection(filtered_subscriptions))
        else:
            azure_subscriptions = filtered_subscriptions

    daily_costs = {}
    monthly_costs = {}
    if not is_org_admin and not (len(azure_subscriptions)):
        return

    monthly_params = {"group_by[subscription_guid]": "*"}
    daily_params = {}
    if len(azure_subscriptions):
        daily_params["filter[subscription_guid]"] = ",".join(azure_subscriptions)
        monthly_params["filter[subscription_guid]"] = ",".join(azure_subscriptions)

    daily_costs = get_daily_cost(report_type=report_type, params=daily_params, is_org_admin=is_org_admin)
    monthly_costs = get_monthly_cost(report_type=report_type, params=monthly_params, is_org_admin=is_org_admin)
    meta = daily_costs.get("meta", {})
    daily_data = daily_costs.get("data", [])

    values_present = False
    for day_data in daily_data:
        if day_data.get("values"):
            values_present = True

    if not daily_data or not values_present:
        print("Empty daily data values ... skipping report.")
        return

    img_file, img_path = plot_data(daily_data)
    images.append(img_file)
    img_paths.append(img_path)

    if len(daily_data) > 0:
        daily = daily_data[0]
        date = daily["date"]
        total = meta["total"]["cost"]["total"]
        formatted_total = "{:.2f}".format(total["value"])
        formatted_delta = "{:.2f}".format(meta["delta"]["value"])
        current_month = date[:-3]
        print(
            f"Azure costs for {current_month} are {formatted_total}"
            f' {total["units"]} with a delta of'
            f' {formatted_delta} {total["units"]}'
        )

        monthly_data = monthly_costs.get("data", [{}])
        subscription_data = monthly_data[0].get("subscription_guids", [])

        subscription_breakdown = []
        for sub_data in subscription_data:
            sub_datum = sub_data.get("values", [{}])[0]
            if filtered_subscriptions:
                for fc in filtered_subscriptions:
                    if fc in sub_datum.get("subscription_guid", []):
                        subscription_breakdown.append(sub_datum)
                    break
            else:
                subscription_breakdown.append(sub_datum)
        if cost_order == "delta":
            subscription_breakdown = sorted(subscription_breakdown, key=lambda i: i["delta_value"], reverse=True)
        else:
            subscription_breakdown = sorted(
                subscription_breakdown, key=lambda i: i["cost"]["total"]["value"], reverse=True
            )

    email_template = Template(get_email_content(report_type))
    template_variables = {
        "cost_timeframe": current_month,
        "azure_cost": float(formatted_total),
        "azure_cost_delta": float(formatted_delta),
        "azure_subscription_breakdown": subscription_breakdown,
        "web_url": PRODUCTION_ENDPOINT,
        "units": CURRENCY_SYMBOLS_MAP.get(total["units"]),
        "azure_img_index": 1,
    }
    for img_path in img_paths:
        file_name = img_path.split("/")[-1]
        template_variables[file_name] = file_name
    email_msg = email_template.render(**template_variables)
    subject = email_subject(report_type)
    if report_title_suffix:
        subject += f" [{report_title_suffix}]"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with open(tmp.name, "w", newline="") as csvfile:
        fieldnames = ["subscription_id", "cost", "delta"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for sub in subscription_breakdown:
            writer.writerow(
                {
                    "subscription_id": sub.get("subscription_guid"),
                    "cost": sub.get("cost", {}).get("total", {}).get("value"),
                    "delta": sub.get("delta_value"),
                }
            )
    images.append(tmp)
    img_paths.append(tmp.name)

    email(
        recipients=email_addrs,
        subject=subject,
        content=email_msg,
        attachments=img_paths,
        email_iso_days=report_schedule,
    )

    for img in images:
        if os.path.exists(img.name):
            os.unlink(img.name)
            img.close()
