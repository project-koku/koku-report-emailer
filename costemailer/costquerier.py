import requests

from .config import Config


AWS_COST_ENDPONT = "reports/aws/costs/"
CURRENT_MONTH_PARAMS = {
    "filter[time_scope_units]": "month",
    "filter[resolution]": "daily",
    "filter[time_scope_value]": "-1",
    "delta": "cost",
}


def get_cost_data(path="status/", params={}):
    """Obtain the response cost data."""
    api_call = Config.CLOUD_DOT_API_ROOT + Config.COST_MGMT_API_PREFIX + path
    credentials = (Config.CLOUD_DOT_USERNAME, Config.CLOUD_DOT_PASSWORD)
    response = requests.get(api_call, params=params, auth=credentials)

    if (
        response.status_code >= 200
        and response.status_code < 300
        and "application/json" in response.headers["content-type"]
    ):
        return response.json()

    return {}
