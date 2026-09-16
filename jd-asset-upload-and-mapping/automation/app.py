import threading

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jira import JiraClient
from s3 import S3Client
from main import process_ticket

app = FastAPI()


def run_automation(ticket):
    ticket_key = ticket.get("key")

    try:
        print(f"🚀 Starting automation for {ticket_key}")

        jira = JiraClient()
        s3 = S3Client()

        process_ticket(
            jira,
            s3,
            ticket
        )

        print(f"✅ Automation finished for {ticket_key}")

    except Exception as error:
        print(
            f"❌ Automation failed for "
            f"{ticket_key}: {error}"
        )


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "JD Asset Automation"
    }


@app.post("/webhook/jira")
async def jira_webhook(request: Request):
    try:
        payload = await request.json()

        issue = payload.get("issue", {})
        fields = issue.get("fields", {})

        ticket_key = issue.get("key")

        if not ticket_key:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Issue key not found"
                }
            )

        project = fields.get("project", {})
        project_key = project.get("key")

        status = fields.get("status", {})
        status_name = status.get("name", "")

        labels = fields.get("labels", [])

        print(
            f"📥 Jira webhook received: "
            f"{ticket_key} | "
            f"Project: {project_key} | "
            f"Status: {status_name} | "
            f"Labels: {labels}"
        )

        if project_key != "ECPS":
            print(
                f"⏭️ Ignoring {ticket_key}: "
                f"wrong project"
            )

            return {
                "status": "ignored",
                "reason": "wrong project"
            }

        if "jira-automation" not in labels:
            print(
                f"⏭️ Ignoring {ticket_key}: "
                f"automation label missing"
            )

            return {
                "status": "ignored",
                "reason": "automation label missing"
            }

        if status_name.lower() != "in progress":
            print(
                f"⏭️ Ignoring {ticket_key}: "
                f"status is '{status_name}'"
            )

            return {
                "status": "ignored",
                "reason": "ticket is not In Progress"
            }

        print(
            f"✅ Valid automation ticket: "
            f"{ticket_key}"
        )

        thread = threading.Thread(
            target=run_automation,
            args=(issue,),
            daemon=True
        )

        thread.start()

        return {
            "status": "accepted",
            "ticket": ticket_key
        }

    except Exception as error:
        print(
            f"❌ Webhook processing error: "
            f"{error}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(error)
            }
        )