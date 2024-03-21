import random
import smtplib
import time
from datetime import datetime
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from email.mime.text import MIMEText

from costemailer import DEFAULT_REPORT_ISO_DAYS
from costemailer import DEFAULT_REPORT_TYPE
from costemailer import get_email_content
from costemailer.config import Config


def email_subject(report_type):
    today = datetime.today().strftime("%Y-%m-%d")
    subject = f"{report_type} Cost Management Report: {today}"
    if len(report_type) > 3:
        subject = f"{report_type.capitalize()} Cost Management Report: {today}"
    return subject


def email(
    recipients,
    subject,
    content=get_email_content(DEFAULT_REPORT_TYPE),
    attachments=None,
    email_iso_days=DEFAULT_REPORT_ISO_DAYS,
):
    today = datetime.today()
    day_num = today.isoweekday()

    if Config.RUNTIME_MODE == "dev":
        recipients = [Config.RECIPIENTS_OVERRIDE]
    elif day_num not in email_iso_days:
        print("Email not scheduled for today.")
        return

    if not recipients:
        return
    gmail_user = Config.EMAIL_USER
    gmail_password = Config.EMAIL_PASSWORD
    s = smtplib.SMTP("smtp.gmail.com:587")
    s.starttls()
    s.login(gmail_user, gmail_password)

    msg = MIMEMultipart()
    sender = "cost-mgmt@redhat.com"
    msg_text = content
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ",".join(recipients)
    if attachments is not None:
        attach_count = 0
        for each_file_path in attachments:
            try:
                file_name = each_file_path.split("/")[-1]
                if ".csv" in file_name:
                    # Create the attachment of the message in text/csv.
                    textFile = MIMENonMultipart("text", "csv", charset="utf-8")
                    textFile.add_header("Content-Disposition", "attachment", filename=file_name)
                    textFile.set_payload(open(each_file_path, "r").read())
                    msg.attach(textFile)
                else:
                    msgImage = MIMEImage(open(each_file_path, "rb").read(), filename=file_name)
                    msgImage.add_header("Content-ID", f"<image{attach_count}>")
                    msg.attach(msgImage)
                attach_count += 1
            except Exception as err:  # noqa: E722
                print(f"Could not attach file: {err}")
    msg.attach(MIMEText(msg_text, "html"))
    try:
        time.sleep(random.randint(1, 5))
        s.sendmail(sender, recipients, msg.as_string())
    except Exception as e:
        print(e)
        time.sleep(random.randint(15, 60))
