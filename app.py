import streamlit as st
import pandas as pd
import json
import uuid
from datetime import datetime
import time
import re

# Import our utility functions
from utils import (
    init_sheets, append_request_row, read_all_requests, 
    read_requests_by_status, update_request_status, 
    geocode_address, haversine_distance
)

# Page configuration
st.set_page_config(
    page_title="Disaster Relief Coordination",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

def initialize_app():
    """Initialize the application with Google Sheets or CSV fallback."""
    if st.session_state.initialized:
        return
    
    try:
        # Try to get credentials from Streamlit secrets
        if "SERVICE_ACCOUNT_JSON" in st.secrets and "SHEET_KEY" in st.secrets:
            service_account_info = json.loads(st.secrets["SERVICE_ACCOUNT_JSON"])
            sheet_key = st.secrets["SHEET_KEY"]
            init_sheets(service_account_info, sheet_key)
        # Fallback to local file and environment variable
        elif hasattr(st, 'secrets') and "SHEET_KEY" in st.secrets:
            init_sheets("service_account.json", st.secrets["SHEET_KEY"])
        else:
            # No credentials available, use CSV fallback
            init_sheets({}, "")
            st.sidebar.warning("⚠️ Using CSV fallback (Google Sheets not configured)")
            
        st.session_state.initialized = True
        
    except Exception as e:
        st.error(f"Initialization error: {e}")
        # Still allow the app to run with CSV fallback
        init_sheets({}, "")
        st.session_state.initialized = True

def validate_phone(phone: str) -> bool:
    """Basic phone number validation."""
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    # Check if it's a reasonable length and format
    return len(cleaned) >= 10 and (cleaned.startswith('+') or cleaned.isdigit())

def validate_coordinates(lat_str: str, lon_str: str) -> tuple[bool, float, float]:
    """Validate and convert latitude/longitude strings."""
    try:
        lat = float(lat_str)
        lon = float(lon_str)
        # Basic range validation
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return True, lat, lon
        else:
            return False, 0.0, 0.0
    except ValueError:
        return False, 0.0, 0.0

def victim_view():
    """Victim form for submitting help requests."""
    st.header("🆘 Request Help")
    st.write("Fill out this form to request assistance during the disaster.")
    
    with st.form("victim_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Full Name *", placeholder="Enter your full name")
            phone = st.text_input("Phone Number *", placeholder="+91-XXXXXXXXXX")
            
        with col2:
            need = st.selectbox(
                "Type of Help Needed *",
                ["Water", "Food", "Medical", "Shelter", "Evacuation", "Other"]
            )
            extra = st.text_area("Additional Details", placeholder="Any special requirements or urgent notes")
        
        st.subheader("Location Information")
        location_method = st.radio(
            "How would you like to provide your location?",
            ["Enter Address", "Enter Coordinates"]
        )
        
        address = ""
        manual_lat = manual_lon = ""
        
        if location_method == "Enter Address":
            address = st.text_input("Address *", placeholder="Enter your current address or nearest landmark")
        else:
            col3, col4 = st.columns(2)
            with col3:
                manual_lat = st.text_input("Latitude *", placeholder="e.g., 13.0827")
            with col4:
                manual_lon = st.text_input("Longitude *", placeholder="e.g., 80.2707")
        
        submitted = st.form_submit_button("🚨 Submit Help Request", type="primary")
        
        if submitted:
            # Validation
            errors = []
            
            if not name.strip():
                errors.append("Name is required")
            if not phone.strip():
                errors.append("Phone number is required")
            elif not validate_phone(phone):
                errors.append("Please enter a valid phone number")
            
            lat = lon = None
            
            if location_method == "Enter Address":
                if not address.strip():
                    errors.append("Address is required")
                else:
                    # Try to geocode the address
                    with st.spinner("Finding your location..."):
                        coords = geocode_address(address)
                        if coords:
                            lat, lon = coords
                            st.success(f"✅ Location found: {lat:.4f}, {lon:.4f}")
                        else:
                            st.error("❌ Could not find your address. Please try entering coordinates manually.")
                            errors.append("Address could not be geocoded")
            else:
                if not manual_lat.strip() or not manual_lon.strip():
                    errors.append("Both latitude and longitude are required")
                else:
                    valid, lat, lon = validate_coordinates(manual_lat, manual_lon)
                    if not valid:
                        errors.append("Please enter valid coordinates (latitude: -90 to 90, longitude: -180 to 180)")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            elif lat is not None and lon is not None:
                # Create the request
                request = {
                    'id': str(uuid.uuid4()),
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'name': name.strip(),
                    'phone': phone.strip(),
                    'address': address.strip() if address else f"{lat}, {lon}",
                    'need': need,
                    'extra': extra.strip(),
                    'lat': lat,
                    'lon': lon,
                    'status': 'pending',
                    'responder': ''
                }
                
                # Submit the request
                with st.spinner("Submitting your request..."):
                    append_request_row(request)
                
                st.success("✅ Your help request has been submitted successfully!")
                st.info("📞 Emergency services and volunteers will be notified. Keep your phone nearby.")
                
                # Show request details
                st.subheader("📋 Your Request Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Request ID:** {request['id'][:8]}...")
                    st.write(f"**Name:** {request['name']}")
                    st.write(f"**Phone:** {request['phone']}")
                with col2:
                    st.write(f"**Need:** {request['need']}")
                    st.write(f"**Location:** {request['address']}")
                    st.write(f"**Status:** Pending")

def volunteer_view():
    """Volunteer dashboard for viewing and accepting requests."""
    st.header("🤝 Volunteer Dashboard")
    
    # Add refresh button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Refresh", type="secondary"):
            st.rerun()
    with col2:
        auto_refresh = st.checkbox("Auto-refresh (30s)")
    
    if auto_refresh:
        time.sleep(30)
        st.rerun()
    
    # Get pending and ongoing requests
    pending_requests = read_requests_by_status('pending')
    ongoing_requests = read_requests_by_status('ongoing')
    
    # Display summary
    st.subheader("📊 Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Pending Requests", len(pending_requests))
    with col2:
        st.metric("Ongoing Requests", len(ongoing_requests))
    with col3:
        helped_count = len(read_requests_by_status('helped'))
        st.metric("Completed Today", helped_count)
    
    # Map view
    if not pending_requests.empty:
        st.subheader("🗺️ Pending Requests Map")
        # Filter out rows with invalid coordinates
        map_data = pending_requests.dropna(subset=['lat', 'lon'])
        if not map_data.empty:
            st.map(map_data[['lat', 'lon']])
        else:
            st.info("No requests with valid coordinates to display on map.")
    
    # Pending requests list
    st.subheader("⏳ Pending Requests")
    if pending_requests.empty:
        st.info("🎉 No pending requests at the moment!")
    else:
        for idx, request in pending_requests.iterrows():
            with st.expander(f"🚨 {request['need']} - {request['name']} ({request['address']})"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Name:** {request['name']}")
                    st.write(f"**Phone:** {request['phone']}")
                    st.write(f"**Address:** {request['address']}")
                    st.write(f"**Need:** {request['need']}")
                    if request['extra']:
                        st.write(f"**Details:** {request['extra']}")
                    st.write(f"**Submitted:** {request['timestamp']}")
                    
                    # Calculate distance if volunteer location is available (you can enhance this)
                    if pd.notna(request['lat']) and pd.notna(request['lon']):
                        st.write(f"**Coordinates:** {request['lat']:.4f}, {request['lon']:.4f}")
                
                with col2:
                    responder_name = st.text_input(
                        "Your Name/Contact", 
                        key=f"responder_{request['id']}",
                        placeholder="Enter your name"
                    )
                    
                    if st.button(f"✅ Accept Request", key=f"accept_{request['id']}", type="primary"):
                        if responder_name.strip():
                            success = update_request_status(
                                request['id'], 
                                'ongoing', 
                                responder_name.strip()
                            )
                            if success:
                                st.success("✅ Request accepted!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to update request status")
                        else:
                            st.error("Please enter your name/contact info")
    
    # Ongoing requests (assigned to volunteers)
    st.subheader("🚧 Your Ongoing Requests")
    if ongoing_requests.empty:
        st.info("You have no ongoing requests.")
    else:
        for idx, request in ongoing_requests.iterrows():
            with st.expander(f"🚧 {request['need']} - {request['name']} (In Progress)"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Name:** {request['name']}")
                    st.write(f"**Phone:** {request['phone']}")
                    st.write(f"**Address:** {request['address']}")
                    st.write(f"**Need:** {request['need']}")
                    if request['extra']:
                        st.write(f"**Details:** {request['extra']}")
                    st.write(f"**Volunteer:** {request['responder']}")
                
                with col2:
                    if st.button(f"✅ Mark as Helped", key=f"complete_{request['id']}", type="primary"):
                        success = update_request_status(request['id'], 'helped')
                        if success:
                            st.success("✅ Request marked as completed!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to update request status")

def admin_view():
    """Admin view showing all requests and statistics."""
    st.header("👨‍💼 Admin Dashboard")
    
    # Refresh button
    if st.button("🔄 Refresh Data"):
        st.rerun()
    
    # Get all requests
    all_requests = read_all_requests()
    
    if all_requests.empty:
        st.info("No requests in the system yet.")
        return
    
    # Statistics
    st.subheader("📊 Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_requests = len(all_requests)
        st.metric("Total Requests", total_requests)
    
    with col2:
        pending_count = len(all_requests[all_requests['status'] == 'pending'])
        st.metric("Pending", pending_count)
    
    with col3:
        ongoing_count = len(all_requests[all_requests['status'] == 'ongoing'])
        st.metric("Ongoing", ongoing_count)
    
    with col4:
        helped_count = len(all_requests[all_requests['status'] == 'helped'])
        st.metric("Completed", helped_count)
    
    # Status distribution chart
    if not all_requests.empty:
        st.subheader("📈 Request Status Distribution")
        status_counts = all_requests['status'].value_counts()
        st.bar_chart(status_counts)
        
        # Need type distribution
        st.subheader("📋 Request Types")
        need_counts = all_requests['need'].value_counts()
        st.bar_chart(need_counts)
    
    # All requests table
    st.subheader("📋 All Requests")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "pending", "ongoing", "helped", "cancelled"]
        )
    with col2:
        need_filter = st.selectbox(
            "Filter by Need Type",
            ["All"] + sorted(all_requests['need'].unique().tolist())
        )
    
    # Apply filters
    filtered_data = all_requests.copy()
    if status_filter != "All":
        filtered_data = filtered_data[filtered_data['status'] == status_filter]
    if need_filter != "All":
        filtered_data = filtered_data[filtered_data['need'] == need_filter]
    
    # Display the table
    if not filtered_data.empty:
        # Format the display
        display_data = filtered_data.copy()
        display_data['timestamp'] = pd.to_datetime(display_data['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.TextColumn("ID", width="small"),
                "timestamp": st.column_config.TextColumn("Time", width="medium"),
                "name": st.column_config.TextColumn("Name", width="medium"),
                "phone": st.column_config.TextColumn("Phone", width="medium"),
                "address": st.column_config.TextColumn("Address", width="large"),
                "need": st.column_config.TextColumn("Need", width="small"),
                "extra": st.column_config.TextColumn("Details", width="large"),
                "status": st.column_config.TextColumn("Status", width="small"),
                "responder": st.column_config.TextColumn("Volunteer", width="medium")
            }
        )
        
        # Download button
        csv = filtered_data.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"disaster_requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No requests match the current filters.")

def main():
    """Main application function."""
    # Initialize the app
    initialize_app()
    
    # App title
    st.title("🚨 Disaster Relief Coordination System")
    st.markdown("---")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    view = st.sidebar.selectbox(
        "Select View",
        ["Victim", "Volunteer", "Admin"],
        help="Choose your role to access the appropriate interface"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info(
        "This system helps coordinate disaster relief efforts by connecting "
        "victims who need help with volunteers who can provide assistance."
    )
    
    # Display the selected view
    if view == "Victim":
        victim_view()
    elif view == "Volunteer":
        volunteer_view()
    elif view == "Admin":
        admin_view()

if __name__ == "__main__":
    main()