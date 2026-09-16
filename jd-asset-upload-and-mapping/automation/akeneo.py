import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()


class AkeneoClient:

    def __init__(self):

        self.base_url = os.getenv(
            "AKENEO_BASE_URL",
            "https://gmg.cloud.akeneo.com"
        ).rstrip("/")

        self.job_code = os.getenv(
            "AKENEO_IMPORT_JOB_CODE",
            "columbia_asset_import"
        )

        # Same authentication values used by your working Job 2
        self.basic_auth = os.getenv("AKENEO_BASIC_AUTH")
        self.username = os.getenv("AKENEO_USERNAME")
        self.password = os.getenv("AKENEO_PASSWORD")

        self.poll_interval = int(
            os.getenv("AKENEO_POLL_INTERVAL", "30")
        )

        self.max_wait_seconds = int(
            os.getenv("AKENEO_MAX_WAIT_SECONDS", "14400")
        )

        self.access_token = None
        self.token_created_at = 0

        self.session = requests.Session()

    # =========================================================
    # AUTHENTICATION
    # =========================================================

    def authenticate(self):

        print()
        print("=" * 60)
        print("AUTHENTICATING WITH AKENEO")
        print("=" * 60)

        if not self.basic_auth:
            raise Exception(
                "AKENEO_BASIC_AUTH is not configured"
            )

        if not self.username:
            raise Exception(
                "AKENEO_USERNAME is not configured"
            )

        if not self.password:
            raise Exception(
                "AKENEO_PASSWORD is not configured"
            )

        url = f"{self.base_url}/api/oauth/v1/token"

        response = self.session.post(
            url,
            json={
                "username": self.username,
                "password": self.password,
                "grant_type": "password",
            },
            headers={
                "Authorization": f"Basic {self.basic_auth}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )

        if response.status_code != 200:

            print(
                f"❌ Authentication failed: "
                f"HTTP {response.status_code}"
            )

            print(f"Response: {response.text}")

            raise Exception(
                "Akeneo authentication failed.\n"
                f"HTTP {response.status_code}\n"
                f"{response.text}"
            )

        data = response.json()

        self.access_token = data["access_token"]

        print("✅ Akeneo authentication successful")

        return data

    # =========================================================
    # TOKEN
    # =========================================================

    def get_headers(self):

        if not self.access_token:
            self.authenticate()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # =========================================================
    # TRIGGER IMPORT
    # =========================================================

    def trigger_import(self):

        if not self.access_token:
            self.authenticate()

        print()
        print("=" * 60)
        print("TRIGGERING AKENEO IMPORT")
        print("=" * 60)

        print(f"Job code: {self.job_code}")

        url = (
            f"{self.base_url}"
            f"/api/rest/v1/jobs/import/"
            f"{self.job_code}"
        )

        response = self.session.post(
            url,
            headers=self.get_headers(),
            json={},
            timeout=60,
        )

        print(f"HTTP Status: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 401:

            print("🔄 Access token expired. Re-authenticating...")

            self.authenticate()

            response = self.session.post(
                url,
                headers=self.get_headers(),
                json={},
                timeout=60,
            )

        if response.status_code != 200:

            raise Exception(
                "Failed to trigger Akeneo import.\n"
                f"HTTP {response.status_code}\n"
                f"{response.text}"
            )

        data = response.json()

        execution_id = data.get("job_execution_id")

        if not execution_id:

            raise Exception(
                "Akeneo accepted the import request but "
                "did not return job_execution_id.\n"
                f"Response: {data}"
            )

        print()
        print("✅ AKENEO IMPORT TRIGGERED")
        print(f"Job code     : {self.job_code}")
        print(f"Execution ID : {execution_id}")

        return execution_id

    # =========================================================
    # GET JOB STATUS
    # =========================================================

    def get_job_status(self, execution_id):

        url = (
            f"{self.base_url}"
            f"/api/rest/v1/jobs/{execution_id}"
        )

        response = self.session.get(
            url,
            headers=self.get_headers(),
            timeout=60,
        )

        if response.status_code == 401:

            print("🔄 Access token expired. Re-authenticating...")

            self.authenticate()

            response = self.session.get(
                url,
                headers=self.get_headers(),
                timeout=60,
            )

        if response.status_code != 200:

            raise Exception(
                "Failed to get Akeneo job status.\n"
                f"HTTP {response.status_code}\n"
                f"{response.text}"
            )

        return response.json()

    # =========================================================
    # WAIT FOR COMPLETION
    # =========================================================

    def wait_for_completion(self, execution_id):

        print()
        print("=" * 60)
        print("WAITING FOR AKENEO IMPORT")
        print("=" * 60)

        print(f"Execution ID : {execution_id}")
        print(
            f"Poll interval: {self.poll_interval} seconds"
        )

        start_time = time.time()

        while True:

            elapsed = int(time.time() - start_time)

            if elapsed >= self.max_wait_seconds:

                raise Exception(
                    "Akeneo import timed out.\n"
                    f"Execution ID: {execution_id}\n"
                    f"Waited: {elapsed} seconds"
                )

            status_data = self.get_job_status(
                execution_id
            )

            status = (
                status_data.get("status")
                or status_data.get("job", {}).get("status")
                or ""
            ).lower()

            print(
                f"⏳ Akeneo status: "
                f"{status or 'unknown'} "
                f"({elapsed}s)"
            )

            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------

            if status in (
                "completed",
                "complete",
                "finished",
                "success",
                "successful",
            ):

                print()
                print("=" * 60)
                print("✅ AKENEO IMPORT COMPLETED")
                print("=" * 60)

                print(f"Execution ID: {execution_id}")

                return status_data

            # -------------------------------------------------
            # FAILURE
            # -------------------------------------------------

            if status in (
                "failed",
                "failure",
                "aborted",
                "error",
            ):

                raise Exception(
                    "❌ Akeneo import failed.\n"
                    f"Execution ID: {execution_id}\n"
                    f"Status: {status}\n"
                    f"Details: {status_data}"
                )

            time.sleep(self.poll_interval)