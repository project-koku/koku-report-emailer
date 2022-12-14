import os
import smtplib
from datetime import datetime
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from costemailer import costquerier
from costemailer import CURRENCY_SYMBOLS_MAP
from costemailer.charting import plot_data
from costemailer.config import Config
from costemailer.rbac import AWS_ACCOUNT_ACCESS
from costemailer.rbac import AWS_ORG_ACCESS
from costemailer.rbac import get_access
from costemailer.rbac import get_users
from jinja2 import Template


PRODUCTION_ENDPOINT = "https://console.redhat.com"
REL_TEMPLATE_PATH = "costemailer/resources/CostEmailTemplate.html"
REL_LOGO_PATH = "costemailer/resources/Logo-Red_Hat-cost-management-RGB.png"
LOGO_PATH = Path(__file__).parent / REL_LOGO_PATH
EMAIL_TEMPLATE_PATH = Path(__file__).parent / REL_TEMPLATE_PATH
EMAIL_TEMPLATE_CONTENT = None
with open(EMAIL_TEMPLATE_PATH) as email_template:
    EMAIL_TEMPLATE_CONTENT = email_template.read()


def email(recipients, content=EMAIL_TEMPLATE_CONTENT, attachments=None):
    if not recipients:
        return
    gmail_user = Config.EMAIL_USER
    gmail_password = Config.EMAIL_PASSWORD
    s = smtplib.SMTP("smtp.gmail.com:587")
    s.starttls()
    s.login(gmail_user, gmail_password)

    today = datetime.today().strftime("%Y-%m-%d")

    msg = MIMEMultipart()
    sender = "cost-mgmt@redhat.com"
    subject = f"AWS Cost Management Report: {today}"
    msg_text = content
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ",".join(recipients)
    if attachments is not None:
        attach_count = 0
        for each_file_path in attachments:
            try:
                file_name = each_file_path.split("/")[-1]
                msgImage = MIMEImage(open(each_file_path, "rb").read(), filename=file_name)
                msgImage.add_header("Content-ID", f"<image{attach_count}>")
                msg.attach(msgImage)
                attach_count += 1
            except Exception as err:  # noqa: E722
                print(f"Could not attach file: {err}")
    msg.attach(MIMEText(msg_text, "html"))
    s.sendmail(sender, recipients, msg.as_string())


def get_org_level(parent_org, aws_orgs_access, all_aws_orgs):
    org_level = 0
    if not parent_org or parent_org in aws_orgs_access:
        return org_level
    parent_org_dict = all_aws_orgs.get(parent_org, {})
    next_parent = parent_org_dict.get("parent_org")
    if next_parent:
        org_level = 1 + get_org_level(next_parent, aws_orgs_access, all_aws_orgs)
    return org_level


def construct_parent_org(parent_org, aws_orgs_access, all_aws_orgs, org_values):
    parent_org_dict = all_aws_orgs.get(parent_org, {})
    if not parent_org_dict:
        return None

    next_parent = parent_org_dict.get("parent_org")
    level = 0
    if parent_org in aws_orgs_access:
        next_parent = None
    else:
        level = 1 + get_org_level(next_parent, aws_orgs_access, all_aws_orgs)

    parent_org_cost_dict = {
        "org_unit_id": parent_org,
        "org_unit_name": parent_org_dict.get("org_unit_name"),
        "parent_org": parent_org_dict.get("parent_org"),
        "level": level,
        "cost": 0,
        "delta": 0,
    }
    org_values[parent_org] = parent_org_cost_dict
    return next_parent


def apply_cost_to_parent_ou(parent_org, org_dict, org_values, orgs_in_ous, accounts_in_ous):
    parent_org_dict = org_values.get(parent_org, {})
    if parent_org_dict:
        parent_org_dict["cost"] = parent_org_dict.get("cost", 0) + org_dict.get("cost", 0)
        parent_org_dict["delta"] = parent_org_dict.get("delta", 0) + org_dict.get("delta", 0)
        org_values[parent_org] = parent_org_dict
        if not orgs_in_ous.get(parent_org):
            orgs_in_ous[parent_org] = []
        orgs_in_ous[parent_org].append(org_dict)

        for acct in accounts_in_ous.get(parent_org, []):
            parent_org_dict["cost"] = parent_org_dict.get("cost", 0) + acct.get("cost", 0)
            parent_org_dict["delta"] = parent_org_dict.get("delta", 0) + acct.get("delta", 0)


email_list = []
print(f"COST_MGMT_RECIPIENTS={Config.COST_MGMT_RECIPIENTS}")
account_users = get_users()
print(f"Account has {len(account_users)} users.")
for user in account_users:
    username = user.get("username")
    # if username not in Config.COST_MGMT_RECIPIENTS.keys():
    #     print(f"User {username} is not in recipient list.")
    # else:
    if username in Config.COST_MGMT_RECIPIENTS.keys():
        print(f"User {username} is not in recipient list.")
        user_email = user.get("email")
        cc_list = Config.COST_MGMT_RECIPIENTS.get(username, {}).get("cc", [])
        print(f"User {username} is in recipient list with email {user_email} and cc list {cc_list}.")
        user_access = get_access(username, [AWS_ACCOUNT_ACCESS, AWS_ORG_ACCESS])
        user_info = {
            "user": user,
            "aws.account": user_access[AWS_ACCOUNT_ACCESS],
            "aws.organizational_unit": user_access[AWS_ORG_ACCESS],
            "cc": cc_list,
        }
        email_list.append(user_info)


aws_orgs_monthly_params = costquerier.CURRENT_MONTH_PARAMS.copy()
org_units_response = costquerier.get_cost_data(path=costquerier.AWS_ORG_UNIT_ENDPONT, params=aws_orgs_monthly_params)

org_units_data = org_units_response.get("data", [])
org_units = {}
orgs_in_ou = {}
aws_accounts_in_ou = {}
for org in org_units_data:
    org_unit_id = org.get("org_unit_id")
    org_units[org_unit_id] = org
    accounts = org.get("accounts", [])
    for account in accounts:
        aws_accounts_in_ou[account] = org_unit_id

for org_unit_id, org in org_units.items():
    sub_orgs = org.get("sub_orgs", [])
    for sub_org in sub_orgs:
        sub_org_dict = org_units.get(sub_org, {})
        sub_org_dict["parent_org"] = org_unit_id

for email_item in email_list:  # noqa C901
    images = []
    img_paths = [str(LOGO_PATH)]
    print(f"User info: {email_item}.")
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    aws_accounts = email_item.get("aws.account", [])
    aws_orgs_access = email_item.get("aws.organizational_unit", [])
    aws_daily_params = costquerier.CURRENT_COST_MONTH_PARAMS.copy()
    aws_daily_params["filter[resolution]"] = "daily"
    aws_monthly_params = costquerier.CURRENT_COST_MONTH_PARAMS.copy()
    aws_monthly_params["filter[resolution]"] = "monthly"
    aws_monthly_params["group_by[account]"] = "*"
    daily_costs = {}
    monthly_costs = {}
    if is_org_admin:
        daily_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_daily_params)
        monthly_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_monthly_params)
    elif len(aws_accounts) or len(aws_orgs_access):
        if len(aws_accounts):
            aws_daily_params["filter[account]"] = ",".join(aws_accounts)
            aws_monthly_params["filter[account]"] = ",".join(aws_accounts)
        if len(aws_orgs_access):
            aws_daily_params["filter[org_unit_id]"] = ",".join(aws_orgs_access)
            aws_monthly_params["filter[org_unit_id]"] = ",".join(aws_orgs_access)
        daily_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_daily_params)
        monthly_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_monthly_params)
    else:
        continue
    meta = daily_costs.get("meta", {})
    daily_data = daily_costs.get("data", [])

    values_present = False
    for day_data in daily_data:
        if day_data.get("values"):
            values_present = True

    if not daily_data or not values_present:
        print("Empty daily data values ... skipping report.")
        continue

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
            f"AWS costs for {current_month} are {formatted_total}"
            f' {total["units"]} with a delta of'
            f' {formatted_delta} {total["units"]}'
        )

        monthly_data = monthly_costs.get("data", [{}])
        accounts_data = monthly_data[0].get("accounts", [])
        orgs_in_ous = {}
        accounts_in_ous = {}
        accounts_not_in_ous = []
        account_breakdown = []
        org_values = {}
        org_values_list = []
        for acct_data in accounts_data:
            acct_datum = acct_data.get("values", [{}])[0]
            account_breakdown.append(acct_datum)
            account_id = acct_datum.get("account")
            account_alias = acct_datum.get("account_alias")
            account_monthly_cost = acct_datum.get("cost", {}).get("total").get("value")
            account_monthly_delta = acct_datum.get("delta_value")

            aws_org = {}
            cur_org_unit_id = aws_accounts_in_ou.get(account_alias)
            cur_org_unit_name = None
            if cur_org_unit_id:
                aws_org = org_units.get(cur_org_unit_id, {})
                cur_org_unit_name = aws_org.get("org_unit_name")

            account_dict = {
                "account": account_id,
                "account_alias": account_alias,
                "cost": account_monthly_cost,
                "delta": account_monthly_delta,
                "parent": cur_org_unit_id,
            }

            if not aws_org:
                accounts_not_in_ous.append(account_dict)
            else:
                if not accounts_in_ous.get(cur_org_unit_id, []):
                    accounts_in_ous[cur_org_unit_id] = []
                accounts_in_ous[cur_org_unit_id].append(account_dict)
                parent_org_id = aws_org.get("parent_org")
                org_level = 0
                if cur_org_unit_id not in aws_orgs_access:
                    org_level = 1 + get_org_level(parent_org_id, aws_orgs_access, org_units)
                org_dict = {
                    "org_unit_id": cur_org_unit_id,
                    "org_unit_name": cur_org_unit_name,
                    "parent_org": parent_org_id,
                    "level": org_level,
                    "cost": account_monthly_cost,
                    "delta": account_monthly_delta,
                }
                if not org_values.get(cur_org_unit_id, {}):
                    org_values[cur_org_unit_id] = org_dict
                else:
                    cur_org_value = org_values.get(cur_org_unit_id, {})
                    org_dict["cost"] = cur_org_value.get("cost", 0) + org_dict.get("cost", 0)
                    org_dict["delta"] = cur_org_value.get("delta", 0) + org_dict.get("delta", 0)
                    org_values[cur_org_unit_id] = org_dict

                if cur_org_unit_id not in aws_orgs_access:
                    parent_org = aws_org.get("parent_org")
                    while parent_org:
                        parent_org = construct_parent_org(parent_org, aws_orgs_access, org_units, org_values)

        org_level = 5
        for i in range(org_level, -1, -1):
            cur_org_level_list = []
            for _, cur_org in org_values.items():
                cur_level = cur_org.get("level")
                if cur_level == i:
                    cur_org_level_list.append(cur_org)

            for the_org in cur_org_level_list:
                the_parent_org = the_org.get("parent_org")
                apply_cost_to_parent_ou(the_parent_org, the_org, org_values, orgs_in_ous, accounts_in_ous)

        for _, org_value in org_values.items():
            org_values_list.append(org_value)
        org_values_list = sorted(org_values_list, key=lambda i: i["delta"], reverse=True)

        for org_unit_id, org_list in orgs_in_ous.items():
            org_list = sorted(org_list, key=lambda i: i["delta"], reverse=True)
            orgs_in_ous[org_unit_id] = org_list

        for org_unit_id, acct_list in accounts_in_ous.items():
            acct_list = sorted(acct_list, key=lambda i: i["delta"], reverse=True)
            accounts_in_ous[org_unit_id] = acct_list

        for ov in org_values_list:
            print(f"{ov}")
            org_unit_id = ov.get("org_unit_id")
            org_list = orgs_in_ous.get(org_unit_id, [])
            for org in org_list:
                print(f"    {org}")
            acct_list = accounts_in_ous.get(org_unit_id, [])
            for acct in acct_list:
                print(f"    {acct}")

        accounts_not_in_ous = sorted(accounts_not_in_ous, key=lambda i: i["delta"], reverse=True)

        account_breakdown = sorted(account_breakdown, key=lambda i: i["delta_value"], reverse=True)

        email_template = Template(EMAIL_TEMPLATE_CONTENT)
        template_variables = {
            "cost_timeframe": current_month,
            "aws_cost": float(formatted_total),
            "aws_cost_delta": float(formatted_delta),
            "aws_account_breakdown": account_breakdown,
            "aws_org_unit_list": org_values_list,
            "aws_orgs_in_ous": orgs_in_ous,
            "aws_accounts_in_ous": accounts_in_ous,
            "aws_accounts_not_in_ous": accounts_not_in_ous,
            "web_url": PRODUCTION_ENDPOINT,
            "units": CURRENCY_SYMBOLS_MAP.get(total["units"]),
            "aws_img_index": 1,
        }
        for img_path in img_paths:
            file_name = img_path.split("/")[-1]
            template_variables[file_name] = file_name
        email_msg = email_template.render(**template_variables)
        email(recipients=email_addrs, content=email_msg, attachments=img_paths)

        for img in images:
            if os.path.exists(img.name):
                os.unlink(img.name)
                img.close()
