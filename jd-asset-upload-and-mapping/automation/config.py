import os
from dotenv import load_dotenv


load_dotenv()


# ---------------------------------------------------------
# Jira configuration
# ---------------------------------------------------------

JIRA_URL = os.getenv(
    "JIRA_URL",
    ""
).rstrip("/")

JIRA_EMAIL = os.getenv(
    "JIRA_EMAIL"
)

JIRA_API_TOKEN = os.getenv(
    "JIRA_API_TOKEN"
)


# ---------------------------------------------------------
# Automation trigger configuration
# ---------------------------------------------------------

JIRA_PROJECT = os.getenv(
    "JIRA_PROJECT",
    "ECPS"
)

JIRA_TRIGGER_LABEL = os.getenv(
    "JIRA_TRIGGER_LABEL",
    "jira-automation"
)

JIRA_TRIGGER_STATUS = os.getenv(
    "JIRA_TRIGGER_STATUS",
    "In Progress"
)


# ---------------------------------------------------------
# File configuration
# ---------------------------------------------------------

INPUT_DIR = "input"

INPUT_XLSX = (
    f"{INPUT_DIR}/images.xlsx"
)

AWS_ACCESS_KEY_ID = os.getenv(
    "AWS_ACCESS_KEY_ID"
)

AWS_SECRET_ACCESS_KEY = os.getenv(
    "AWS_SECRET_ACCESS_KEY"
)

S3_BUCKET = "omniversemedia"

S3_PREFIX = "akeneo-sftp"