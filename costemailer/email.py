import smtplib
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from costemailer.config import Config
from jinja2 import Template


REL_TEMPLATE_PATH = "resources/CostEmailTemplate.html"
EMAIL_TEMPLATE_PATH = Path(__file__).parent / REL_TEMPLATE_PATH
EMAIL_TEMPLATE_CONTENT = None
with open(EMAIL_TEMPLATE_PATH) as email_template:
    EMAIL_TEMPLATE_CONTENT = email_template.read()


def render_email(template_variables, img_paths):
    email_template = Template(EMAIL_TEMPLATE_CONTENT)
    for img_path in img_paths:
        file_name = img_path.split("/")[-1]
        template_variables[file_name] = file_name
    return email_template.render(**template_variables)


def email(recipients, content=EMAIL_TEMPLATE_CONTENT, attachments=None, subject=None):
    if not recipients:
        return
    gmail_user = Config.EMAIL_USER
    gmail_password = Config.EMAIL_PASSWORD
    s = smtplib.SMTP("smtp.gmail.com:587")
    s.starttls()
    s.login(gmail_user, gmail_password)

    today = datetime.today().strftime("%Y-%m-%d")
    if not subject:
        subject = f"Cost Management Report: {today}"

    msg = MIMEMultipart()
    sender = "cost-mgmt@redhat.com"
    msg_text = content
    msg["Subject"] = subject
    msg["From"] = sender
    # msg["To"] = ",".join(recipients)
    msg["To"] = "chambrid@redhat.com"
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
    s.sendmail(sender, "chambrid@redhat.com", msg.as_string())
    # s.sendmail(sender, recipients, msg.as_string())
