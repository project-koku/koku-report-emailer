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


def check_thresholds(budget_total, thresholds_list, daily_totals):
    threshold_triggered = None
    thresholds_dict = {}
    for threshold in thresholds_list:
        thresholds_dict[threshold] = {"alert": False}
        if total < (budget_total * threshold):
            break

        print(f"Current cost {total} is over {threshold} of budget {budget_total}.")
        day_step_total = 0
        day_counter = 0
        num_days = len(daily_totals)
        for day in daily_totals:
            day_counter += 1
            day_step_total += day.get("total")
            if day_step_total > (budget_total * threshold):
                if day_counter < num_days:
                    break
                elif day_counter == num_days:
                    thresholds_dict[threshold] = {"alert": True}
                    threshold_triggered = threshold
                    break
        if threshold_triggered:
            break
    print(f"{thresholds_dict}")
    return threshold_triggered, thresholds_dict


email_list = process_config()
for email_item in email_list:
    images = []
    img_paths = [str(LOGO_PATH)]
    print(f"User info: {email_item}.")

    budget = email_item.get("budget")
    if not budget:
        break

    aws_budget = budget.get("aws", {})
    aws_budget_total = aws_budget.get("total")
    aws_budget_total_thresholds = aws_budget.get("thresholds", [0.5, 0.75])
    aws_budget_accounts = aws_budget.get("accounts")

    if aws_budget_accounts and aws_budget_accounts.keys():
        aws_budget_total = 0
        for acct_budget_num, acct_budget in aws_budget_accounts.items():
            aws_budget_total += acct_budget["total"]

    print(f"{aws_budget_total} - {aws_budget_total_thresholds} - {aws_budget_accounts}.")

    if aws_budget is None:
        break

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
    total_obj = meta["total"]["cost"]["total"]
    total = total_obj["value"]

    daily_totals = []
    for day_data in daily_data:
        day_date = day_data["date"]
        if day_data["values"]:
            day_total = day_data["values"][0]["cost"]["total"]["value"]
            daily_totals.append({"date": day_date, "total": day_total})

    if total > aws_budget_total:
        print(f"Current cost {total} is over budget {aws_budget_total}.")
        break

    aws_budget_total_alert_triggered, aws_budget_total_thresholds_dict = check_thresholds(
        aws_budget_total, aws_budget_total_thresholds, daily_totals
    )

    if aws_budget_total_alert_triggered:
        img_file, img_path = plot_data(daily_data)
        images.append(img_file)
        img_paths.append(img_path)

        daily = daily_data[0]
        date = daily["date"]
        formatted_total = f"{total:.2f}"
        formatted_delta = "{:.2f}".format(meta["delta"]["value"])
        formatted_budget_total = f"{aws_budget_total:.2f}"
        current_month = date[:-3]
        print(
            f"AWS costs for {current_month} are {formatted_total}"
            f' {total_obj["units"]} with a delta of'
            f' {formatted_delta} {total_obj["units"]}'
        )

        monthly_data = montly_costs.get("data", [])
        accounts_data = monthly_data[0].get("accounts", [])
        account_breakdown = []
        for acct_data in accounts_data:
            acct_datum = acct_data.get("values", [{}])[0]
            acct_number = acct_datum.get("account")
            acct_budget = aws_budget_accounts.get(acct_number)
            if acct_budget:
                acct_datum["budget"] = acct_budget["total"]
            account_breakdown.append(acct_datum)
            print(
                f"{acct_datum.get('account')}/{acct_datum.get('account_alias')}: {acct_datum.get('cost',{}).get('total')} ({acct_datum.get('delta_value')})"
            )

        template_variables = {
            "cost_masthead": f"Monthly total budget threshold of {int(aws_budget_total_alert_triggered * 100)}% exceeded",
            "aws_cost": formatted_total,
            "aws_cost_delta": formatted_delta,
            "aws_budget_monthly_total": formatted_budget_total,
            "aws_account_breakdown": account_breakdown,
            "web_url": PRODUCTION_ENDPOINT,
            "units": total_obj["units"],
            "aws_img_index": 1,
        }

        subject = f"Cost Management Report: Monthly total budget threshold of {int(aws_budget_total_alert_triggered * 100)}% exceeded"

        email_msg = render_email(template_variables, img_paths)
        email(recipients=email_addrs, content=email_msg, attachments=img_paths, subject=subject)

        for img in images:
            if os.path.exists(img.name):
                os.unlink(img.name)
                img.close()
