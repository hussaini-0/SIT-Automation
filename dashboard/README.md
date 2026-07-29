# QA Control Center

QA Control Center is a companion application for the existing SIT Automation Framework. It adds a web UI and a thin service layer around the current runner, configuration, Excel workbooks, reports, results, and logs.

It does not replace `runner.py`. The existing CLI remains the source of truth and continues to run with:

```powershell
python runner.py
```

The dashboard runs separately with:

```powershell
python -m streamlit run dashboard/app.py
```

## Boundary

The companion app consumes framework behavior through adapter services:

- `services.execution_service` instantiates `SITRunner`, executes selected `ServiceTestCase` records, and calls the runner's existing report writers.
- `services.testcase_service` reads existing Excel workbooks and maps rows into dashboard inventory records.
- `services.report_service` reads existing `results/`, `reports/`, and `logs/` artifacts.
- `services.swagger_service` imports OpenAPI definitions by appending new APIs/templates/testcases without changing existing formats.
- `services.config_service` reads framework YAML and stores dashboard-only defaults in `config/dashboard_settings.yaml`.

## Ownership Rules

- Keep framework execution logic in `runner.py` and existing utility modules.
- Keep dashboard orchestration, presentation, and background job state in `dashboard/` and `services/`.
- Do not change Excel formats, request template formats, report formats, or log formats for dashboard convenience.
- Prefer new adapter functions over editing framework internals when the dashboard needs another view of existing data.
- Treat writes to framework config or workbooks as explicit user actions from Settings or Swagger Import.

## Optional API

The companion also exposes a small FastAPI surface for integrations:

```powershell
uvicorn dashboard.api:app
```

Streamlit does not require the API server; both entry points consume the same adapter services.
