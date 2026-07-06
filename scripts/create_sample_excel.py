from pathlib import Path

from openpyxl import Workbook


output_path = Path("d:/tranning/SIT-automation/testcases/sit_testcases_generated.xlsx")
output_path.parent.mkdir(parents=True, exist_ok=True)

workbook = Workbook()
sheet = workbook.active
sheet.title = "SIT"

sheet.append(
    [
        "TC_ID",
        "Service",
        "Description",
        "Bank",
        "API_Name",
        "Request_File",
        "Expected_Result",
        "Validation_Type",
        "Execute (Y/N)",
        "Flow_Config",
        "Validation_Rules",
        "Trx_type",
    ]
)

sheet.append(
    [
        "TC001",
        "cas",
        "DirectPosting ACSP",
        "bank1",
        "directposting",
        "tc001.json",
        "ACSP",
        "response",
        "Y",
        "",
        "",
        "financial",
    ]
)

sheet.append(
    [
        "TC002",
        "cas",
        "DirectPosting RJCT",
        "bank1",
        "directposting",
        "tc002.json",
        "RJCT",
        "response",
        "Y",
        "",
        "",
        "financial",
    ]
)

sheet.append(
    [
        "TC003",
        "cas",
        "TitleFetch Success",
        "bank2",
        "titlefetch",
        "tc003.json",
        "SUCCESS",
        "response",
        "Y",
        "",
        "",
        "non-financial",
    ]
)

sheet.append(
    [
        "TC004",
        "cas",
        "ISO pacs.008 to pacs.002 flow",
        "bank1",
        "pacs008",
        "tc004_pacs008.json",
        "ACSP",
        "json_field",
        "N",
        "pacs008_to_pacs002",
        '{"field":"transaction_status"}',
        "non-financial",
    ]
)

sheet.append(
    [
        "TC101",
        "acquiring",
        "Acquiring Auth",
        "bank1",
        "authenticate",
        "tc_auth_acq.json",
        "SUCCESS",
        "response",
        "Y",
        "",
        "",
        "non-financial",
    ]
)

sheet.append(
    [
        "TC102",
        "acquiring",
        "Acquiring Transaction",
        "bank1",
        "transaction",
        "tc_acq_transaction.json",
        "SUCCESS",
        "response",
        "Y",
        "",
        "",
        "non-financial",
    ]
)

sheet.append(
    [
        "TC201",
        "merchant_cas",
        "Merchant CAS Auth",
        "bank1",
        "authenticate",
        "tc_auth_mcas.json",
        "SUCCESS",
        "response",
        "Y",
        "",
        "",
        "non-financial",
    ]
)

sheet.append(
    [
        "TC202",
        "merchant_cas",
        "Merchant CAS Payment",
        "bank1",
        "payment",
        "tc_mcas_payment.json",
        "SUCCESS",
        "response",
        "Y",
        "",
        "",
        "financial",
    ]
)

workbook.save(output_path)
print(f"Created: {output_path}")
