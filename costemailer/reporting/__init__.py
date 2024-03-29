from costemailer import costquerier


API_ENDPOINTS = {
    "AWS": costquerier.AWS_COST_ENDPOINT,
    "OCP": costquerier.OPENSHIFT_COST_ENDPOINT,
    "AZURE": costquerier.AZURE_COST_ENDPOINT,
    "GCP": costquerier.GCP_COST_ENDPOINT,
}


def get_daily_cost(report_type, params={}, is_org_admin=False):
    api_endpoint = API_ENDPOINTS.get(report_type)
    daily_params = costquerier.CURRENT_COST_MONTH_PARAMS.copy()
    daily_params["filter[resolution]"] = "daily"
    if not is_org_admin:
        daily_params.update(params)

    return costquerier.get_cost_data(path=api_endpoint, params=daily_params)


def get_monthly_cost(report_type, params={}, is_org_admin=False):
    api_endpoint = API_ENDPOINTS.get(report_type)
    monthly_params = costquerier.CURRENT_COST_MONTH_PARAMS.copy()
    monthly_params["filter[resolution]"] = "monthly"
    monthly_params.update(params)
    # if not is_org_admin:
    #     monthly_params.update(params)

    return costquerier.get_cost_data(path=api_endpoint, params=monthly_params)


def get_recommendations(report_type, params, is_org_admin=False):
    if report_type != "OCP":
        return {}
    api_endpoint = costquerier.OPENSHIFT_RECOMMENDATIONS_ENDPOINT
    rec_params = costquerier.RECOMMENDATION_PARAMS.copy()
    rec_params.update(params)

    return costquerier.get_cost_data(path=api_endpoint, params=rec_params)
