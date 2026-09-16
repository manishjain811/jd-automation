import subprocess
import sys
import traceback
from pathlib import Path

from jira import JiraClient
from s3 import S3Client
from akeneo import AkeneoClient


JOB_1 = "run_columbia_asset_pipeline.py"
ASSET_LABEL_JOB = "update-asset-labels-columbia.py"
TARGET_STATUS = "Development Completed"
CSV_FILE = "generated/asset_import.csv"


def run_python_job(script_name, job_description):
    print()
    print("=" * 60)
    print(f"RUNNING: {job_description}")
    print("=" * 60)
    print(f"Script: {script_name}")

    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            script_name
        ],
        text=True
    )

    if result.returncode != 0:
        raise Exception(
            f"{job_description} failed.\n"
            f"Exit code: {result.returncode}"
        )

    print()
    print(f"✅ {job_description} completed")

    return True


def process_ticket(jira, s3, ticket):
    ticket_key = ticket.get("key")

    summary = (
        ticket
        .get("fields", {})
        .get("summary", "")
    )

    print()
    print()
    print("#" * 70)
    print(
        f"PROCESSING JIRA TICKET: "
        f"{ticket_key}"
    )
    print("#" * 70)

    print(
        f"Summary: {summary}"
    )

    failed_step = "Unknown"

    try:
        # STEP 1 - DOWNLOAD + PREPARE EXCEL

        failed_step = (
            "Download and prepare Excel"
        )

        print()
        print("=" * 60)
        print(
            "STEP 1: DOWNLOAD EXCEL FROM JIRA"
        )
        print("=" * 60)

        excel_file = (
            jira.download_excel_from_ticket(
                ticket_key
            )
        )

        print()
        print(
            f"Excel ready: {excel_file}"
        )

        # STEP 2 - RUN JOB 1

        failed_step = (
            "Run Columbia asset pipeline"
        )

        run_python_job(
            JOB_1,
            "Columbia asset pipeline"
        )

        # STEP 3 - VERIFY CSV

        failed_step = (
            "Verify generated CSV"
        )

        csv_path = Path(
            CSV_FILE
        )

        if not csv_path.exists():
            raise Exception(
                f"Expected CSV was not generated: "
                f"{CSV_FILE}"
            )

        print()
        print(
            f"✅ CSV generated: {CSV_FILE}"
        )

        # STEP 4 - UPLOAD CSV TO S3

        failed_step = (
            "Upload CSV to S3"
        )

        s3_url = s3.upload_file(
            CSV_FILE
        )

        print()
        print(
            "✅ S3 upload successful"
        )

        print(
            f"S3 URL: {s3_url}"
        )

        # STEP 5 - AKENEO IMPORT

        failed_step = (
            "Run Akeneo import"
        )

        print()
        print("=" * 60)
        print(
            "STEP 5: AKENEO IMPORT"
        )
        print("=" * 60)

        akeneo = AkeneoClient()

        execution_id = (
            akeneo.trigger_import()
        )

        print()
        print(
            f"Akeneo execution ID: "
            f"{execution_id}"
        )

        akeneo.wait_for_completion(
            execution_id
        )

        print()
        print(
            "✅ Akeneo import completed"
        )

        # STEP 6 - UPDATE ASSET LABELS

        failed_step = (
            "Run asset label update"
        )

        run_python_job(
            ASSET_LABEL_JOB,
            "Asset label update"
        )

        # STEP 7 - ADD JIRA SUCCESS COMMENT

        failed_step = (
            "Add Jira success comment"
        )

        success_comment = (
            "Automation completed successfully.\n\n"
            "Excel: downloaded and processed\n"
            "Job 1: completed\n"
            f"CSV: {CSV_FILE}\n"
            "S3: uploaded successfully\n"
            f"S3 URL: {s3_url}\n"
            "Akeneo: import completed\n"
            "Asset label update: completed"
        )

        jira.add_comment(
            ticket_key,
            success_comment
        )

        # STEP 8 - MOVE JIRA TICKET

        failed_step = (
            "Move Jira ticket to "
            "Development Completed"
        )

        jira.transition_ticket(
            ticket_key,
            TARGET_STATUS
        )

        print()
        print("#" * 70)
        print(
            f"✅ TICKET COMPLETED: "
            f"{ticket_key}"
        )
        print(
            f"✅ STATUS: "
            f"{TARGET_STATUS}"
        )
        print("#" * 70)

        return True

    except Exception as error:
        print()
        print("#" * 70)
        print(
            f"❌ TICKET FAILED: "
            f"{ticket_key}"
        )
        print("#" * 70)

        print()
        print(
            f"Failed step: {failed_step}"
        )

        print(
            f"Error: {error}"
        )

        try:
            failure_comment = (
                "Automation failed.\n\n"
                f"Failed step: {failed_step}\n"
                f"Error: {error}\n\n"
                "Please review the automation logs "
                "for details."
            )

            jira.add_comment(
                ticket_key,
                failure_comment
            )

        except Exception as comment_error:
            print()
            print(
                "⚠️ Failed to add Jira failure comment:"
            )

            print(
                comment_error
            )

        print()
        print(
            "⚠️ Jira ticket will remain in its "
            "current status."
        )

        return False


def main():
    print()
    print("=" * 70)
    print(
        "JIRA ASSET AUTOMATION"
    )
    print("=" * 70)

    jira = None
    s3 = None

    try:
        # INITIALIZE JIRA

        print()
        print(
            "Initializing Jira client..."
        )

        jira = JiraClient()

        print(
            "✅ Jira client initialized"
        )

        # INITIALIZE S3

        print()
        print(
            "Initializing S3 client..."
        )

        s3 = S3Client()

        print(
            "✅ S3 client initialized"
        )

        # FIND ELIGIBLE JIRA TICKETS

        print()
        print(
            "Checking Jira for automation tickets..."
        )

        tickets = (
            jira.find_automation_tickets()
        )

        print()
        print(
            f"Found {len(tickets)} "
            f"automation ticket(s)"
        )

        if not tickets:
            print()
            print(
                "No tickets to process."
            )

            return

        # PROCESS TICKETS

        successful = 0
        failed = 0

        for ticket in tickets:

            result = process_ticket(
                jira,
                s3,
                ticket
            )

            if result:
                successful += 1
            else:
                failed += 1

        # FINAL SUMMARY

        print()
        print()
        print("=" * 70)
        print(
            "AUTOMATION SUMMARY"
        )
        print("=" * 70)

        print(
            f"Total tickets : {len(tickets)}"
        )

        print(
            f"Successful    : {successful}"
        )

        print(
            f"Failed        : {failed}"
        )

        print()

    except Exception as error:
        print()
        print("=" * 70)
        print(
            "❌ AUTOMATION ERROR"
        )
        print("=" * 70)

        print(
            error
        )

        print()
        traceback.print_exc()

        sys.exit(1)


if __name__ == "__main__":
    main()