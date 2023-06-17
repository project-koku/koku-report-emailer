import requests

from .config import Config


USER_ENDPONT = "principals/"
ACCESS_ENDPOINT = "access/"

AWS_ACCOUNT_ACCESS = "cost-management:aws.account:read"
AWS_ORG_ACCESS = "cost-management:aws.organizational_unit:read"
OPENSHIFT_CLUSTER_ACCESS = "cost-management:openshift.cluster:read"
OPENSHIFT_PROJECT_ACCESS = "cost-management:openshift.project:read"
AZURE_SUBSCRIPTION_ID_ACCESS = "cost-management:azure.subscription_guid:read"


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


def get_access(username, permissions):
    """Obtain user access for a specific permision"""
    resources = {}
    for perm in permissions:
        resources[perm] = []
    all_access = _get_access(username)
    for access in all_access:
        access_perm = access.get("permission")
        if access_perm in permissions:
            resource_defs = access.get("resourceDefinitions", [])
            for definition in resource_defs:
                def_value = definition.get("attributeFilter", {}).get("value")
                def_operation = definition.get("attributeFilter", {}).get("operation")
                if def_operation == "in":
                    resources[access_perm] = resources[access_perm] + def_value
                elif def_operation == "equal":
                    resources[access_perm].append(def_value)
    return resources
