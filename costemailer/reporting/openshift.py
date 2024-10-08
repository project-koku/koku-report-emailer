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
from costemailer.reporting import get_recommendations
from jinja2 import Template


def get_resource_dict(resource_def):
    if not resource_def:
        return {}
    res_dict = {}
    res_def_items = ["limits", "requests"]
    res_types = ["cpu", "memory"]
    for def_item in res_def_items:
        res_dict[def_item] = {}
        res_info = resource_def.get(def_item)
        for res_type in res_types:
            res_detail = res_info.get(res_type)
            value = res_detail.get("amount")
            format = res_detail.get("format")
            if format:
                if format == "bytes":
                    convert_bytes_to_mib = value / (1024 * 1024)
                    value = f"{convert_bytes_to_mib} MiB"
                else:
                    value = f"{value} {format}"
            res_dict[def_item][res_type] = value
    return res_dict


def send_recommendations_report(email_item, images, img_paths, recommendations):
    report_type = email_item.get("report_type", DEFAULT_REPORT_TYPE)
    report_schedule = email_item.get("schedule", DEFAULT_REPORT_ISO_DAYS)
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
    report_title_suffix = email_item.get("title_suffix")

    rec_data = recommendations.get("data", [])
    if not rec_data:
        return
    rec_items = []
    for rec_datum in rec_data:
        cost_recommendation_window = 7
        perf_recommendation_window = 7
        cost_recommendation = get_resource_dict(
            rec_datum.get("recommendations", {})
            .get("recommendation_terms", {})
            .get("medium_term", {})
            .get("recommendation_engines", {})
            .get("cost", {})
            .get("config", {})
        )
        perf_recommendation = get_resource_dict(
            rec_datum.get("recommendations", {})
            .get("recommendation_terms", {})
            .get("medium_term", {})
            .get("recommendation_engines", {})
            .get("performance", {})
            .get("config", {})
        )
        if cost_recommendation == {}:
            cost_recommendation = get_resource_dict(
                rec_datum.get("recommendations", {})
                .get("recommendation_terms", {})
                .get("short_term", {})
                .get("recommendation_engines", {})
                .get("cost", {})
                .get("config", {})
            )
            cost_recommendation_window = 1
        if perf_recommendation == {}:
            perf_recommendation = get_resource_dict(
                rec_datum.get("recommendations", {})
                .get("recommendation_terms", {})
                .get("short_term", {})
                .get("recommendation_engines", {})
                .get("performance", {})
                .get("config", {})
            )
            perf_recommendation_window = 1

        rec_item = {
            "container": rec_datum.get("container"),
            "project": rec_datum.get("project"),
            "cluster_alias": rec_datum.get("cluster_alias"),
            "cluster_uuid": rec_datum.get("cluster_uuid"),
            "last_reported": rec_datum.get("last_reported"),
            "current": get_resource_dict(rec_datum.get("recommendations", {}).get("current")),
            "cost_recommendation": cost_recommendation,
            "cost_recommendation_window": cost_recommendation_window,
            "perf_recommendation": perf_recommendation,
            "perf_recommendation_window": perf_recommendation_window,
        }
        if rec_item.get("cost_recommendation") and rec_item.get("perf_recommendation"):
            rec_items.append(rec_item)
    if not rec_items:
        return

    email_template = Template(get_email_content(report_type, report_feature="recommendation"))
    template_variables = {
        "recommendation_items": rec_items,
        "web_url": PRODUCTION_ENDPOINT,
    }
    for img_path in img_paths:
        file_name = img_path.split("/")[-1]
        template_variables[file_name] = file_name
    email_msg = email_template.render(**template_variables)
    subject = email_subject(report_type, report_feature=" - Recommendations")
    if report_title_suffix:
        subject += f" [{report_title_suffix}]"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with open(tmp.name, "w", newline="") as csvfile:
        fieldnames = [
            "container",
            "project",
            "cluster_alias",
            "cluster_uuid",
            "last_reported",
            "current_limits_cpu",
            "current_limits_memory",
            "current_requests_cpu",
            "current_requests_memory",
            "cost_recommendation_limits_cpu",
            "cost_recommendation_limits_memory",
            "cost_recommendation_requests_cpu",
            "cost_recommendation_requests_memory",
            "cost_recommendation_window",
            "perf_recommendation_limits_cpu",
            "perf_recommendation_limits_memory",
            "perf_recommendation_requests_cpu",
            "perf_recommendation_requests_memory",
            "perf_recommendation_window",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for recommendation in rec_items:
            writer.writerow(
                {
                    "container": recommendation.get("container"),
                    "project": recommendation.get("project"),
                    "cluster_alias": recommendation.get("cluster_alias"),
                    "cluster_uuid": recommendation.get("cluster_uuid"),
                    "last_reported": recommendation.get("last_reported"),
                    "current_limits_cpu": recommendation.get("current").get("limits").get("cpu"),
                    "current_limits_memory": recommendation.get("current").get("limits").get("memory"),
                    "current_requests_cpu": recommendation.get("current").get("requests").get("cpu"),
                    "current_requests_memory": recommendation.get("current").get("requests").get("memory"),
                    "cost_recommendation_limits_cpu": recommendation.get("cost_recommendation")
                    .get("limits")
                    .get("cpu"),
                    "cost_recommendation_limits_memory": recommendation.get("cost_recommendation")
                    .get("limits")
                    .get("memory"),
                    "cost_recommendation_requests_cpu": recommendation.get("cost_recommendation")
                    .get("requests")
                    .get("cpu"),
                    "cost_recommendation_requests_memory": recommendation.get("cost_recommendation")
                    .get("requests")
                    .get("memory"),
                    "cost_recommendation_window": recommendation.get("cost_recommendation_window"),
                    "perf_recommendation_limits_cpu": recommendation.get("perf_recommendation")
                    .get("limits")
                    .get("cpu"),
                    "perf_recommendation_limits_memory": recommendation.get("perf_recommendation")
                    .get("limits")
                    .get("memory"),
                    "perf_recommendation_requests_cpu": recommendation.get("perf_recommendation")
                    .get("requests")
                    .get("cpu"),
                    "perf_recommendation_requests_memory": recommendation.get("perf_recommendation")
                    .get("requests")
                    .get("memory"),
                    "perf_recommendation_window": recommendation.get("perf_recommendation_window"),
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


def send_cost_report(  # noqa C901
    email_item,
    images,
    img_paths,
    daily_costs,
    monthly_costs,
    openshift_projects,
    filtered_clusters,
    filtered_projects,
    filtered_accounts,
):
    report_type = email_item.get("report_type", DEFAULT_REPORT_TYPE)
    report_schedule = email_item.get("schedule", DEFAULT_REPORT_ISO_DAYS)
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
    report_title_suffix = email_item.get("title_suffix")
    cost_order = email_item.get("order", DEFAULT_ORDER)

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
            else:
                project_breakdown.append(proj_datum)
        if cost_order == "delta":
            project_breakdown = sorted(project_breakdown, key=lambda i: i["delta_value"], reverse=True)
        else:
            project_breakdown = sorted(project_breakdown, key=lambda i: i["cost"]["total"]["value"], reverse=True)

        openshift_project_aws_service_cost = {}
        if openshift_projects:
            for project in openshift_projects:
                aws_services_monthly_params = {
                    "group_by[service]": "*",
                    "filter[account]": filtered_accounts,
                    "filter[tag:namespace]": project,
                }

                aws_services_monthly_costs = get_monthly_cost(
                    report_type="AWS", params=aws_services_monthly_params, is_org_admin=is_org_admin
                )
                aws_monthly_data = aws_services_monthly_costs.get("data", [])
                if aws_monthly_data:
                    aws_cur_month_services = aws_monthly_data[0].get("services", [])
                    for aws_service in aws_cur_month_services:
                        service_name = aws_service.get("service")
                        service_values = aws_service.get("values", [])
                        if service_values:
                            service_delta = service_values[0].get("delta_value")
                            service_cost = service_values[0].get("cost", {}).get("total", {}).get("value", 0)
                            service_dict = {"name": service_name, "cost": service_cost, "delta": service_delta}
                            if not openshift_project_aws_service_cost.get(project):
                                openshift_project_aws_service_cost[project] = []
                            openshift_project_aws_service_cost.get(project).append(service_dict)

    email_template = Template(get_email_content(report_type))
    template_variables = {
        "cost_timeframe": current_month,
        "openshift_cost": float(formatted_total),
        "openshift_cost_delta": float(formatted_delta),
        "openshift_project_breakdown": project_breakdown,
        "openshift_project_aws_breakdown": openshift_project_aws_service_cost,
        "web_url": PRODUCTION_ENDPOINT,
        "units": CURRENCY_SYMBOLS_MAP.get(total["units"]),
        "openshift_img_index": 1,
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
        fieldnames = ["project", "cost", "delta"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for project in project_breakdown:
            writer.writerow(
                {
                    "project": project.get("project"),
                    "cost": project.get("cost", {}).get("total", {}).get("value"),
                    "delta": project.get("delta_value"),
                }
            )
    images.append(tmp)
    img_paths.append(tmp.name)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with open(tmp.name, "w", newline="") as csvfile:
        fieldnames = ["project", "aws_service", "cost", "delta"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for project, services in openshift_project_aws_service_cost.items():
            for service in services:
                writer.writerow(
                    {
                        "project": project,
                        "aws_service": service.get("name"),
                        "cost": service.get("cost"),
                        "delta": service.get("delta"),
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


def email_report(email_item, images, img_paths, **kwargs):  # noqa: C901
    report_type = email_item.get("report_type", DEFAULT_REPORT_TYPE)
    report_filter = email_item.get("filter", {})
    filtered_clusters = report_filter.get("clusters", [])
    filtered_projects = report_filter.get("projects", [])
    filtered_accounts = report_filter.get("accounts", [])
    print(f"User info: {email_item}.")
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    openshift_clusters = email_item.get("openshift.cluster", [])
    openshift_projects = email_item.get("openshift.project", [])

    if filtered_clusters:
        if openshift_clusters:
            openshift_clusters = list(set(openshift_clusters).intersection(filtered_clusters))
        else:
            openshift_clusters = filtered_clusters
    if filtered_projects:
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
    recommendation_params = {}
    if len(openshift_clusters) or len(openshift_projects):
        if len(openshift_clusters):
            daily_params["filter[cluster]"] = ",".join(openshift_clusters)
            monthly_params["filter[cluster]"] = ",".join(openshift_clusters)
            recommendation_params["cluster"] = openshift_clusters
        if len(openshift_projects):
            daily_params["filter[project]"] = ",".join(openshift_projects)
            monthly_params["filter[project]"] = ",".join(openshift_projects)
            recommendation_params["project"] = openshift_projects

    daily_costs = get_daily_cost(report_type=report_type, params=daily_params, is_org_admin=is_org_admin)
    monthly_costs = get_monthly_cost(report_type=report_type, params=monthly_params, is_org_admin=is_org_admin)
    recommendations = get_recommendations(
        report_type=report_type, params=recommendation_params, is_org_admin=is_org_admin
    )
    send_cost_report(
        email_item,
        images,
        img_paths,
        daily_costs,
        monthly_costs,
        openshift_projects,
        filtered_clusters,
        filtered_projects,
        filtered_accounts,
    )
    send_recommendations_report(email_item, images, img_paths, recommendations)
