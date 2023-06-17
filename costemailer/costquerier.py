import time

import requests

from .config import Config


AWS_COST_ENDPOINT = "reports/aws/costs/"
AWS_ORG_UNIT_ENDPOINT = "organizations/aws/"
AWS_COST_CATEGORIES_ENDPOINT = "resource-types/aws-categories/"
AZURE_COST_ENDPOINT = "reports/azure/costs/"
OPENSHIFT_COST_ENDPOINT = "reports/openshift/costs/"
CURRENT_MONTH_PARAMS = {"filter[time_scope_units]": "month", "filter[time_scope_value]": "-1", "limit": "1000"}
CURRENT_COST_MONTH_PARAMS = {"filter[time_scope_units]": "month", "filter[time_scope_value]": "-1", "delta": "cost"}


def get_cost_data(path="status/", params={}, retry_count=0):
    """Obtain the response cost data."""
    api_call = Config.CLOUD_DOT_API_ROOT + Config.COST_MGMT_API_PREFIX + path
    credentials = (Config.CLOUD_DOT_USERNAME, Config.CLOUD_DOT_PASSWORD)

    if retry_count < 3:
        response = requests.get(api_call, params=params, auth=credentials)
        print(f"path={path}, params={params}, response.status_code={response.status_code}")
        if (
            response.status_code >= 200
            and response.status_code < 300
            and "application/json" in response.headers["content-type"]
        ):
            return response.json()
        else:
            print(response.text)
            time.sleep(30)
            return get_cost_data(path, params, retry_count=retry_count + 1)

    return {}
