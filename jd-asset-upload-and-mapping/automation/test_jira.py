import requests
from requests.auth import HTTPBasicAuth

from config import (
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    JIRA_CLOUD_ID
)


def test_jira_connection():

    print("=" * 60)
    print("TESTING JIRA SCOPED TOKEN")
    print("=" * 60)

    url = (
        f"https://api.atlassian.com/ex/jira/"
        f"{JIRA_CLOUD_ID}/rest/api/3/myself"
    )

    response = requests.get(
        url,
        auth=HTTPBasicAuth(
            JIRA_EMAIL,
            JIRA_API_TOKEN
        ),
        headers={
            "Accept": "application/json"
        },
        timeout=30
    )

    print(f"HTTP Status: {response.status_code}")
    print()

    if response.status_code == 200:

        data = response.json()

        print("✅ Jira connection successful!")
        print(f"Account ID : {data.get('accountId')}")
        print(f"Display Name: {data.get('displayName')}")

    else:

        print("❌ Jira connection failed")
        print("Response:")
        print(response.text)

    print("=" * 60)


if __name__ == "__main__":
    test_jira_connection()