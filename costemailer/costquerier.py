import requests

from .config import Config

CLOUD_DOT_API_ROOT = "https://cloud.redhat.com"
COST_MGMT_API_PREFIX = "/api/cost-management/v1/"


AWS_COST_ENDPONT = "reports/aws/costs/"


def get_cost_data(path="status/", params={}):
    """Obtain the response cost data."""
    api_call = CLOUD_DOT_API_ROOT + COST_MGMT_API_PREFIX + path
    credentials = (Config.CLOUD_DOT_USERNAME, Config.CLOUD_DOT_PASSWORD)
    response = requests.get(api_call, params=params, auth=credentials)

    if (
        response.status_code >= 200
        and response.status_code < 300
        and "application/json" in response.headers["content-type"]
    ):
        return response.json()

    return {}
