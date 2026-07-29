from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
from fastapi import FastAPI

from services.config_service import get_services_config, load_settings
from services.execution_service import ExecutionOptions, get_execution_state, start_execution
from services.report_service import list_reports, summarize_latest
from services.testcase_service import inventory_summary, load_testcase_inventory


app = FastAPI(title="QA Control Center API")


@app.get("/status")
def status() -> dict[str, object]:
    settings = load_settings()
    return {
        "framework_status": "ready",
        "environment": settings.environment,
        "inventory": inventory_summary(),
        "latest": summarize_latest(),
    }


@app.get("/services")
def services() -> dict[str, object]:
    return get_services_config()


@app.get("/testcases")
def testcases() -> list[dict[str, object]]:
    return [record.__dict__ for record in load_testcase_inventory()]


@app.get("/reports")
def reports() -> list[dict[str, object]]:
    return [
        {
            "run_tag": artifact.run_tag,
            "path": str(artifact.path),
            "kind": artifact.kind,
            "modified_at": artifact.modified_at.isoformat(timespec="seconds"),
        }
        for artifact in list_reports()
    ]


@app.post("/execute")
def execute(options: ExecutionOptions) -> dict[str, str]:
    return {"job_id": start_execution(options)}


@app.get("/execute/{job_id}")
def execution_status(job_id: str) -> dict[str, object]:
    state = get_execution_state(job_id)
    return state.__dict__ if state else {"status": "not_found"}
