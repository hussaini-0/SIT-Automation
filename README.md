# SIT Automation Framework

Config-driven Python automation framework for System Integration Testing (SIT) of banking/payment APIs. The framework reads testcases from Excel, renders JSON request templates, calls configured service endpoints, validates responses, and writes JSON, CSV, HTML reports, and rotating logs.

## What This Project Does

- Runs API testcases from Excel files in `testcases/`.
- Supports multiple services: `cas`, `acquiring`, and `merchant_cas`.
- Loads service URLs, enabled flags, API endpoints, auth rules, token routing, and flows from YAML config.
- Renders JSON payload templates from `requests/<service>/` using generated and user-defined tokens.
- Executes auth cases first, independent cases in parallel, and numbered dependent cases sequentially.
- Supports single-step tests, polling flows, and chained success-dependent flows.
- Produces run artifacts in `results/`, `reports/`, and `logs/`.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python runner.py
```

Optional run controls:

```powershell
$env:MAX_WORKERS="8"
$env:ENABLED_SERVICES="cas,merchant_cas"
$env:DISABLED_SERVICES="acquiring"
python runner.py
```

## Current Project State

- Main runner: `runner.py`
- Services configured: `cas`, `acquiring`, `merchant_cas`
- Request templates: service-scoped JSON files under `requests/`
- Main CAS workbook: `testcases/sit_testcases.xlsx`
- Latest execution outputs are written to `results/` and `reports/`
- Slack report watcher: `slack_report_alert.py`

## Documentation

Start here:

- [Project Overview](docs/PROJECT_OVERVIEW.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Module and Script Reference](docs/MODULE_REFERENCE.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [Testcase Authoring Guide](docs/TESTCASES.md)
- [Execution and Reporting](docs/EXECUTION.md)
- [Operations and Security Notes](docs/OPERATIONS_SECURITY.md)

## Repository Layout

```text
config/              YAML configuration for services, APIs, and shared test data
requests/            JSON request templates, grouped by service
testcases/           Excel testcase workbooks
utils/               API client, templating, logging, data generation, service config
validators/          Response validation logic
scripts/             Helper scripts for testcase workbook maintenance
results/             Generated JSON and CSV run outputs
reports/             Generated HTML reports
logs/                Generated framework, request, response, validation, and error logs
runner.py            Main execution entry point
slack_report_alert.py Optional report watcher and Slack notifier
```

## Important Note

This repository contains environment-specific URLs, payloads, and test data. Treat it as internal automation code. Review `docs/OPERATIONS_SECURITY.md` before sharing, committing externally, or running the Slack watcher.
