import base64

import requests

from .config import Config


USER_ENDPONT = "principals/"
ACCESS_ENDPOINT = "access/"

AWS_ACCOUNT_ACCESS = "cost-management:aws.account:read"
AWS_ORG_ACCESS = "cost-management:aws.organizational_unit:read"
OPENSHIFT_CLUSTER_ACCESS = "cost-management:openshift.cluster:read"
OPENSHIFT_PROJECT_ACCESS = "cost-management:openshift.project:read"
AZURE_SUBSCRIPTION_ID_ACCESS = "cost-management:azure.subscription_guid:read"
GCP_ACCOUNT_ACCESS = "cost-management:gcp.account:read"


def get_service_account_token():
    payload = {
        "client_id": Config.CLOUD_DOT_SERVICE_ACCOUNT_ID,
        "client_secret": Config.CLOUD_DOT_SERVICE_ACCOUNT_SECRET,
        "grant_type": "client_credentials",
        "scope": "api.console api.iam.service_accounts",
    }
    response = requests.post(Config.CLOUD_DOT_SERVICE_ACCOUNT_URL, data=payload)
    response_json = response.json()
    return response_json.get("access_token")


def get_rbac_credential_header():
    if Config.CLOUD_DOT_USERNAME and Config.CLOUD_DOT_PASSWORD:
        cred = f"{Config.CLOUD_DOT_USERNAME}:{Config.CLOUD_DOT_PASSWORD}".encode("ascii")
        encoded_cred = base64.b64encode(cred).decode("ascii")
        return {"Authorization": f"Basic {encoded_cred}"}
    if Config.CLOUD_DOT_SERVICE_ACCOUNT_ID and Config.CLOUD_DOT_SERVICE_ACCOUNT_SECRET:
        token = get_service_account_token()
        return {"Authorization": f"Bearer {token}"}
    return {}


def get_rbac_data(path="status/", params={}):
    """Obtain the response rbac data."""
    api_call = Config.CLOUD_DOT_API_ROOT + Config.RBAC_API_PREFIX + path
    headers = get_rbac_credential_header()
    response = requests.get(api_call, params=params, headers=headers)

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
