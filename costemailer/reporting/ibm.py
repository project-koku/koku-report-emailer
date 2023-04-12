import csv
import os
import tempfile
from datetime import date

import requests
from costemailer import CURRENCY_SYMBOLS_MAP
from costemailer import DEFAULT_ORDER
from costemailer import DEFAULT_REPORT_ISO_DAYS
from costemailer import DEFAULT_REPORT_TYPE
from costemailer import get_email_content
from costemailer import PRODUCTION_ENDPOINT
from costemailer.charting import plot_data
from costemailer.email import email
from costemailer.email import email_subject
from jinja2 import Template

from ..config import Config


def get_current_month():
    return f"{date.today().year}-{date.today().month:02}"


def get_bearer_token():
    """Obtain the bearer token."""
    api_call = "https://iam.cloud.ibm.com/identity/token"
    form_data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": Config.IBM_CLOUD_API_KEY}
    access_token = None
    response = requests.post(url=api_call, data=form_data)
    if (
        response.status_code >= 200
        and response.status_code < 300
        and "application/json" in response.headers["content-type"]
    ):
        access_token = response.json().get("access_token")
    else:
        print(response.text)

    return access_token


def get_data(api_call, field, default=[]):
    token = get_bearer_token()
    data = []
    if token:
        response = requests.get(url=api_call, headers={"Authorization": f"Bearer {token}"})
        print(f"url={api_call}, response.status_code={response.status_code}")
        if (
            response.status_code >= 200
            and response.status_code < 300
            and "application/json" in response.headers["content-type"]
        ):
            data = response.json().get(field, default)
        else:
            print(response.text)

    return data


def get_account_groups():
    return get_data(api_call="https://enterprise.cloud.ibm.com/v1/account-groups", field="resources")


def get_accounts():
    return get_data(api_call="https://enterprise.cloud.ibm.com/v1/accounts", field="resources")


def get_account_costs(account_id):
    current_month = get_current_month()
    return get_data(
        api_call=f"https://enterprise.cloud.ibm.com/v1/resource-usage-reports?account_id={account_id}&month={current_month}",
        field="reports",
    )


def email_report(email_item, images, img_paths, **kwargs):  # noqa: C901
    report_type = email_item.get("report_type", DEFAULT_REPORT_TYPE)
    report_schedule = email_item.get("schedule", DEFAULT_REPORT_ISO_DAYS)
    report_filter = email_item.get("filter", {})
    filtered_accounts = report_filter.get("accounts", [])
    print(f"User info: {email_item}.")
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])

    account_groups = get_account_groups()
    account_groups_dict = {}
    for ag in account_groups:
        account_groups_dict[ag.get("crn")] = ag

    accts_in_ag = {}
    accounts = get_accounts()
    for acct in accounts:
        account_group_crn = acct.get("parent")
        account_group_dict = account_groups_dict.get(account_group_crn, {})
        account_group_name = account_group_dict.get("name")
        include_account = not filtered_accounts or (filtered_accounts and acct.get("id") in filtered_accounts)
        if (
            include_account
            and acct.get("state") == "ACTIVE"
            and account_group_name
            and "Suspended" not in account_group_name
        ):
            if not accts_in_ag.get(account_group_name):
                accts_in_ag[account_group_name] = []
            acct_costs_reports = get_account_costs(acct.get("id"))
            acct_costs = {}
            if acct_costs_reports:
                acct_costs = acct_costs_reports[0]
            acct_dict = {
                "id": acct.get("id"),
                "name": acct.get("name"),
                "cost": float(acct_costs.get("billable_rated_cost", 0)),
                "currency": acct_costs.get("currency_code", "USD"),
            }
            accts_in_ag[account_group_name].append(acct_dict)

    grand_total = 0
    report_currency = "USD"
    acct_grp_breakdown = {}
    for acct_grp, accts in accts_in_ag.items():
        total = 0
        currency = "USD"
        for acct in accts:
            total = float(total + acct.get("cost", 0))
            grand_total = float(grand_total + acct.get("cost", 0))
            currency = acct.get("currency", "USD")
            report_currency = acct.get("currency", "USD")

        acct_grp_breakdown[acct_grp] = {"name": acct_grp, "cost": total, "currency": currency}

    email_template = Template(get_email_content(report_type))
    template_variables = {
        "cost_timeframe": get_current_month(),
        "ibmcloud_cost": float(grand_total),
        "ibmcloud_group_breakdown": acct_grp_breakdown,
        "ibmcloud_account_breakdown": accts_in_ag,
        "web_url": PRODUCTION_ENDPOINT,
        "units": CURRENCY_SYMBOLS_MAP.get(report_currency),
    }
    for img_path in img_paths:
        file_name = img_path.split("/")[-1]
        template_variables[file_name] = file_name
    email_msg = email_template.render(**template_variables)
    subject = email_subject(report_type)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with open(tmp.name, "w", newline="") as csvfile:
        fieldnames = ["id", "name", "group", "cost", "currency"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for acct_grp, accts in accts_in_ag.items():
            for acct in accts:
                writer.writerow(
                    {
                        "id": acct.get("id"),
                        "name": acct.get("name"),
                        "group": acct_grp,
                        "cost": acct.get("cost"),
                        "currency": acct.get("currency"),
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
