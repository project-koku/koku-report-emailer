import csv
import os
import tempfile

from costemailer import CURRENCY_SYMBOLS_MAP
from costemailer import DEFAULT_ACCOUNT_LIMIT
from costemailer import DEFAULT_ORDER
from costemailer import DEFAULT_ORG_LEVEL_LIMIT
from costemailer import DEFAULT_REPORT_ISO_DAYS
from costemailer import DEFAULT_REPORT_TYPE
from costemailer import get_email_content
from costemailer import PRODUCTION_ENDPOINT
from costemailer.charting import plot_data
from costemailer.costquerier import AWS_COST_CATEGORIES_ENDPOINT
from costemailer.costquerier import get_cost_data
from costemailer.email import email
from costemailer.email import email_subject
from costemailer.reporting import get_daily_cost
from costemailer.reporting import get_monthly_cost
from jinja2 import Template


AWS_REPORT_VIEW_ORG_UNITS = "ou"
AWS_REPORT_VIEW_COST_CENTER = "cost_center"
DEFAULT_AWS_REPORT_VIEW = AWS_REPORT_VIEW_ORG_UNITS


def get_cost_centers():
    cost_centers = {}
    cost_centers = get_cost_data(path=AWS_COST_CATEGORIES_ENDPOINT, params={"key": "CostCenter"})
    return cost_centers


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


def apply_account_costs(org_dict, accounts_in_ous, debug=False):
    org_unit_id = org_dict.get("org_unit_id")
    if debug:
        print(f"org={org_unit_id}")
    for acct in accounts_in_ous.get(org_unit_id, []):
        org_dict["cost"] = org_dict.get("cost", 0) + acct.get("cost", 0)
        org_dict["delta"] = org_dict.get("delta", 0) + acct.get("delta", 0)
        if debug:
            print(f"acct={acct}")
            print(f"org_dict={org_dict}")
    return org_dict


def apply_cost_to_parent_ou(parent_org, org_dict, org_values, orgs_in_ous, debug=False):
    parent_org_dict = org_values.get(parent_org, {})
    if debug:
        print(f"org={org_dict.get('org_unit_id')}")
        print(f"parent_org={parent_org}")
    if parent_org_dict:
        parent_org_dict["cost"] = parent_org_dict.get("cost", 0) + org_dict.get("cost", 0)
        parent_org_dict["delta"] = parent_org_dict.get("delta", 0) + org_dict.get("delta", 0)
        if not orgs_in_ous.get(parent_org):
            orgs_in_ous[parent_org] = []
        if debug:
            print(f"Adding {org_dict.get('org_unit_id')} to {parent_org} list.")
            print(f"parent_org_dict={parent_org_dict}")
        orgs_in_ous[parent_org].append(org_dict)
        org_values[parent_org] = parent_org_dict


def email_report_cost_centers(
    report_type,
    monthly_params,
    is_org_admin,
    cost_order,
    account_limit,
    current_month,
    total,
    img_paths,
    filtered_cost_centers,
):
    email_msg = None
    cost_centers = []
    cost_centers_response = get_cost_centers()
    cost_centers_data = cost_centers_response.get("data", [])
    if cost_centers_data:
        cost_centers = cost_centers_data[0].get("values", [])

    if filtered_cost_centers:
        if cost_centers:
            cost_centers = list(set(cost_centers).intersection(filtered_cost_centers))
        else:
            cost_centers = filtered_cost_centers

    my_total = 0
    my_delta = 0
    cost_centers_list = []
    for cost_center in cost_centers:
        cc_total = 0
        cc_delta = 0
        monthly_params["filter[aws_category:CostCenter]"] = cost_center
        monthly_costs = get_monthly_cost(report_type=report_type, params=monthly_params, is_org_admin=is_org_admin)
        monthly_data = monthly_costs.get("data", [{}])
        accounts_data = monthly_data[0].get("accounts", [])
        accounts_list = []
        for acct_data in accounts_data:
            acct_datum = acct_data.get("values", [{}])[0]
            account_id = acct_datum.get("account")
            account_alias = acct_datum.get("account_alias")
            account_monthly_cost = acct_datum.get("cost", {}).get("total").get("value")
            account_monthly_delta = acct_datum.get("delta_value")

            cc_total += account_monthly_cost
            cc_delta += account_monthly_delta
            my_total += account_monthly_cost
            my_delta += account_monthly_delta
            account_dict = {
                "account": account_id,
                "account_alias": account_alias,
                "cost": account_monthly_cost,
                "delta": account_monthly_delta,
            }
            accounts_list.append(account_dict)
        accounts_list = sorted(accounts_list, key=lambda i: i[cost_order], reverse=True)
        cost_center_dict = {"name": cost_center, "cost": cc_total, "delta": cc_delta, "accounts": accounts_list}
        cost_centers_list.append(cost_center_dict)
    cost_centers_list = sorted(cost_centers_list, key=lambda i: i[cost_order], reverse=True)

    email_template = Template(get_email_content(report_type))
    template_variables = {
        "cost_timeframe": current_month,
        "aws_cost": float(my_total),
        "aws_cost_delta": float(my_delta),
        "aws_cost_center_list": cost_centers_list,
        "account_limit": account_limit,
        "web_url": PRODUCTION_ENDPOINT,
        "units": CURRENCY_SYMBOLS_MAP.get(total["units"]),
        "aws_img_index": 1,
    }
    for img_path in img_paths:
        file_name = img_path.split("/")[-1]
        template_variables[file_name] = file_name
    email_msg = email_template.render(**template_variables)
    return email_msg, cost_centers_list


def email_report_ou(  # noqa
    report_type,
    monthly_params,
    is_org_admin,
    aws_accounts_in_ou,
    org_units,
    aws_accounts,
    aws_orgs_access,
    cost_order,
    org_level_limit,
    account_limit,
    current_month,
    total,
    img_paths,
):
    email_msg = None
    monthly_costs = get_monthly_cost(report_type=report_type, params=monthly_params, is_org_admin=is_org_admin)
    monthly_data = monthly_costs.get("data", [{}])
    accounts_data = monthly_data[0].get("accounts", [])
    orgs_in_ous = {}
    accounts_in_ous = {}
    accounts_not_in_ous = []
    account_breakdown = []
    org_values = {}
    org_values_list = []
    my_total = 0
    my_delta = 0
    for acct_data in accounts_data:
        acct_datum = acct_data.get("values", [{}])[0]
        account_breakdown.append(acct_datum)
        account_id = acct_datum.get("account")
        account_alias = acct_datum.get("account_alias")
        account_monthly_cost = acct_datum.get("cost", {}).get("total").get("value")
        account_monthly_delta = acct_datum.get("delta_value")

        my_total += account_monthly_cost
        my_delta += account_monthly_delta

        aws_org = {}
        cur_org_unit_id = aws_accounts_in_ou.get(account_alias)
        cur_org_unit_name = None
        if cur_org_unit_id:
            aws_org = org_units.get(cur_org_unit_id, {})
            cur_org_unit_name = aws_org.get("org_unit_name")
        else:
            print(f"{account_alias} not found in Org Units.")

        account_dict = {
            "account": account_id,
            "account_alias": account_alias,
            "cost": account_monthly_cost,
            "delta": account_monthly_delta,
            "parent": cur_org_unit_id,
        }
        if aws_accounts and account_id not in aws_accounts:
            continue

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
    cur_org_level_list = []
    for i in range(org_level, -1, -1):
        cur_org_level_list = []
        for _, cur_org in org_values.items():
            cur_level = cur_org.get("level")
            if cur_level == i:
                cur_org_level_list.append(cur_org)

        for the_org in cur_org_level_list:
            the_parent_org = the_org.get("parent_org")
            apply_cost_to_parent_ou(the_parent_org, the_org, org_values, orgs_in_ous)

    for _, org_value in org_values.items():
        org_values_list.append(org_value)
    org_values_list = sorted(org_values_list, key=lambda i: i[cost_order], reverse=True)

    for org_unit_id, org_list in orgs_in_ous.items():
        org_list = sorted(org_list, key=lambda i: i[cost_order], reverse=True)
        orgs_in_ous[org_unit_id] = org_list

    for org_unit_id, acct_list in accounts_in_ous.items():
        acct_list = sorted(acct_list, key=lambda i: i[cost_order], reverse=True)
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

    accounts_not_in_ous = sorted(accounts_not_in_ous, key=lambda i: i[cost_order], reverse=True)

    if cost_order == "delta":
        account_breakdown = sorted(account_breakdown, key=lambda i: i["delta_value"], reverse=True)
    else:
        account_breakdown = sorted(account_breakdown, key=lambda i: i["cost"]["total"]["value"], reverse=True)

    print(f"org_values_list={len(org_values_list)}")
    print(f"accounts_not_in_ous={len(accounts_not_in_ous)}")
    print(f"account_breakdown={len(account_breakdown)}")

    filtered_org_list = []
    unique_org_list = []
    for org in org_values_list:
        org_unit_id = org.get("org_unit_id")
        if org_unit_id not in unique_org_list:
            unique_org_list.append(org_unit_id)
            if org.get("level", 5) <= org_level_limit:
                filtered_org_list.append(org)

    email_template = Template(get_email_content(report_type))
    template_variables = {
        "cost_timeframe": current_month,
        "aws_cost": float(my_total),
        "aws_cost_delta": float(my_delta),
        "aws_account_breakdown": account_breakdown,
        "aws_org_unit_list": filtered_org_list,
        "aws_orgs_in_ous": orgs_in_ous,
        "aws_accounts_in_ous": accounts_in_ous,
        "aws_accounts_not_in_ous": accounts_not_in_ous,
        "account_limit": account_limit,
        "web_url": PRODUCTION_ENDPOINT,
        "units": CURRENCY_SYMBOLS_MAP.get(total["units"]),
        "aws_img_index": 1,
    }
    for img_path in img_paths:
        file_name = img_path.split("/")[-1]
        template_variables[file_name] = file_name
    email_msg = email_template.render(**template_variables)
    return email_msg, accounts_in_ous, accounts_not_in_ous


def email_report(email_item, images, img_paths, **kwargs):  # noqa: C901
    report_type = email_item.get("report_type", DEFAULT_REPORT_TYPE)
    report_schedule = email_item.get("schedule", DEFAULT_REPORT_ISO_DAYS)
    report_view = email_item.get("view", DEFAULT_AWS_REPORT_VIEW)
    report_filter = email_item.get("filter", {})
    report_title_suffix = email_item.get("title_suffix")
    filtered_accounts = report_filter.get("accounts", [])
    filtered_orgs = report_filter.get("orgs", [])
    filtered_cost_centers = report_filter.get("cost_centers", [])
    aws_accounts_in_ou = kwargs.get("aws_accounts_in_ou", {})
    org_units = kwargs.get("org_units", {})
    cost_order = email_item.get("order", DEFAULT_ORDER)
    print(f"User info: {email_item}.")
    curr_user_email = email_item.get("user", {}).get("email")
    email_addrs = [curr_user_email] + email_item.get("cc", [])
    is_org_admin = email_item.get("user", {}).get("is_org_admin", False)
    aws_accounts = email_item.get("aws.account", [])
    aws_orgs_access = email_item.get("aws.organizational_unit", [])
    org_level_limit = email_item.get("org_level_limit", DEFAULT_ORG_LEVEL_LIMIT)
    account_limit = email_item.get("account_limit", DEFAULT_ACCOUNT_LIMIT)

    if filtered_orgs:
        if aws_orgs_access:
            aws_orgs_access = list(set(aws_orgs_access).intersection(filtered_orgs))
        else:
            aws_orgs_access = filtered_orgs
    if filtered_accounts:
        if aws_accounts:
            aws_accounts = list(set(aws_accounts).intersection(filtered_accounts))
        else:
            aws_accounts = filtered_accounts

    daily_costs = {}
    if not is_org_admin and not (len(aws_accounts) or len(aws_orgs_access)):
        print("User has no access.")
        return

    monthly_params = {"group_by[account]": "*"}
    daily_params = {}
    if aws_accounts or aws_orgs_access or filtered_cost_centers:
        if aws_accounts and not filtered_cost_centers:
            daily_params["filter[account]"] = ",".join(aws_accounts)
            monthly_params["filter[account]"] = ",".join(aws_accounts)
        if aws_orgs_access and not filtered_cost_centers:
            daily_params["filter[org_unit_id]"] = ",".join(aws_orgs_access)
            monthly_params["filter[org_unit_id]"] = ",".join(aws_orgs_access)
        if filtered_cost_centers:
            daily_params["filter[aws_category:CostCenter]"] = ",".join(filtered_cost_centers)
            monthly_params["filter[aws_category:CostCenter]"] = ",".join(filtered_cost_centers)

    daily_costs = get_daily_cost(report_type=report_type, params=daily_params, is_org_admin=is_org_admin)
    meta = daily_costs.get("meta", {})
    daily_data = daily_costs.get("data", [])

    values_present = False
    for day_data in daily_data:
        if day_data.get("values"):
            values_present = True

    if not daily_data or not values_present:
        print("Empty daily data values ... skipping report.")
        return

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

        email_msg = None
        accounts_in_ous = None
        accounts_not_in_ous = None
        cost_center_list = None
        if report_view == AWS_REPORT_VIEW_ORG_UNITS:
            email_msg, accounts_in_ous, accounts_not_in_ous = email_report_ou(
                report_type,
                monthly_params,
                is_org_admin,
                aws_accounts_in_ou,
                org_units,
                aws_accounts,
                aws_orgs_access,
                cost_order,
                org_level_limit,
                account_limit,
                current_month,
                total,
                img_paths,
            )
        elif report_view == AWS_REPORT_VIEW_COST_CENTER:
            email_msg, cost_center_list = email_report_cost_centers(
                report_type,
                monthly_params,
                is_org_admin,
                cost_order,
                account_limit,
                current_month,
                total,
                img_paths,
                filtered_cost_centers,
            )

        subject = email_subject(report_type)
        if report_title_suffix:
            subject += f" [{report_title_suffix}]"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        with open(tmp.name, "w", newline="") as csvfile:
            fieldnames = ["account", "account_alias", "cost", "delta"]
            if accounts_in_ous or accounts_not_in_ous:
                fieldnames.append("org_unit")
            if cost_center_list:
                fieldnames.append("cost_center")
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            if accounts_in_ous:
                for _, accts in accounts_in_ous.items():
                    for acct in accts:
                        writer.writerow(
                            {
                                "account": acct.get("account"),
                                "account_alias": acct.get("account_alias"),
                                "cost": acct.get("cost"),
                                "delta": acct.get("delta"),
                                "org_unit": acct.get("parent", ""),
                            }
                        )
            if accounts_not_in_ous:
                for acct in accounts_not_in_ous:
                    writer.writerow(
                        {
                            "account": acct.get("account"),
                            "account_alias": acct.get("account_alias"),
                            "cost": acct.get("cost"),
                            "delta": acct.get("delta"),
                            "org_unit": acct.get("parent", ""),
                        }
                    )
            if cost_center_list:
                for cost_center in cost_center_list:
                    accts = cost_center.get("accounts", [])
                    for acct in accts:
                        writer.writerow(
                            {
                                "account": acct.get("account"),
                                "account_alias": acct.get("account_alias"),
                                "cost": acct.get("cost"),
                                "delta": acct.get("delta"),
                                "cost_center": cost_center.get("name"),
                            }
                        )
        images.append(tmp)
        img_paths.append(tmp.name)

        email(
            recipients=email_addrs,
            subject=subject,
            content=email_msg,
            attachments=img_paths,
            email_iso_days=report_schedule,
        )

        for img in images:
            if os.path.exists(img.name):
                os.unlink(img.name)
                img.close()
