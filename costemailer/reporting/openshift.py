import os

from costemailer import costquerier
from costemailer import CURRENCY_SYMBOLS_MAP
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
    filtered_clusters = report_filter.get("clusters", [])
    filtered_projects = report_filter.get("projects", [])
    print(f"User info: {email_item}.")
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    openshift_clusters = email_item.get("openshift.cluster", [])
    openshift_projects = email_item.get("openshift.project", [])

    if openshift_clusters:
        openshift_clusters = list(set(openshift_clusters).intersection(filtered_clusters))
    if openshift_projects:
        openshift_projects = list(set(openshift_projects).intersection(filtered_projects))
    else:
        openshift_projects = filtered_projects

    daily_costs = {}
    monthly_costs = {}
    if not is_org_admin and not (len(openshift_clusters) or len(openshift_projects)):
        return

    monthly_params = {"group_by[project]": "*"}
    daily_params = {}
    if len(openshift_clusters) or len(openshift_projects):
        if len(openshift_clusters):
            daily_params["filter[cluster]"] = ",".join(openshift_clusters)
            monthly_params["filter[cluster]"] = ",".join(openshift_clusters)
        if len(openshift_projects):
            daily_params["filter[project]"] = ",".join(openshift_projects)
            monthly_params["filter[project]"] = ",".join(openshift_projects)

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
            f"OpenShift costs for {current_month} are {formatted_total}"
            f' {total["units"]} with a delta of'
            f' {formatted_delta} {total["units"]}'
        )

        monthly_data = monthly_costs.get("data", [{}])
        project_data = monthly_data[0].get("projects", [])

        project_breakdown = []
        for proj_data in project_data:
            proj_datum = proj_data.get("values", [{}])[0]
            if filtered_projects:
                if proj_datum.get("project") in filtered_projects:
                    project_breakdown.append(proj_datum)
            elif filtered_clusters:
                for fc in filtered_clusters:
                    if fc in proj_datum.get("clusters", []):
                        project_breakdown.append(proj_datum)
                    break

        project_breakdown = sorted(project_breakdown, key=lambda i: i["delta_value"], reverse=True)

    email_template = Template(get_email_content(report_type))
    template_variables = {
        "cost_timeframe": current_month,
        "openshift_cost": float(formatted_total),
        "openshift_cost_delta": float(formatted_delta),
        "openshift_project_breakdown": project_breakdown,
        "web_url": PRODUCTION_ENDPOINT,
        "units": CURRENCY_SYMBOLS_MAP.get(total["units"]),
        "openshift_img_index": 1,
    }
    for img_path in img_paths:
        file_name = img_path.split("/")[-1]
        template_variables[file_name] = file_name
    email_msg = email_template.render(**template_variables)
    subject = email_subject(report_type)
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
