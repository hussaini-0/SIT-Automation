# SIT Automation Framework

Config-driven API automation framework for SIT testing of banking and payment services.

This project can be used in 3 main ways:

1. Run functional SIT testcases from Excel through `runner.py`
2. Use the Streamlit dashboard to execute, review reports, inspect logs, and launch stress runs
3. Run isolated stress scenarios through the CLI or dashboard

## What This Project Covers

- Excel-driven testcase execution
- Service-aware request templates under `requests/`
- Auth token capture and token routing
- Sequential, parallel, chained, and polling flows
- JSON, CSV, and HTML reports
- Dashboard for execution, reports, logs, settings, Swagger import, and stress testing
- Stress scenarios with separate outputs

## Supported Services

- `cas`
- `acquiring`
- `merchant_cas`
- any additional service workbook/config added in the same project pattern

## Quick Start

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Create local config files

Copy the example configs and fill in your office-specific values:

```powershell
Copy-Item config\servers.example.yaml config\servers.yaml
Copy-Item config\test_data.example.yaml config\test_data.yaml
```

### 3. Run the framework

```powershell
python runner.py
```

### 4. Open the dashboard

```powershell
python -m streamlit run dashboard/app.py
```

## Normal Functional Runs

Run everything enabled:

```powershell
python runner.py
```

Run only one service:

```powershell
python runner.py --service cas
```

Run one API:

```powershell
python runner.py --service cas --api payment
```

Run one testcase:

```powershell
python runner.py --tc TC176
```

Include rows marked `Execute=N`:

```powershell
python runner.py --service merchant_cas --include-disabled
```

Override worker count:

```powershell
python runner.py --workers 8
```

## Stress Runs

Stress mode is separate from functional mode, so `python runner.py` still behaves normally.

Basic stress run:

```powershell
python runner.py --mode stress
```

Run a named scenario:

```powershell
python runner.py --mode stress --stress-scenario safe_read_only
```

Run by fixed iterations:

```powershell
python runner.py --mode stress --stress-scenario safe_read_only --iterations 100
```

Run a payment smoke scenario:

```powershell
python runner.py --mode stress --stress-scenario cas_payment_smoke --workers 2 --duration-seconds 30
```

Important:

- `iterations = 0` means duration-based execution
- stress outputs go to `results/stress/` and `reports/stress/`
- stateful APIs like `payment`, `registerCustomer`, `onestep`, and `registercaa` should be run carefully

### Available Stress Scenarios

Configured in [stress.yaml](C:/Users/TalalHussain/GitProjects/SIT-Automation/config/stress.yaml):

- `safe_read_only`
- `cas_auth_burst`
- `cas_titlefetch_burst`
- `cas_customer_reads`
- `mixed_read_only`
- `acquiring_safe`
- `merchant_cas_safe_read_only`
- `cas_payment_smoke`
- `payment_boundary_subset`
- `register_flows_low_concurrency`

## Dashboard Pages

The dashboard includes:

- `Home`: high-level project and execution summary
- `Execute`: run selected functional testcases in the background
- `Stress`: launch and review stress runs
- `Reports`: inspect functional reports and result JSON files
- `Logs`: browse framework/request/response/validation/error logs
- `Swagger Import`: import or refresh API template definitions
- `Settings`: adjust dashboard defaults

## Outputs

### Functional outputs

- `results/results_<timestamp>.json`
- `results/results_<timestamp>.csv`
- `reports/report_<timestamp>.html`

### Stress outputs

- `results/stress/stress_results_<timestamp>.json`
- `results/stress/stress_results_<timestamp>.csv`
- `reports/stress/stress_report_<timestamp>.html`

### Logs

- `logs/framework.log`
- `logs/request.log`
- `logs/response.log`
- `logs/validation.log`
- `logs/error.log`

## Core Files

- [runner.py](C:/Users/TalalHussain/GitProjects/SIT-Automation/runner.py): main execution entry point
- [apis.yaml](C:/Users/TalalHussain/GitProjects/SIT-Automation/config/apis.yaml): API definitions, token routing, flows, defaults
- [servers.example.yaml](C:/Users/TalalHussain/GitProjects/SIT-Automation/config/servers.example.yaml): shareable template for service URLs and bank-specific overrides
- [test_data.example.yaml](C:/Users/TalalHussain/GitProjects/SIT-Automation/config/test_data.example.yaml): shareable template for runtime tokens and fallback account pool
- [stress.yaml](C:/Users/TalalHussain/GitProjects/SIT-Automation/config/stress.yaml): stress presets
- [sit_testcases.xlsx](C:/Users/TalalHussain/GitProjects/SIT-Automation/testcases/sit_testcases.xlsx): main CAS testcase workbook
- [response_validator.py](C:/Users/TalalHussain/GitProjects/SIT-Automation/validators/response_validator.py): response validation logic

## How Testcases Work

Each Excel row typically provides:

- `TC_ID`
- `API_Name`
- `Description`
- `Request_File`
- `Expected_Result`
- `Validation_Type`
- `Validation_Rules`
- `Execute (Y/N)`
- `Test_Type`
- `Trx_type`
- `Bank`

Request payloads are loaded from JSON files under `requests/<service>/` and placeholders like `${RRN}` or `${SENDER_IBAN}` are filled at runtime.

## Validation Modes

The framework supports:

- `response`: expected text should appear in the response body/text
- `json_field`: compare a JSON field value using `Validation_Rules`
- `status_code`: compare the HTTP status code

Recommended:

- use `json_field` for stable things like `response.response_code`
- use `response` for human-readable messages only when needed
- avoid overfitting negative testcases to brittle full-sentence wording unless the exact message matters

## Recent Quality Improvements

The framework now includes:

- account fallback retries for positive closed/inactive-account cases
- report viewing fixed in the dashboard
- stress mode and stress dashboard support
- validator alias handling for common API wording drift
- outcome labels in reports:
  - `Positive Pass`
  - `Expected Negative`
  - `Regression`
  - `Negative Mismatch`
- a validation drift audit script:

```powershell
python scripts/audit_validation_drift.py
```

This helps identify:

- integer `amount` / `fee` fields in request templates
- stale workbook expectations

## Common Troubleshooting

### Report opens but content looks old

- refresh the dashboard page
- make sure you are opening the latest file under `results/` or `reports/`

### API returns auth errors

- confirm the auth testcase for that service/channel is enabled
- confirm `token_json_path` in `config/apis.yaml` matches the auth response
- confirm `token_routing` is correct for the API

### A testcase fails even though the API response looks correct

- check `Expected_Result` in the workbook
- check `Validation_Type`
- check `Validation_Rules`
- compare the HTML report request/response details

### Decimal/amount parse errors

- inspect the request JSON file
- make sure decimal fields are sent as `0.0`, `5.0`, `10.50`, etc. when that API requires decimals

### Stress run is too risky

- use a read-only scenario first
- keep `allow_stateful_apis` off unless needed
- lower workers and duration for payment or registration flows

## Repository Layout

```text
config/                YAML config for APIs, servers, stress, and shared data
dashboard/             Streamlit QA Control Center
docs/                  Project documentation
generated_testcases/   Generated workbook previews and request files
logs/                  Framework and API logs
reports/               Functional HTML reports
reports/stress/        Stress HTML reports
requests/              JSON request templates grouped by service
results/               Functional JSON/CSV results
results/stress/        Stress JSON/CSV results
scripts/               Helper and audit scripts
services/              Dashboard/backend service layer
testcases/             Excel testcase workbooks
utils/                 Request rendering, stress runner, logging, helpers
validators/            Response validation
runner.py              Main CLI entry point
```

## Useful Commands

Run latest functional flow:

```powershell
python runner.py
```

Run one testcase:

```powershell
python runner.py --tc TC449
```

Run dashboard:

```powershell
python -m streamlit run dashboard/app.py
```

Run stress scenario:

```powershell
python runner.py --mode stress --stress-scenario cas_titlefetch_burst
```

Run validation drift audit:

```powershell
python scripts/audit_validation_drift.py
```

## Documentation

For deeper detail, see:

- [Project Overview](docs/PROJECT_OVERVIEW.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Module Reference](docs/MODULE_REFERENCE.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [Testcase Guide](docs/TESTCASES.md)
- [Execution Guide](docs/EXECUTION.md)
- [Operations Security](docs/OPERATIONS_SECURITY.md)

## Internal Use Note

This repository contains environment-specific URLs, payloads, account data, logs, and reports. Treat it as internal automation code and review sensitive artifacts before sharing them.
