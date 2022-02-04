import os
from pathlib import Path

from costemailer import costquerier
from costemailer.charting import plot_data
from costemailer.email import email
from costemailer.email import render_email
from costemailer.processor import process_config


PRODUCTION_ENDPOINT = "https://console.redhat.com"
REL_LOGO_PATH = "costemailer/resources/Logo-Red_Hat-cost-management-RGB.png"
LOGO_PATH = Path(__file__).parent / REL_LOGO_PATH


email_list = process_config()
for email_item in email_list:
    images = []
    img_paths = [str(LOGO_PATH)]
    print(f"User info: {email_item}.")
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
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

        monthly_data = montly_costs.get("data", [])
        accounts_data = monthly_data[0].get("accounts", [])
        account_breakdown = []
        for acct_data in accounts_data:
            acct_datum = acct_data.get("values", [{}])[0]
            account_breakdown.append(acct_datum)
            print(
                f"{acct_datum.get('account')}/{acct_datum.get('account_alias')}: {acct_datum.get('cost',{}).get('total')} ({acct_datum.get('delta_value')})"
            )

        template_variables = {
            "cost_masthead": f"Cost Management update for {current_month}",
            "aws_cost": formatted_total,
            "aws_cost_delta": formatted_delta,
            "aws_account_breakdown": account_breakdown,
            "web_url": PRODUCTION_ENDPOINT,
            "units": total["units"],
            "aws_img_index": 1,
        }
        # email_msg = render_email(template_variables, img_paths)
        # email(recipients=email_addrs, content=email_msg, attachments=img_paths)

        for img in images:
            if os.path.exists(img.name):
                os.unlink(img.name)
                img.close()
