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
from costemailer.charting import plot_data
from costemailer.config import Config
from costemailer.rbac import AWS_ACCOUNT_ACCESS
from costemailer.rbac import get_access
from costemailer.rbac import get_users
from jinja2 import Template


PRODUCTION_ENDPOINT = "https://cloud.redhat.com"
REL_TEMPLATE_PATH = "costemailer/resources/CostEmailTemplate.html"
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
    subject = f"Cost Management Report: {today}"
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


email_list = []
print(f"COST_MGMT_RECIPIENTS={Config.COST_MGMT_RECIPIENTS}")
account_users = get_users()
print(f"Account has {len(account_users)} users.")
for user in account_users:
    username = user.get("username")
    if username not in Config.COST_MGMT_RECIPIENTS:
        print(f"User {username} is not in recipient list.")
    else:
        user_email = user.get("email")
        print(f"User {username} is in recipient list with email {user_email}.")
        user_info = {"user": user, "aws.account": get_access(username, AWS_ACCOUNT_ACCESS)}
        email_list.append(user_info)


images = []
img_paths = []
for email_item in email_list:
    print(f"User info: {email_item}.")
    email_addrs = [email_item.get("user", {}).get("email")]
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    aws_accounts = email_item.get("aws.account", [])
    aws_daily_params = costquerier.CURRENT_MONTH_PARAMS.copy()
    aws_daily_params["filter[resolution]"] = "daily"
    aws_montly_params = costquerier.CURRENT_MONTH_PARAMS.copy()
    aws_montly_params["filter[resolution]"] = "monthly"
    aws_montly_params["group_by[account]"] = "*"
    daily_costs = {}
    montly_costs = {}
    if is_org_admin:
        daily_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_daily_params)
        montly_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_montly_params)
    elif len(aws_accounts):
        for acct in aws_accounts:
            aws_daily_params["filter[account]"] = ",".join(aws_accounts)
            aws_montly_params["filter[account]"] = ",".join(aws_accounts)
        daily_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_daily_params)
        montly_costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws_montly_params)
    else:
        break
    meta = daily_costs.get("meta", {})
    daily_data = daily_costs.get("data", [])
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

        monthly_data = montly_costs.get("data", [])
        accounts_data = monthly_data[0].get("accounts", [])
        account_breakdown = []
        for acct_data in accounts_data:
            acct_datum = acct_data.get("values", [{}])[0]
            account_breakdown.append(acct_datum)
            print(
                f"{acct_datum.get('account')}/{acct_datum.get('account_alias')}: {acct_datum.get('cost',{}).get('total')} ({acct_datum.get('delta_value')})"
            )

        email_template = Template(EMAIL_TEMPLATE_CONTENT)
        template_variables = {
            "cost_timeframe": current_month,
            "aws_cost": formatted_total,
            "aws_cost_delta": formatted_delta,
            "aws_account_breakdown": account_breakdown,
            "web_url": PRODUCTION_ENDPOINT,
            "units": total["units"],
            "aws_img_index": 0,
        }
        for img_path in img_paths:
            file_name = img_path.split("/")[-1]
            template_variables[file_name] = file_name
        email_msg = email_template.render(**template_variables)
        email(recipients=email_addrs, content=email_msg, attachments=img_paths)

    for img in images:
        os.unlink(img.name)
        img.close()
