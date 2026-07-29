# Testcase Generation

This project now includes a spec-driven generator for creating positive and negative testcase variants without changing the live workbooks by default.

## What It Generates

The generator creates:

- JSON request files under `generated_testcases/requests/<service>/`
- preview workbooks under `generated_testcases/workbooks/`

This keeps generation safe for review before anything is appended to the real Excel files.

## Command

```powershell
python scripts/generate_testcases.py
```

Optional append mode:

```powershell
python scripts/generate_testcases.py --append-workbook
```

Use append mode only after reviewing the generated request files and preview workbook.

## Spec File

Default spec:

`config/testcase_generation.yaml`

Each suite defines:

- `service`
- `api_name`
- `bank`
- `base_request_file`
- `workbook`
- `sheet`
- `start_id`
- default validation values
- optional `test_data_bindings`
- a list of `variants`

`test_data_bindings` maps JSON paths in the generated request to keys from `config/test_data.yaml`.
That means generated request files keep placeholders like `${SENDER_IBAN}` instead of hardcoded live values.

## Variant Mutations

Supported mutation operations:

- `set`
- `remove`

Examples:

```yaml
mutations:
  - op: set
    path: amount
    value: -1
```

```yaml
mutations:
  - op: remove
    path: receiver_iban
```

You can also force a mutation to use a value from `config/test_data.yaml`:

```yaml
test_data_bindings:
  sender_iban: sender_iban
  sender_idvalue: CNIC
```

## Recommended Workflow

1. Add or update a suite in `config/testcase_generation.yaml`
2. Run the generator
3. Review generated JSON payloads
4. Review the preview workbook
5. Adjust expected results and validation rules if needed
6. Append to the real workbook only when the generated cases look correct

## How To Scale Toward 1000 Testcases

Use one suite per API or flow and add reusable negative patterns:

- missing field
- empty field
- invalid format
- invalid enum
- invalid amount
- invalid participant
- duplicate RRN
- auth failures
- boundary values

With 10 to 15 structured variants per API, this project can grow toward 1000 useful testcases without manual row-by-row authoring.
