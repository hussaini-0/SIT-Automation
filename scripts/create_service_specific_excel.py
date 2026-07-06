from pathlib import Path
from openpyxl import Workbook

# Base directory
testcases_dir = Path("d:/tranning/SIT-automation/testcases")
testcases_dir.mkdir(parents=True, exist_ok=True)

# Column headers (without Service since it's implicit by filename)
headers = [
    "TC_ID",
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

# CAS workbook is intentionally not generated here.
# Existing file sit_testcases.xlsx remains the source for CAS service.

# ============================================
# Acquiring Service Test Cases
# ============================================
acquiring_workbook = Workbook()
acquiring_sheet = acquiring_workbook.active
acquiring_sheet.title = "ACQUIRING"
acquiring_sheet.append(headers)

acquiring_testcases = []

for tc in acquiring_testcases:
    acquiring_sheet.append(tc)

acquiring_workbook.save(testcases_dir / "sit_testcases_acquiring.xlsx")
print(f"✓ Created: {testcases_dir / 'sit_testcases_acquiring.xlsx'}")

# ============================================
# Merchant CAS Service Test Cases
# ============================================
merchant_workbook = Workbook()
merchant_sheet = merchant_workbook.active
merchant_sheet.title = "MERCHANT_CAS"
merchant_sheet.append(headers)

merchant_testcases = []

for tc in merchant_testcases:
    merchant_sheet.append(tc)

merchant_workbook.save(testcases_dir / "sit_testcases_merchant_cas.xlsx")
print(f"✓ Created: {testcases_dir / 'sit_testcases_merchant_cas.xlsx'}")

print("\n✓ Created acquiring and merchant CAS testcase files successfully!")
