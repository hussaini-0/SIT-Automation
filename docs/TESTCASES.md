# Testcase Authoring Guide

## Workbook Sources

| Service | File | Sheet |
| --- | --- | --- |
| `cas` | `testcases/sit_testcases.xlsx` | `SIT` |
| `acquiring` | `testcases/sit_testcases_acquiring.xlsx` | `ACQUIRING` |
| `merchant_cas` | `testcases/sit_testcases_merchant_cas.xlsx` | `MERCHANT_CAS` |

## Required Columns

| Column | Meaning |
| --- | --- |
| `TC_ID` | Testcase identifier, usually numeric like `TC001` |
| `Description` | Human-readable testcase purpose |
| `Bank` | Bank key, used by legacy bank URL fallback |
| `API_Name` | API key from `config/apis.yaml` |
| `Request_File` | JSON template filename |
| `Expected_Result` | Expected value used by the selected validation type |
| `Validation_Type` | Validation mode: `response`, `json_field`, or `status_code` |
| `Execute (Y/N)` | Only `Y` rows are executed |

## Optional Columns

| Column | Meaning |
| --- | --- |
| `Service` | Explicit service override |
| `Flow_Config` | Flow key from `config/apis.yaml` |
| `Validation_Rules` | JSON object string with extra validation settings |
| `Test_Type` | Display classification such as `positive` or `negative` |
| `Trx_type` | Transaction category: `financial` or `non-financial`. If blank or missing, CAS `payment`/`directposting` APIs are financial, Merchant CAS APIs are financial except `authenticate`, and other APIs default to non-financial. |

## Validation Types

`response`

Checks whether `Expected_Result` appears in the raw response text or JSON body. If `Expected_Result` contains comma-separated values, all expected values must appear in the collected response values, order independently.

`json_field`

Checks a JSON path against the expected value. Preferred format:

```json
{"field":"response.response_code"}
```

Put that JSON object in the Excel `Validation_Rules` column and the expected value in `Expected_Result`.

Backward-compatible format:

```text
response.response_code:00
```

`status_code`

Compares the HTTP status code with `Expected_Result`, for example `200`.

## Request Templates

Request templates are JSON files under `requests/<service>/`. If the service-scoped file is not found, the runner falls back to `requests/<file>`.

Supported generated tokens:

| Token | Meaning |
| --- | --- |
| `${RRN}` | Unique 12-digit reference number generated only when the template uses it, and persisted in `results/rrn_registry.json` |
| `${DUPLICATE_RRN}` | Reuses the last generated RRN for intentional duplicate-RRN negative cases only |
| `${STAN}` | Random 6-digit trace number |
| `${DATE}` | Current date as `YYYY-MM-DD` |
| `${TIME}` | Current time as `HHMMSS` |
| `${DATETIME}` | Current date and time as `YYYYMMDDHHMMSS` |
| `${RTP_ID_UNIQUE}` | Unique RTP reference suitable for positive merchant RTP payments |
| `${TRANSACTION_ID}` | Usually supplied by a flow/polling step |

Any key from `config/test_data.yaml` is also available as an uppercase token. For example, `sender_iban` can be referenced as `${SENDER_IBAN}`.

Token precedence:

1. Generated defaults from `DataGenerator`.
2. Values from `config/test_data.yaml`.
3. Flow/runtime overrides passed by the runner.

## Creating Chained Testcases

For a chained flow:

1. Define the flow in `config/apis.yaml` under the service.
2. Set `Flow_Config` in Excel to the flow key.
3. Set `API_Name` to the initial API or the flow key, depending on local convention.
4. Set `Request_File` to the initial request template unless the flow overrides it.
5. Add mappings from response JSON paths to token names for the next request.

Chained flows proceed to the next API only when the initial response has `response_code` equal to `00`.

## Creating Polling Testcases

Polling flows require:

- `initial_api`
- `initial_request_file`
- `polling.api`
- Optional `polling.request_file`
- Poll interval and timeout values
- Correlation source and target paths
- `stop_when` condition

Use `json_field` stop conditions when the final status is stored in the response body.
