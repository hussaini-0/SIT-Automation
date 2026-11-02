# NBP Swagger alignment

Source contracts: `specs/nbp/9091.openapi.json` (CAS), `9093.openapi.json` (Merchant CAS), and `9096.openapi.json` (Acquiring). The NBP-only workbook is `testcases/sit_testcases_nbp.xlsx`.

All in-scope HTTP operations have a corresponding NBP workbook case and configured route: CAS 46/47 (the previously excluded `registercaa` is not included), Merchant CAS 19/19, and Acquiring 38/38. The 37 routes absent from the shared config are defined in `config/apis_nbp.yaml`. Existing case/request mappings were kept; 101 Merchant CAS alias/RTP request bodies were copied into `requests/merchant_cas/nbp/` and trimmed to the respective Swagger schemas.

The workbook's `MPG_SENDER_API` sheet is outside these three contracts and was not changed. Twenty Acquiring authentication cases target Keycloak rather than an operation in the 9096 spec.

The workbook includes 38 newly added, **disabled** cases for operations that were missing from NBP coverage (26 CAS and 12 Merchant CAS). Their request files are structural scaffolds, not validated business examples. Twenty-six pre-existing Merchant CAS negative cases were disabled because their request did not actually exercise the stated negative condition. The Acquiring workbook also has 41 pre-existing disabled positive Swagger smoke cases; these should not be treated as proven passing scenarios.

For NBP RTP Now/Later Merchant CAS payments, the runner now calls Acquiring `generateRTP` first and injects the returned RTP ID into the payment request. Cases explicitly testing a missing or invalid RTP ID keep their original input. Other banks are unaffected.

NBP SQRC Merchant CAS payments use the PHC merchant profile supplied for NBP (`NBPBPKKA`, `PK47NBPA0271003000011184`) through bank-and-API-scoped `api_test_data` in `config/servers.yaml`. This applies only to `merchant_payment_direct_sqrc` and `merchant_payment_sqrc`; alias/RTP cases and other banks retain their existing merchant data. The supplied MCIB sender, zero amount, and fixed transaction timestamp were not copied into NBP positive tests. Negative SQRC templates still preserve intentionally missing or invalid fields.

Static audit: `outputs/nbp-swagger-20260916/audit.json`. To regenerate it, run `python tools/sync_nbp_swagger_suite.py`. This audit checks route membership and JSON schema shape; it does **not** prove business responses. `MERCHANT_ALIAS_PAYMENT_PURPOSE` is currently set to `027` as a candidate and needs a successful NBP example to confirm it. Enable the new cases only after supplying valid NBP request data and verified expected business response codes. No financial API was called during this alignment.
