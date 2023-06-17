from costemailer import costquerier
from costemailer import DEFAULT_ACCOUNT_LIMIT
from costemailer import DEFAULT_ORDER
from costemailer import DEFAULT_ORG_LEVEL_LIMIT
from costemailer import DEFAULT_REPORT_ISO_DAYS
from costemailer import DEFAULT_REPORT_TYPE
from costemailer import LOGO_PATH
from costemailer.config import Config
from costemailer.rbac import AWS_ACCOUNT_ACCESS
from costemailer.rbac import AWS_ORG_ACCESS
from costemailer.rbac import AZURE_SUBSCRIPTION_ID_ACCESS
from costemailer.rbac import get_access
from costemailer.rbac import get_users
from costemailer.rbac import OPENSHIFT_CLUSTER_ACCESS
from costemailer.rbac import OPENSHIFT_PROJECT_ACCESS
from costemailer.reporting.aws import email_report as aws_email_report
from costemailer.reporting.azure import email_report as azure_email_report
from costemailer.reporting.ibm import email_report as ibm_email_report
from costemailer.reporting.openshift import email_report as ocp_email_report


email_list = []
print(f"COST_MGMT_RECIPIENTS={Config.COST_MGMT_RECIPIENTS}")
account_users = get_users()
print(f"Account has {len(account_users)} users.")
for user in account_users:
    username = user.get("username")
    if username in Config.COST_MGMT_RECIPIENTS.keys():
        user_email = user.get("email")
        cc_list = Config.COST_MGMT_RECIPIENTS.get(username, {}).get("cc", [])
        print(f"User {username} is in recipient list with email {user_email}.")
        report_type = Config.COST_MGMT_RECIPIENTS.get(username, {}).get("report_type", DEFAULT_REPORT_TYPE)
        user_access = get_access(
            username,
            [
                AWS_ACCOUNT_ACCESS,
                AWS_ORG_ACCESS,
                OPENSHIFT_CLUSTER_ACCESS,
                OPENSHIFT_PROJECT_ACCESS,
                AZURE_SUBSCRIPTION_ID_ACCESS,
            ],
        )
        reports_list = Config.COST_MGMT_RECIPIENTS.get(username, {}).get("reports", [])
        if not reports_list:
            reports_list.append(Config.COST_MGMT_RECIPIENTS.get(username, {}))

        for report in reports_list:
            report_filter = report.get("filter", {})
            report_schedule = report.get("schedule", DEFAULT_REPORT_ISO_DAYS)
            report_view = report.get("view", "ou")
            report_cc = report.get("cc", [])
            report_type_item = report.get("report_type", report_type)
            report_order = report.get("order", DEFAULT_ORDER)
            report_org_level_limit = report.get("org_level_limit", DEFAULT_ORG_LEVEL_LIMIT)
            report_account_limit = report.get("account_limit", DEFAULT_ACCOUNT_LIMIT)
            report_title_suffix = report.get("title_suffix")
            report_info = {
                "user": user,
                "aws.account": user_access[AWS_ACCOUNT_ACCESS],
                "aws.organizational_unit": user_access[AWS_ORG_ACCESS],
                "openshift.cluster": user_access[OPENSHIFT_CLUSTER_ACCESS],
                "openshift.project": user_access[OPENSHIFT_PROJECT_ACCESS],
                "azure.subscriptions": user_access[AZURE_SUBSCRIPTION_ID_ACCESS],
                "cc": cc_list + report_cc,
                "report_type": report_type_item,
                "filter": report_filter,
                "schedule": report_schedule,
                "view": report_view,
                "order": report_order,
                "org_level_limit": report_org_level_limit,
                "account_limit": report_account_limit,
                "title_suffix": report_title_suffix,
            }
            email_list.append(report_info)

aws_orgs_monthly_params = costquerier.CURRENT_MONTH_PARAMS.copy()
org_units_response = costquerier.get_cost_data(path=costquerier.AWS_ORG_UNIT_ENDPOINT, params=aws_orgs_monthly_params)

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
    report_type = email_item.get("report_type", DEFAULT_REPORT_TYPE)
    if report_type == "AWS":
        aws_email_report(email_item, images, img_paths, aws_accounts_in_ou=aws_accounts_in_ou, org_units=org_units)
    elif report_type == "OCP":
        ocp_email_report(email_item, images, img_paths)
    elif report_type == "IBM":
        ibm_email_report(email_item, images, img_paths)
    elif report_type == "AZURE":
        azure_email_report(email_item, images, img_paths)
    else:
        pass
