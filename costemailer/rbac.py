import requests

from .config import Config


USER_ENDPONT = "principals/"
ACCESS_ENDPOINT = "access/"

AWS_ACCOUNT_ACCESS = "cost-management:aws.account:read"


def get_rbac_data(path="status/", params={}):
    """Obtain the response rbac data."""
    api_call = Config.CLOUD_DOT_API_ROOT + Config.RBAC_API_PREFIX + path
    credentials = (Config.CLOUD_DOT_USERNAME, Config.CLOUD_DOT_PASSWORD)
    response = requests.get(api_call, params=params, auth=credentials)

    if (
        response.status_code >= 200
        and response.status_code < 300
        and "application/json" in response.headers["content-type"]
    ):
        return response.json()

    return {}


def get_users():
    """Obtain users in account"""
    response = get_rbac_data(path=USER_ENDPONT, params={"limit": "100"})
    return response.get("data", [])


def _get_access(username):
    """Obtain user access."""
    response = get_rbac_data(
        path=ACCESS_ENDPOINT, params={"limit": "100", "application": "cost-management", "username": username}
    )
    return response.get("data", [])


def get_access(username, permission):
    """Obtain user access for a specific permision"""
    resources = []
    all_access = _get_access(username)
    for access in all_access:
        if access.get("permission") == permission:
            resource_defs = access.get("resourceDefinitions", [])
            for definition in resource_defs:
                def_value = definition.get("attributeFilter", {}).get("value")
                def_operation = definition.get("attributeFilter", {}).get("operation")
                if def_operation == "in":
                    resources = resources + def_value.split(",")
                elif def_operation == "equal":
                    resources.append(def_value)
    return resources
