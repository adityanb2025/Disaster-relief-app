import pandas as pd
import gspread
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import json
import csv
import os
import time
import math
from typing import Optional, Tuple, Dict, Union

# Global variables for Google Sheets
gc = None
worksheet = None
sheets_enabled = False

def init_sheets(service_account_json_path: Union[str, dict], sheet_key: str) -> None:
    """Initialize gspread client and reference to 'requests' worksheet."""
    global gc, worksheet, sheets_enabled
    
    try:
        if isinstance(service_account_json_path, dict):
            # Use dictionary directly (for Streamlit secrets)
            gc = gspread.service_account_from_dict(service_account_json_path)
        else:
            # Use file path
            gc = gspread.service_account(filename=service_account_json_path)
        
        # Open the sheet and get the requests worksheet
        sheet = gc.open_by_key(sheet_key)
        worksheet = sheet.worksheet('requests')
        sheets_enabled = True
        print("Google Sheets initialized successfully")
        
        # Ensure header row exists
        try:
            headers = worksheet.row_values(1)
            expected_headers = ['id', 'timestamp', 'name', 'phone', 'address', 'need', 'extra', 'lat', 'lon', 'status', 'responder']
            if not headers or headers != expected_headers:
                worksheet.clear()
                worksheet.append_row(expected_headers)
                print("Header row created/updated")
        except Exception as e:
            print(f"Error setting up headers: {e}")
            
    except Exception as e:
        print(f"Failed to initialize Google Sheets: {e}")
        sheets_enabled = False
        # Ensure CSV fallback file exists
        if not os.path.exists('requests.csv'):
            with open('requests.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'timestamp', 'name', 'phone', 'address', 'need', 'extra', 'lat', 'lon', 'status', 'responder'])

def append_request_row(request: dict) -> None:
    """Append a new request row to the sheet. 'request' keys match header names."""
    global worksheet, sheets_enabled
    
    # Ensure all required fields are present
    row_data = [
        request.get('id', ''),
        request.get('timestamp', ''),
        request.get('name', ''),
        request.get('phone', ''),
        request.get('address', ''),
        request.get('need', ''),
        request.get('extra', ''),
        request.get('lat', ''),
        request.get('lon', ''),
        request.get('status', 'pending'),
        request.get('responder', '')
    ]
    
    if sheets_enabled and worksheet:
        try:
            worksheet.append_row(row_data)
            print("Request added to Google Sheets")
        except Exception as e:
            print(f"Error writing to Google Sheets: {e}")
            # Fall back to CSV
            _append_to_csv(row_data)
    else:
        # Use CSV fallback
        _append_to_csv(row_data)

def _append_to_csv(row_data: list) -> None:
    """Helper function to append data to CSV file."""
    with open('requests.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(row_data)
    print("Request added to CSV file")

def read_all_requests() -> pd.DataFrame:
    """Return all rows as DataFrame with proper dtypes."""
    global worksheet, sheets_enabled
    
    if sheets_enabled and worksheet:
        try:
            records = worksheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                # Convert lat/lon to numeric, handling empty strings
                df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
                df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
                return df
            else:
                return _get_empty_dataframe()
        except Exception as e:
            print(f"Error reading from Google Sheets: {e}")
            # Fall back to CSV
            return _read_csv()
    else:
        return _read_csv()

def _read_csv() -> pd.DataFrame:
    """Helper function to read from CSV file."""
    if os.path.exists('requests.csv'):
        try:
            df = pd.read_csv('requests.csv')
            # Convert lat/lon to numeric, handling empty strings
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            return df
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return _get_empty_dataframe()
    else:
        return _get_empty_dataframe()

def _get_empty_dataframe() -> pd.DataFrame:
    """Return empty DataFrame with correct columns."""
    return pd.DataFrame(columns=['id', 'timestamp', 'name', 'phone', 'address', 'need', 'extra', 'lat', 'lon', 'status', 'responder'])

def read_requests_by_status(status: str) -> pd.DataFrame:
    """Return requests filtered by status."""
    df = read_all_requests()
    if not df.empty:
        return df[df['status'] == status]
    return df

def update_request_status(request_id: str, new_status: str, responder: Optional[str] = None) -> bool:
    """Change status for row that matches id. Return True if updated."""
    global worksheet, sheets_enabled
    
    if sheets_enabled and worksheet:
        try:
            # Find the cell with the matching ID
            cell = worksheet.find(request_id)
            if cell:
                row_num = cell.row
                # Update status (column 10)
                worksheet.update_cell(row_num, 10, new_status)
                # Update responder (column 11) if provided
                if responder:
                    worksheet.update_cell(row_num, 11, responder)
                print(f"Updated request {request_id} in Google Sheets")
                return True
            else:
                print(f"Request ID {request_id} not found in Google Sheets")
                return False
        except Exception as e:
            print(f"Error updating Google Sheets: {e}")
            # Fall back to CSV update
            return _update_csv_status(request_id, new_status, responder)
    else:
        return _update_csv_status(request_id, new_status, responder)

def _update_csv_status(request_id: str, new_status: str, responder: Optional[str] = None) -> bool:
    """Helper function to update status in CSV file."""
    if not os.path.exists('requests.csv'):
        return False
    
    try:
        # Read all rows
        rows = []
        updated = False
        with open('requests.csv', 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # Update the matching row
        for i, row in enumerate(rows):
            if i > 0 and len(row) > 0 and row[0] == request_id:  # Skip header row
                row[9] = new_status  # status column
                if responder:
                    row[10] = responder  # responder column
                updated = True
                break
        
        # Write back to file
        if updated:
            with open('requests.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            print(f"Updated request {request_id} in CSV")
            return True
        else:
            print(f"Request ID {request_id} not found in CSV")
            return False
            
    except Exception as e:
        print(f"Error updating CSV: {e}")
        return False

def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) using geopy.Nominatim or None if failed."""
    if not address.strip():
        return None
    
    geolocator = Nominatim(user_agent="disaster_relief_app")
    
    # Try up to 3 times with increasing delays
    for attempt in range(3):
        try:
            location = geolocator.geocode(address, timeout=10)
            if location:
                return (location.latitude, location.longitude)
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            if attempt < 2:  # Don't sleep on the last attempt
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            print(f"Geocoding failed after {attempt + 1} attempts: {e}")
        except Exception as e:
            print(f"Geocoding error: {e}")
            break
    
    return None

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km using Haversine formula."""
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r