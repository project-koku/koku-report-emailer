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
    filtered_accounts = report_filter.get("gcp_accounts", [])
    print(f"User info: {email_item}.")
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    gcp_accounts = email_item.get("gcp.account", [])
    cost_order = email_item.get("order", DEFAULT_ORDER)

    if filtered_accounts:
        if gcp_accounts:
            gcp_accounts = list(set(gcp_accounts).intersection(filtered_accounts))
        else:
            gcp_accounts = filtered_accounts

    daily_costs = {}
    monthly_costs = {}
    if not is_org_admin and not (len(gcp_accounts)):
        return

    monthly_params = {"group_by[gcp_project]": "*"}
    daily_params = {}
    if len(gcp_accounts):
        daily_params["filter[account]"] = ",".join(gcp_accounts)
        monthly_params["filter[account]"] = ",".join(gcp_accounts)

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
            f"GCP costs for {current_month} are {formatted_total}"
            f' {total["units"]} with a delta of'
            f' {formatted_delta} {total["units"]}'
        )

        monthly_data = monthly_costs.get("data", [{}])
        project_data = monthly_data[0].get("gcp_projects", [])

        project_breakdown = []
        for proj_data in project_data:
            proj_datum = proj_data.get("values", [{}])[0]
            if filtered_accounts:
                for fc in filtered_accounts:
                    if fc in proj_datum.get("gcp_project", []):
                        project_breakdown.append(proj_datum)
                    break
            else:
                project_breakdown.append(proj_datum)
        if cost_order == "delta":
            project_breakdown = sorted(project_breakdown, key=lambda i: i["delta_value"], reverse=True)
        else:
            project_breakdown = sorted(project_breakdown, key=lambda i: i["cost"]["total"]["value"], reverse=True)

    email_template = Template(get_email_content(report_type))
    template_variables = {
        "cost_timeframe": current_month,
        "gcp_cost": float(formatted_total),
        "gcp_cost_delta": float(formatted_delta),
        "gcp_project_breakdown": project_breakdown,
        "web_url": PRODUCTION_ENDPOINT,
        "units": CURRENCY_SYMBOLS_MAP.get(total["units"]),
        "gcp_img_index": 1,
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
        fieldnames = ["project", "project_id", "cost", "delta"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for proj in project_breakdown:
            writer.writerow(
                {
                    "project": proj.get("gcp_project_alias"),
                    "project_id": proj.get("gcp_project"),
                    "cost": proj.get("cost", {}).get("total", {}).get("value"),
                    "delta": proj.get("delta_value"),
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
