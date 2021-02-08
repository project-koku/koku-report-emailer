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


images = []
img_paths = []
for key, value in Config.COST_MGMT_RECIPIENTS_JSON.items():
    print(f"Creating email content for {key} with values {value}.")
    email_addrs = value.get("emails", [])
    if email_addrs is None:
        break
    aws = value.get("aws", {})
    costs = costquerier.get_cost_data(path=costquerier.AWS_COST_ENDPONT, params=aws)
    meta = costs.get("meta", {})
    data = costs.get("data", [])
    img_file, img_path = plot_data(data)
    images.append(img_file)
    img_paths.append(img_path)

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
