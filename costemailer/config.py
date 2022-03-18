"""Configuration loader for application."""
import json
import logging
import os

import yaml


LOG = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods,simplifiable-if-expression
class Config:
    """Configuration for app."""

    CLOUD_DOT_USERNAME = os.getenv("CLOUD_DOT_USERNAME")
    CLOUD_DOT_PASSWORD = os.getenv("CLOUD_DOT_PASSWORD")
    CLOUD_DOT_API_ROOT = os.getenv("CLOUD_DOT_API_ROOT", "https://cloud.redhat.com/api/")

    COST_MGMT_RECIPIENTS = {}
    COST_MGMT_RECIPIENTS_FILE = os.getenv("COST_MGMT_RECIPIENTS_FILE", "/data/config.yaml")
    COST_MGMT_API_PREFIX = os.getenv("COST_MGMT_API_PREFIX", "cost-management/v1/")

    RBAC_API_PREFIX = os.getenv("RBAC_API_PREFIX", "rbac/v1/")

    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    if os.path.exists(COST_MGMT_RECIPIENTS_FILE):
        with open(COST_MGMT_RECIPIENTS_FILE, "r") as stream:
            try:
                COST_MGMT_RECIPIENTS = yaml.safe_load(stream)
            except yaml.YAMLError as error:
                LOG.error(error)

    if COST_MGMT_RECIPIENTS == {}:
        COST_MGMT_RECIPIENTS = os.getenv("COST_MGMT_RECIPIENTS", "{}")
        try:
            COST_MGMT_RECIPIENTS = json.loads(COST_MGMT_RECIPIENTS)
        except Exception as err:
            LOG.error("Failed to parse COST_MGMT_RECIPIENTS", err)
            exit(-1)

    if CLOUD_DOT_USERNAME is None or CLOUD_DOT_PASSWORD is None:
        LOG.warning(
            "You must provide environment variables CLOUD_DOT_USERNAME"
            " and CLOUD_DOT_PASSWORD to execute the program."
        )
