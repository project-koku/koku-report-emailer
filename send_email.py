import smtplib
from datetime import datetime
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from costemailer import costquerier
from costemailer.config import Config
from jinja2 import Template

# from email.mime.image import MIMEImage

PRODUCTION_ENDPOINT = "https://cloud.redhat.com"
REL_TEMPLATE_PATH = "costemailer/resources/CostEmailTemplate.html"
EMAIL_TEMPLATE_PATH = Path(__file__).parent / REL_TEMPLATE_PATH
EMAIL_TEMPLATE_CONTENT = None
with open(EMAIL_TEMPLATE_PATH) as email_template:
    EMAIL_TEMPLATE_CONTENT = email_template.read()


def email(recipients, content=EMAIL_TEMPLATE_CONTENT, attachments=None):
    if recipients is None:
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
    msg["To"] = recipients
    if attachments is not None:
        for each_file_path in attachments:
            try:
                file_name = each_file_path.split("/")[-1]
                part = MIMEBase("application", "octet-stream")
                part.set_payload(open(each_file_path, "rb").read())

                encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=file_name)
                msg.attach(part)
            except:  # noqa: E722
                print("Could not attach file.")
    msg.attach(MIMEText(msg_text, "html"))
    s.sendmail(sender, recipients, msg.as_string())


for key, value in Config.COST_MGMT_RECIPIENTS_JSON.items():
    print(f"Creating email content for {key} with values {value}.")
    email_addr = value.get("email")
    if email_addr is None:
        break
    aws = value.get("aws", {})
    costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws)
    meta = costs.get("meta", {})
    data = costs.get("data", [])
    if len(data) > 0:
        daily = data[0]
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
        email_template = Template(EMAIL_TEMPLATE_CONTENT)
        template_variables = {
            "cost_timeframe": current_month,
            "aws_cost": formatted_total,
            "aws_cost_delta": formatted_delta,
            "web_url": PRODUCTION_ENDPOINT,
            "units": total["units"],
        }
        email_msg = email_template.render(**template_variables)
        email(recipients=email_addr, content=email_msg)
