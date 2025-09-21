import json
import gspread

# Load the service account
with open('service_account.json', 'r') as f:
    service_account_info = json.load(f)

# Load the sheet key
with open('.streamlit/secrets.toml', 'r') as f:
    content = f.read()
    sheet_key = content.split('"')[1]

print(f"Sheet key: {sheet_key}")
print("Connecting to Google Sheets...")

try:
    gc = gspread.service_account_from_dict(service_account_info)
    sheet = gc.open_by_key(sheet_key)
    worksheet = sheet.worksheet('requests')
    print("✅ Connection successful!")
    
    # Try to read data
    data = worksheet.get_all_records()
    print(f"Current rows in sheet: {len(data)}")
    
except Exception as e:
    print(f"❌ Error: {e}")