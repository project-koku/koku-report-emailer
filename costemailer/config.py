"""Configuration loader for application."""
import json
import logging
import os


LOG = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods,simplifiable-if-expression
class Config:
    """Configuration for app."""

    CLOUD_DOT_USERNAME = os.getenv("CLOUD_DOT_USERNAME")
    CLOUD_DOT_PASSWORD = os.getenv("CLOUD_DOT_PASSWORD")
    COST_MGMT_RECIPIENTS_JSON = os.getenv("COST_MGMT_RECIPIENTS_JSON", "{}")

    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    try:
        COST_MGMT_RECIPIENTS_JSON = json.loads(COST_MGMT_RECIPIENTS_JSON)
    except Exception as err:
        LOG.error("Failed to parse COST_MGMT_RECIPIENTS_JSON", err)

    if CLOUD_DOT_USERNAME is None or CLOUD_DOT_PASSWORD is None:
        LOG.warning(
            "You must provide environment variables CLOUD_DOT_USERNAME"
            " and CLOUD_DOT_PASSWORD to execute the program."
        )
