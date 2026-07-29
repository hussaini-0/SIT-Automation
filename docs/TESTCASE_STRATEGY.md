# Testcase Strategy

This project should grow to at least 1000 useful testcases by expanding coverage systematically, not by adding near-duplicate rows.

## Goal

For each API or flow, track coverage in these buckets:

- `positive`: happy path and valid business variations
- `negative`: invalid input, invalid state, or expected rejection
- `boundary`: min/max/empty/length/format edge cases
- `auth`: missing token, invalid token, expired token, wrong channel
- `duplicate`: duplicate RRN, replay, idempotency, resubmission
- `flow`: polling, chaining, status follow-up, multi-step behavior

## Minimum Coverage Target

Use these starting targets for each API:

| Bucket | Minimum |
| --- | --- |
| Positive | 2 |
| Negative | 6 |
| Boundary | 2 |
| Auth | 2 |
| Duplicate | 1 |
| Flow | 1 when applicable, otherwise 0 |

This gives a practical default target of 12 to 13 testcases for business-critical APIs.

## Negative Test Patterns

Apply these patterns consistently across services where they make sense:

- missing required field
- null field
- empty string
- whitespace-only value
- invalid format
- invalid length
- invalid enum or code
- invalid amount
- invalid account or alias
- invalid participant code
- unauthorized request
- expired token
- duplicate RRN or transaction reference
- invalid business state
- not found
- malformed payload

## Prioritization Order

Build coverage in this order:

1. auth APIs
2. payment and direct posting APIs
3. title fetch and lookup APIs
4. merchant payment APIs
5. transaction-status and inquiry APIs
6. chained flows
7. polling flows

## Working Model

1. Maintain a coverage matrix per service and API.
2. Measure current counts from the existing Excel inventory.
3. Fill the biggest gaps first, especially negative and auth gaps.
4. Generate new rows from reusable patterns instead of writing each row by hand.

## Output Artifacts

Use these artifacts together:

- [TESTCASES.md](/C:/Users/TalalHussain/GitProjects/SIT-Automation/docs/TESTCASES.md) for authoring rules
- [testcase_coverage_matrix_template.csv](/C:/Users/TalalHussain/GitProjects/SIT-Automation/docs/testcase_coverage_matrix_template.csv) for planning
- [create_testcase_coverage_matrix.py](/C:/Users/TalalHussain/GitProjects/SIT-Automation/scripts/create_testcase_coverage_matrix.py) to generate a live current-state matrix
