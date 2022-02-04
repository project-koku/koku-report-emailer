from costemailer.config import Config
from costemailer.rbac import AWS_ACCOUNT_ACCESS
from costemailer.rbac import get_access
from costemailer.rbac import get_users


def process_config():
    email_list = []
    print(f"COST_MGMT_RECIPIENTS={Config.COST_MGMT_RECIPIENTS}")
    account_users = get_users()
    print(f"Account has {len(account_users)} users.")
    for user in account_users:
        username = user.get("username")
        if username not in Config.COST_MGMT_RECIPIENTS.keys():
            print(f"User {username} is not in recipient list.")
        else:
            user_email = user.get("email")
            cc_list = Config.COST_MGMT_RECIPIENTS.get(username, {}).get("cc", [])
            budget = Config.COST_MGMT_RECIPIENTS.get(username, {}).get("budget", {})

            print(f"User {username} is in recipient list with email {user_email} and cc list {cc_list}.")
            user_info = {
                "user": user,
                "aws.account": get_access(username, AWS_ACCOUNT_ACCESS),
                "cc": cc_list,
                "budget": budget,
            }
            email_list.append(user_info)

    return email_list
