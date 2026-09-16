from pathlib import Path

import pandas as pd
import requests

from requests.auth import HTTPBasicAuth

from config import (
    JIRA_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    JIRA_PROJECT,
    JIRA_TRIGGER_LABEL,
    JIRA_TRIGGER_STATUS,
    INPUT_XLSX,
)


class JiraClient:

    def __init__(self):

        # -------------------------------------------------
        # Validate configuration
        # -------------------------------------------------

        if not JIRA_URL:
            raise Exception(
                "JIRA_URL is not configured"
            )

        if not JIRA_EMAIL:
            raise Exception(
                "JIRA_EMAIL is not configured"
            )

        if not JIRA_API_TOKEN:
            raise Exception(
                "JIRA_API_TOKEN is not configured"
            )

        self.base_url = JIRA_URL

        # -------------------------------------------------
        # Create HTTP session
        # -------------------------------------------------

        self.session = requests.Session()

        self.session.auth = HTTPBasicAuth(
            JIRA_EMAIL,
            JIRA_API_TOKEN
        )

        self.session.headers.update({
            "Accept": "application/json"
        })

    # =====================================================
    # FIND AUTOMATION TICKETS
    # =====================================================

    def find_automation_tickets(self):

        jql = (
            f'project = "{JIRA_PROJECT}" '
            f'AND status = "{JIRA_TRIGGER_STATUS}" '
            f'AND labels = "{JIRA_TRIGGER_LABEL}" '
            f'ORDER BY created ASC'
        )

        url = (
            f"{self.base_url}"
            f"/rest/api/3/search/jql"
        )

        print()
        print("=" * 60)
        print("JIRA AUTOMATION CHECK")
        print("=" * 60)

        print()
        print("Searching for:")
        print(f"Project : {JIRA_PROJECT}")
        print(f"Status  : {JIRA_TRIGGER_STATUS}")
        print(f"Label   : {JIRA_TRIGGER_LABEL}")
        print()

        response = self.session.get(
            url,
            params={
                "jql": jql,
                "maxResults": 50,
                "fields": (
                    "summary,"
                    "status,"
                    "labels,"
                    "issuetype,"
                    "created,"
                    "attachment"
                )
            },
            timeout=30
        )

        if response.status_code != 200:

            raise Exception(
                "Failed to search Jira.\n"
                f"HTTP Status: "
                f"{response.status_code}\n"
                f"Response: "
                f"{response.text}"
            )

        data = response.json()

        return data.get(
            "issues",
            []
        )

    # =====================================================
    # GET SINGLE ISSUE
    # =====================================================

    def get_issue(
        self,
        ticket_key
    ):

        url = (
            f"{self.base_url}"
            f"/rest/api/3/issue/"
            f"{ticket_key}"
        )

        response = self.session.get(
            url,
            params={
                "fields": (
                    "summary,"
                    "status,"
                    "labels,"
                    "attachment"
                )
            },
            timeout=30
        )

        if response.status_code != 200:

            raise Exception(
                f"Failed to get Jira ticket "
                f"{ticket_key}.\n"
                f"HTTP Status: "
                f"{response.status_code}\n"
                f"Response: "
                f"{response.text}"
            )

        return response.json()

    # =====================================================
    # FIND EXCEL ATTACHMENT
    # =====================================================

    def find_excel_attachment(
        self,
        ticket_key
    ):

        issue = self.get_issue(
            ticket_key
        )

        fields = issue.get(
            "fields",
            {}
        )

        attachments = fields.get(
            "attachment",
            []
        )

        if not attachments:

            raise Exception(
                f"No attachments found on "
                f"{ticket_key}"
            )

        print()
        print(
            f"📎 Attachments on "
            f"{ticket_key}:"
        )
        print()

        excel_files = []

        for attachment in attachments:

            filename = attachment.get(
                "filename",
                ""
            )

            created = attachment.get(
                "created",
                ""
            )

            print(
                f"   - {filename}"
            )

            if filename.lower().endswith(
                (".xlsx", ".xls")
            ):

                excel_files.append(
                    attachment
                )

        if not excel_files:

            raise Exception(
                f"No Excel attachment found "
                f"on {ticket_key}"
            )

        # -------------------------------------------------
        # If multiple Excel files exist,
        # use the most recently uploaded one.
        # -------------------------------------------------

        excel_files.sort(
            key=lambda x: x.get(
                "created",
                ""
            ),
            reverse=True
        )

        selected = excel_files[0]

        print()
        print(
            f"✅ Selected Excel: "
            f"{selected['filename']}"
        )

        return selected

    # =====================================================
    # DOWNLOAD EXCEL
    # =====================================================

    def download_attachment(
        self,
        attachment
    ):

        attachment_id = attachment[
            "id"
        ]

        original_filename = attachment[
            "filename"
        ]

        # -------------------------------------------------
        # Always use the filename expected by Job 1
        # -------------------------------------------------

        file_path = Path(
            INPUT_XLSX
        )

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # -------------------------------------------------
        # Remove previous images.xlsx
        # -------------------------------------------------

        if file_path.exists():

            print()
            print(
                f"🗑 Removing previous file: "
                f"{file_path}"
            )

            file_path.unlink()

        # -------------------------------------------------
        # Jira attachment URL
        # -------------------------------------------------

        url = (
            f"{self.base_url}"
            f"/rest/api/3/attachment/content/"
            f"{attachment_id}"
        )

        print()
        print(
            f"⬇️ Downloading attachment:"
        )

        print(
            f"   {original_filename}"
        )

        response = self.session.get(
            url,
            timeout=120,
            stream=True
        )

        if response.status_code != 200:

            raise Exception(
                "Failed to download "
                "Jira attachment.\n"
                f"HTTP Status: "
                f"{response.status_code}\n"
                f"Response: "
                f"{response.text}"
            )

        # -------------------------------------------------
        # Save as images.xlsx
        # -------------------------------------------------

        with open(
            file_path,
            "wb"
        ) as file:

            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):

                if chunk:
                    file.write(chunk)

        print()
        print(
            f"✅ Downloaded successfully"
        )

        print(
            f"📄 Saved as: {file_path}"
        )

        return str(file_path)

    # =====================================================
    # PREPARE EXCEL FOR JOB 1
    # =====================================================

    def prepare_excel(
        self,
        file_path
    ):

        print()
        print("=" * 60)
        print("PREPARING EXCEL FOR JOB 1")
        print("=" * 60)

        # -------------------------------------------------
        # Read Excel
        # -------------------------------------------------

        try:

            df = pd.read_excel(
                file_path
            )

        except Exception as e:

            raise Exception(
                f"Failed to read Excel file: "
                f"{e}"
            )

        print()
        print("Original columns:")

        for column in df.columns:

            print(
                f"   - {column}"
            )

        # -------------------------------------------------
        # Clean column names
        # -------------------------------------------------

        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )

        # -------------------------------------------------
        # Rename columns
        # -------------------------------------------------

        df = df.rename(
            columns={
                "code": "PRODUCT_MODEL",
                "sku": "VARIANT_SKU"
            }
        )

        # -------------------------------------------------
        # Validate required columns
        # -------------------------------------------------

        required_columns = {
            "PRODUCT_MODEL",
            "VARIANT_SKU"
        }

        missing_columns = (
            required_columns
            - set(df.columns)
        )

        if missing_columns:

            raise Exception(
                "Excel is missing required "
                f"columns: "
                f"{', '.join(sorted(missing_columns))}"
            )

        # -------------------------------------------------
        # Remove existing STATUS if present
        # -------------------------------------------------

        if "STATUS" in df.columns:

            df = df.drop(
                columns=["STATUS"]
            )

        # -------------------------------------------------
        # Add STATUS
        # -------------------------------------------------

        df["STATUS"] = ""

        # -------------------------------------------------
        # Keep only required columns
        # -------------------------------------------------

        df = df[
            [
                "PRODUCT_MODEL",
                "VARIANT_SKU",
                "STATUS"
            ]
        ]

        # -------------------------------------------------
        # Save prepared Excel
        # -------------------------------------------------

        df.to_excel(
            file_path,
            index=False
        )

        print()
        print(
            "Final columns:"
        )

        for column in df.columns:

            print(
                f"   - {column}"
            )

        print()
        print(
            f"✅ Excel prepared successfully"
        )

        print(
            f"📄 File: {file_path}"
        )

        print(
            f"📊 Rows: {len(df)}"
        )

        return str(file_path)

    # =====================================================
    # DOWNLOAD + PREPARE EXCEL
    # =====================================================

    def download_excel_from_ticket(
        self,
        ticket_key
    ):

        # Find attachment
        attachment = (
            self.find_excel_attachment(
                ticket_key
            )
        )

        # Download
        file_path = (
            self.download_attachment(
                attachment
            )
        )

        # Prepare
        file_path = (
            self.prepare_excel(
                file_path
            )
        )

        return file_path

    # =====================================================
    # ADD JIRA COMMENT
    # =====================================================

    def add_comment(
        self,
        ticket_key,
        comment
    ):

        print()
        print(
            f"📝 Adding comment to Jira: "
            f"{ticket_key}"
        )

        url = (
            f"{self.base_url}"
            f"/rest/api/3/issue/"
            f"{ticket_key}/comment"
        )

        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": comment
                            }
                        ]
                    }
                ]
            }
        }

        response = self.session.post(
            url,
            json=payload,
            timeout=30
        )

        if response.status_code not in (
            200,
            201
        ):

            raise Exception(
                "Failed to add Jira comment.\n"
                f"HTTP Status: "
                f"{response.status_code}\n"
                f"Response: "
                f"{response.text}"
            )

        print(
            "✅ Jira comment added successfully"
        )

        return response.json()

    # =====================================================
    # TRANSITION JIRA TICKET
    # =====================================================

    def transition_ticket(
        self,
        ticket_key,
        target_status
    ):

        print()
        print("=" * 60)
        print("JIRA TICKET TRANSITION")
        print("=" * 60)

        print(
            f"Ticket        : {ticket_key}"
        )

        print(
            f"Target status : {target_status}"
        )

        url = (
            f"{self.base_url}"
            f"/rest/api/3/issue/"
            f"{ticket_key}/transitions"
        )

        # -------------------------------------------------
        # Get available transitions
        # -------------------------------------------------

        response = self.session.get(
            url,
            timeout=30
        )

        if response.status_code != 200:

            raise Exception(
                "Failed to get Jira transitions.\n"
                f"HTTP Status: "
                f"{response.status_code}\n"
                f"Response: "
                f"{response.text}"
            )

        transitions = response.json().get(
            "transitions",
            []
        )

        # -------------------------------------------------
        # Find transition whose destination
        # status matches target_status
        # -------------------------------------------------

        target_transition = None

        for transition in transitions:

            destination_status = (
                transition
                .get("to", {})
                .get("name", "")
            )

            if (
                destination_status.lower()
                == target_status.lower()
            ):

                target_transition = transition
                break

        if not target_transition:

            available_statuses = [
                transition
                .get("to", {})
                .get("name")
                for transition in transitions
            ]

            raise Exception(
                f"Could not find Jira transition "
                f"to '{target_status}'.\n"
                f"Available statuses: "
                f"{available_statuses}"
            )

        transition_id = (
            target_transition["id"]
        )

        print()
        print(
            f"Transition ID: {transition_id}"
        )

        # -------------------------------------------------
        # Execute transition
        # -------------------------------------------------

        response = self.session.post(
            url,
            json={
                "transition": {
                    "id": transition_id
                }
            },
            timeout=30
        )

        if response.status_code != 204:

            raise Exception(
                "Failed to transition Jira ticket.\n"
                f"HTTP Status: "
                f"{response.status_code}\n"
                f"Response: "
                f"{response.text}"
            )

        print()
        print(
            f"✅ Jira ticket {ticket_key} "
            f"moved to '{target_status}'"
        )

        return True