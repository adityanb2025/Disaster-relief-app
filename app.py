import streamlit as st
import pandas as pd
import json
import uuid
from datetime import datetime
import time
import re
import pytz

# Import our utility functions
from utils import (
    init_sheets, append_request_row, read_all_requests, 
    read_requests_by_status, update_request_status, 
    geocode_address, haversine_distance
)

# Enhanced page configuration
st.set_page_config(
    page_title="Disaster Relief Hub",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper functions for IST timezone handling
def get_ist_now():
    """Get current time in Indian Standard Time."""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def convert_to_ist(timestamp_str):
    """Convert timestamp string to IST datetime object."""
    try:
        # Parse the timestamp
        dt = pd.to_datetime(timestamp_str)
        
        # If timezone-naive, assume UTC
        if dt.tz is None:
            dt = dt.tz_localize('UTC')
        
        # Convert to IST
        ist = pytz.timezone('Asia/Kolkata')
        return dt.tz_convert(ist)
    except:
        # Fallback to current IST time if parsing fails
        return get_ist_now()

def format_ist_time(timestamp_str, format_type='full'):
    """Format timestamp in IST with different format options."""
    try:
        ist_dt = convert_to_ist(timestamp_str)
        
        if format_type == 'short':
            return ist_dt.strftime('%m/%d %H:%M')
        elif format_type == 'time_ago':
            now_ist = get_ist_now()
            # Make both timezone-naive for comparison
            now_naive = now_ist.replace(tzinfo=None)
            dt_naive = ist_dt.replace(tzinfo=None)
            
            time_diff = now_naive - dt_naive
            minutes = int(time_diff.total_seconds() / 60)
            
            if minutes < 1:
                return "Just now"
            elif minutes < 60:
                return f"{minutes} min ago"
            elif minutes < 1440:  # less than 24 hours
                hours = int(minutes / 60)
                return f"{hours}h ago"
            else:
                days = int(minutes / 1440)
                return f"{days}d ago"
        else:  # full format
            return ist_dt.strftime('%B %d, %Y at %I:%M %p IST')
    except:
        return "Recently"

def get_need_emoji(need):
    """Get emoji for need type."""
    emojis = {
        "Water": "💧",
        "Food": "🍞",
        "Medical": "🏥",
        "Shelter": "🏠",
        "Evacuation": "🚑",
        "Other": "❓"
    }
    return emojis.get(need, "❓")

def get_priority_class(need):
    """Get CSS class for priority based on need type."""
    high_priority = ["Medical", "Evacuation"]
    medium_priority = ["Water", "Food"]
    
    if need in high_priority:
        return "priority-high"
    elif need in medium_priority:
        return "priority-medium"
    else:
        return "priority-low"

# Custom CSS for enhanced UI
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-color: #ff4b4b;
        --secondary-color: #0066cc;
        --success-color: #00cc66;
        --warning-color: #ff9900;
        --danger-color: #cc0000;
    }
    
    /* Enhanced sidebar */
    .css-1d391kg {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    /* Custom cards */
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border-left: 4px solid var(--primary-color);
        margin: 0.5rem 0;
    }
    
    .status-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 1rem 0;
    }
    
    .emergency-button {
        background: linear-gradient(135deg, #ff6b6b, #ee5a52);
        color: white !important;
        padding: 0.75rem 2rem;
        border-radius: 50px;
        border: none;
        font-weight: bold;
        font-size: 1.1rem;
        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
        transition: all 0.3s ease;
    }
    
    .emergency-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 107, 107, 0.4);
    }
    
    .help-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }
    
    .help-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
    }
    
    .priority-high {
        border-left: 5px solid #ff4b4b;
    }
    
    .priority-medium {
        border-left: 5px solid #ff9900;
    }
    
    .priority-low {
        border-left: 5px solid #00cc66;
    }
    
    /* Enhanced form styling */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        transition: border-color 0.3s ease;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(255, 75, 75, 0.2);
    }
    
    /* Status badges */
    .status-pending {
        background: #fff3cd;
        color: #856404;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    
    .status-ongoing {
        background: #cce5ff;
        color: #004085;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    
    .status-helped {
        background: #d4edda;
        color: #155724;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    
    /* Animations */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .pulse-animation {
        animation: pulse 2s infinite;
    }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        .help-card {
            padding: 1rem;
        }
        
        .status-card {
            padding: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

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
    """Enhanced victim form for submitting help requests."""
    st.markdown('<div class="status-card">', unsafe_allow_html=True)
    st.markdown("# 🆘 Emergency Help Request")
    st.markdown("### We're here to help you. Fill out this form to request immediate assistance.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Emergency contact info
    col1, col2 = st.columns(2)
    with col1:
        st.info("🚨 **For immediate life-threatening emergencies, call 100 or local emergency services**")
    with col2:
        st.success("📱 **This form connects you with local volunteers and relief coordinators**")
    
    with st.form("victim_form"):
        st.markdown("### 👤 Personal Information")
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input(
                "Full Name *", 
                placeholder="Enter your full name",
                help="This helps us identify and contact you"
            )
            phone = st.text_input(
                "Phone Number *", 
                placeholder="+1-XXX-XXX-XXXX",
                help="We'll use this to coordinate help"
            )
            
        with col2:
            need = st.selectbox(
                "Type of Help Needed *",
                ["Water", "Food", "Medical", "Shelter", "Evacuation", "Other"],
                help="Select your most urgent need"
            )
            
            urgency = st.selectbox(
                "Urgency Level *",
                ["Medium - Urgent", "High - Life threatening", "Low - Non-urgent"],
                help="Help us prioritize requests"
            )
        
        st.markdown("### 📝 Additional Details")
        extra = st.text_area(
            "Describe your situation", 
            placeholder="Please provide any additional details that might help responders (number of people, specific medical needs, etc.)",
            height=100,
            help="The more details you provide, the better we can help"
        )
        
        st.markdown("### 📍 Location Information")
        st.info("📌 **Accurate location is crucial for getting help to you quickly**")
        
        location_method = st.radio(
            "Provide your location?",
            ["📍 Enter Address"],
            horizontal=True
        )
        
        address = ""
        manual_lat = manual_lon = ""
        
        if location_method == "📍 Enter Address":
            address = st.text_input(
                "Your Current Address *", 
                placeholder="Street address, landmark, or detailed description of location",
                help="Be as specific as possible - include landmarks if helpful"
            )
        # Submit button with enhanced styling
        submitted = st.form_submit_button(
            "🚨 SUBMIT EMERGENCY REQUEST", 
            type="primary",
            use_container_width=True
        )
        
        if submitted:
            # Validation with better error messages
            errors = []
            
            if not name.strip():
                errors.append("Please enter your full name")
            if not phone.strip():
                errors.append("Phone number is required")
            elif not validate_phone(phone):
                errors.append("Please enter a valid phone number (e.g., +1-555-123-4567)")
            
            lat = lon = None
            
            if location_method == "📍 Enter Address":
                if not address.strip():
                    errors.append("Address is required")
                else:
                    # Try to geocode the address
                    with st.spinner("🔍 Finding your location..."):
                        coords = geocode_address(address)
                        if coords:
                            lat, lon = coords
                            st.success(f"✅ Location found: {lat:.4f}, {lon:.4f}")
                        else:
                            st.error("❌ Could not find your address. Please try entering GPS coordinates instead.")
                            errors.append("Address could not be found on the map")
            else:
                if not manual_lat.strip() or not manual_lon.strip():
                    errors.append("Both latitude and longitude coordinates are required")
                else:
                    valid, lat, lon = validate_coordinates(manual_lat, manual_lon)
                    if not valid:
                        errors.append("Please enter valid GPS coordinates")
            
            if errors:
                st.error("❌ **Please fix the following issues:**")
                for error in errors:
                    st.error(f"• {error}")
            elif lat is not None and lon is not None:
                # Create the request
                request = {
                    'id': str(uuid.uuid4()),
                    'timestamp': get_ist_now().isoformat(),
                    'name': name.strip(),
                    'phone': phone.strip(),
                    'address': address.strip() if address else f"{lat}, {lon}",
                    'need': need,
                    'urgency': urgency,
                    'extra': extra.strip(),
                    'lat': lat,
                    'lon': lon,
                    'status': 'pending',
                    'responder': ''
                }
                
                # Submit the request
                with st.spinner("📤 Submitting your emergency request..."):
                    try:
                        append_request_row(request)
                        
                        st.balloons()
                        st.success("✅ **Your help request has been submitted successfully!**")
                        
                        # Enhanced success message
                        st.markdown('<div class="help-card">', unsafe_allow_html=True)
                        st.markdown("### 🎯 **What happens next?**")
                        st.markdown("""
                        1. **📡 Your request is now in our system** - Emergency coordinators can see it
                        2. **🤝 Volunteers will be notified** - Based on your location and needs
                        3. **📞 Someone will contact you** - Keep your phone nearby and charged
                        4. **⏱️ Expected response time** - 15-30 minutes for urgent requests
                        """)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Show request details in an attractive format
                        st.markdown("### 📋 Your Request Summary")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"""
                            **🆔 Request ID:** `{request['id'][:8]}...`  
                            **👤 Name:** {request['name']}  
                            **📞 Phone:** {request['phone']}  
                            **📍 Location:** {request['address']}
                            """)
                        with col2:
                            emoji = get_need_emoji(request['need'])
                            st.markdown(f"""
                            **{emoji} Need:** {request['need']}  
                            **⚡ Urgency:** {request['urgency']}  
                            **📊 Status:** 🟡 Pending  
                            **⏰ Submitted:** {get_ist_now().strftime('%I:%M %p IST')}
                            """)
                        
                        if request['extra']:
                            st.markdown(f"**📝 Additional Details:** {request['extra']}")
                            
                    except Exception as e:
                        st.error(f"❌ Failed to submit request: {str(e)}")
                        st.error("Please try again or contact emergency services directly.")

def volunteer_view():
    """Enhanced volunteer dashboard for viewing and accepting requests."""
    st.markdown('<div class="status-card">', unsafe_allow_html=True)
    st.markdown("# 🤝 Volunteer Command Center")
    st.markdown("### Help coordinate disaster relief efforts in your community")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Enhanced control panel
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔄 Refresh Dashboard", type="secondary", use_container_width=True):
            st.rerun()
    with col2:
        auto_refresh = st.checkbox("🔄 Auto-refresh (30s)")
    with col3:
        view_mode = st.selectbox("👁️ View Mode", ["All Requests", "Map Only", "List Only"])
    with col4:
        priority_filter = st.selectbox("⚡ Priority", ["All", "High", "Medium", "Low"])
    
    if auto_refresh:
        time.sleep(30)
        st.rerun()
    
    # Get requests data
    pending_requests = read_requests_by_status('pending')
    ongoing_requests = read_requests_by_status('ongoing')
    helped_requests = read_requests_by_status('helped')
    
    # Enhanced metrics dashboard
    st.markdown("### 📊 Live Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        pending_count = len(pending_requests)
        st.metric("🆘 Pending", pending_count, delta=None)
        if pending_count > 0:
            st.markdown('<small class="pulse-animation">🔴 Needs attention</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        ongoing_count = len(ongoing_requests)
        st.metric("🚧 In Progress", ongoing_count)
        if ongoing_count > 0:
            st.markdown('<small>🟡 Being handled</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        helped_count = len(helped_requests)
        st.metric("✅ Completed Today", helped_count)
        if helped_count > 0:
            st.markdown('<small>🟢 Great work!</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        total_count = pending_count + ongoing_count + helped_count
        st.metric("📈 Total Requests", total_count)
        if total_count > 0:
            completion_rate = (helped_count / total_count) * 100
            st.markdown(f'<small>📊 {completion_rate:.1f}% completion rate</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Map view (enhanced)
    if view_mode in ["All Requests", "Map Only"] and not pending_requests.empty:
        st.markdown("### 🗺️ Emergency Locations Map")
        map_data = pending_requests.dropna(subset=['lat', 'lon'])
        if not map_data.empty:
            st.info("📍 **Red pins show locations needing help** - Click on requests below to respond")
            st.map(map_data[['lat', 'lon']], zoom=11)
        else:
            st.info("📍 No requests with valid coordinates to display on map.")
    
    # Enhanced pending requests section
    if view_mode in ["All Requests", "List Only"]:
        st.markdown("### ⏳ Pending Emergency Requests")
        
        if pending_requests.empty:
            st.markdown('<div class="help-card">', unsafe_allow_html=True)
            st.markdown("### 🎉 All Clear!")
            st.markdown("No pending requests at the moment. Great work team!")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # Sort by timestamp (most recent first)
            pending_requests_sorted = pending_requests.sort_values('timestamp', ascending=False)
            
            for idx, request in pending_requests_sorted.iterrows():
                # Handle urgency field safely
                urgency = request.get('urgency', 'Medium')
                urgency_emoji = "🔴" if "High" in str(urgency) else "🟡" if "Medium" in str(urgency) else "🟢"
                need_emoji = get_need_emoji(request['need'])
                priority_class = get_priority_class(request['need'])
                
                st.markdown(f'<div class="help-card {priority_class}">', unsafe_allow_html=True)
                
                # Request header
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"### {urgency_emoji} {need_emoji} {request['need']} Request")
                    st.markdown(f"**👤 {request['name']}** • 📍 {request['address']}")
                with col2:
                    time_display = format_ist_time(request['timestamp'], 'time_ago')
                    st.markdown(f"**⏰ Submitted**  \n{time_display}")
                with col3:
                    urgency_level = request.get('urgency', 'Not specified')
                    st.markdown(f"**⚡ Priority**  \n{urgency_level}")
                
                # Request details in expandable section
                with st.expander(f"📋 View Full Details - {request['name']}", expanded=False):
                    detail_col1, detail_col2 = st.columns([2, 1])
                    
                    with detail_col1:
                        st.markdown("#### Contact Information")
                        st.markdown(f"**📞 Phone:** {request['phone']}")
                        st.markdown(f"**📍 Address:** {request['address']}")
                        
                        if request['extra']:
                            st.markdown("#### Additional Details")
                            st.markdown(f"💬 _{request['extra']}_")
                        
                        st.markdown("#### Location Data")
                        if pd.notna(request['lat']) and pd.notna(request['lon']):
                            st.markdown(f"**🌐 Coordinates:** {request['lat']:.4f}, {request['lon']:.4f}")
                            st.markdown(f"[📍 View on Google Maps](https://maps.google.com/?q={request['lat']},{request['lon']})")
                        
                        st.markdown(f"**🕒 Request Time:** {format_ist_time(request['timestamp'], 'full')}")
                    
                    with detail_col2:
                        st.markdown("#### 🤝 Accept This Request")
                        responder_name = st.text_input(
                            "Your Name/Contact Info", 
                            key=f"responder_{request['id']}",
                            placeholder="Enter your name and phone",
                            help="This will be shared with the person requesting help"
                        )
                        
                        if st.button(
                            f"✅ I'll Help With This Request", 
                            key=f"accept_{request['id']}", 
                            type="primary",
                            use_container_width=True
                        ):
                            if responder_name.strip():
                                success = update_request_status(
                                    request['id'], 
                                    'ongoing', 
                                    responder_name.strip()
                                )
                                if success:
                                    st.success("✅ Request accepted! The person will be notified.")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to accept request. Please try again.")
                            else:
                                st.error("Please enter your contact information")
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Enhanced ongoing requests section
        st.markdown("### 🚧 Your Active Assignments")
        if ongoing_requests.empty:
            st.info("You have no active assignments. Accept a pending request above to get started!")
        else:
            for idx, request in ongoing_requests.iterrows():
                need_emoji = get_need_emoji(request['need'])
                
                st.markdown('<div class="help-card priority-medium">', unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"### 🚧 {need_emoji} {request['need']} - In Progress")
                    st.markdown(f"**👤 Person:** {request['name']} • **📞 Phone:** {request['phone']}")
                    st.markdown(f"**📍 Location:** {request['address']}")
                    if request['extra']:
                        st.markdown(f"**📝 Notes:** _{request['extra']}_")
                    st.markdown(f"**🤝 Volunteer:** {request['responder']}")
                
                with col2:
                    st.markdown("#### ✅ Mark Complete")
                    if st.button(
                        f"✅ Task Completed", 
                        key=f"complete_{request['id']}", 
                        type="primary",
                        use_container_width=True
                    ):
                        success = update_request_status(request['id'], 'helped')
                        if success:
                            st.success("✅ Excellent work! Request marked as completed.")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to update status. Please try again.")
                
                st.markdown('</div>', unsafe_allow_html=True)

def admin_view():
    """Enhanced admin view showing all requests and statistics."""
    st.markdown('<div class="status-card">', unsafe_allow_html=True)
    st.markdown("#  Admin Control Center")
    st.markdown("### Complete oversight of disaster relief operations")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Enhanced refresh controls
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Refresh All Data", use_container_width=True):
            st.rerun()
    with col2:
        auto_refresh = st.checkbox("🔄 Auto-refresh (60s)")
    
    if auto_refresh:
        time.sleep(60)
        st.rerun()
    
    # Get all requests
    all_requests = read_all_requests()
    
    if all_requests.empty:
        st.markdown('<div class="help-card">', unsafe_allow_html=True)
        st.markdown("### 📊 No Data Available")
        st.markdown("No requests in the system yet. The dashboard will populate as requests come in.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Enhanced statistics dashboard
    st.markdown("### 📊 Real-Time Operations Dashboard")
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_requests = len(all_requests)
    pending_count = len(all_requests[all_requests['status'] == 'pending'])
    ongoing_count = len(all_requests[all_requests['status'] == 'ongoing'])
    helped_count = len(all_requests[all_requests['status'] == 'helped'])
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("📈 Total Requests", total_requests)
        st.markdown(f'<small>All-time requests</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("🆘 Pending", pending_count)
        if pending_count > 0:
            st.markdown(f'<small class="pulse-animation">🔴 Needs immediate attention</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("🚧 In Progress", ongoing_count)
        if ongoing_count > 0:
            st.markdown(f'<small>🟡 Being handled by volunteers</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("✅ Completed", helped_count)
        if total_requests > 0:
            completion_rate = (helped_count / total_requests) * 100
            st.markdown(f'<small>📊 {completion_rate:.1f}% completion rate</small>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Response time and efficiency metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        urgent_requests = all_requests
        if 'urgency' in all_requests.columns:
            urgent_requests = all_requests[all_requests['urgency'].str.contains('High', na=False)]
        else:
            # If no urgency column, count medical and evacuation as urgent
            urgent_requests = all_requests[all_requests['need'].isin(['Medical', 'Evacuation'])]
        
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("🔴 High Priority", len(urgent_requests))
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        medical_requests = all_requests[all_requests['need'] == 'Medical']
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("🏥 Medical", len(medical_requests))
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        try:
            # Calculate recent requests safely using IST
            now_ist = get_ist_now()
            cutoff_time = now_ist - pd.Timedelta(hours=1)
            
            # Convert timestamps to IST and compare
            recent_count = 0
            for _, request in all_requests.iterrows():
                try:
                    request_ist = convert_to_ist(request['timestamp'])
                    if request_ist.replace(tzinfo=None) > cutoff_time.replace(tzinfo=None):
                        recent_count += 1
                except:
                    continue
                    
        except:
            # Fallback if timestamp parsing fails
            recent_count = 0
            
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("🕐 Last Hour", recent_count)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        active_volunteers = all_requests[all_requests['responder'] != '']['responder'].nunique()
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("👥 Active Volunteers", active_volunteers)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Enhanced visualizations
    if not all_requests.empty:
        st.markdown("### 📈 Analytics Dashboard")
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Status Overview", "📋 Request Types", "⏰ Timeline", "🗺️ Geographic"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📊 Request Status Distribution")
                status_counts = all_requests['status'].value_counts()
                st.bar_chart(status_counts)
            
            with col2:
                st.markdown("#### 🔄 Status Breakdown")
                status_data = []
                for status in ['pending', 'ongoing', 'helped']:
                    count = len(all_requests[all_requests['status'] == status])
                    percentage = (count / total_requests * 100) if total_requests > 0 else 0
                    status_data.append({
                        'Status': status.title(),
                        'Count': count,
                        'Percentage': f"{percentage:.1f}%"
                    })
                st.dataframe(pd.DataFrame(status_data), hide_index=True, use_container_width=True)
        
        with tab2:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📋 Help Request Types")
                need_counts = all_requests['need'].value_counts()
                st.bar_chart(need_counts)
            
            with col2:
                st.markdown("#### 📝 Request Type Details")
                need_data = []
                for need in need_counts.index:
                    count = need_counts[need]
                    pending = len(all_requests[(all_requests['need'] == need) & (all_requests['status'] == 'pending')])
                    need_data.append({
                        'Type': f"{get_need_emoji(need)} {need}",
                        'Total': count,
                        'Pending': pending,
                        'Completion Rate': f"{((count-pending)/count*100):.0f}%" if count > 0 else "0%"
                    })
                st.dataframe(pd.DataFrame(need_data), hide_index=True, use_container_width=True)
        
        with tab3:
            st.markdown("#### ⏰ Request Timeline (Last 24 Hours IST)")
            try:
                # Create hourly breakdown with IST timestamps
                timeline_data = []
                now_ist = get_ist_now()
                last_24h = now_ist - pd.Timedelta(hours=24)
                
                for _, request in all_requests.iterrows():
                    try:
                        request_ist = convert_to_ist(request['timestamp'])
                        if request_ist.replace(tzinfo=None) > last_24h.replace(tzinfo=None):
                            hour_bucket = request_ist.replace(minute=0, second=0, microsecond=0)
                            timeline_data.append({
                                'hour': hour_bucket.replace(tzinfo=None),
                                'count': 1
                            })
                    except:
                        continue
                
                if timeline_data:
                    timeline_df = pd.DataFrame(timeline_data)
                    hourly_counts = timeline_df.groupby('hour')['count'].sum().reset_index()
                    st.line_chart(hourly_counts.set_index('hour')['count'])
                else:
                    st.info("No requests in the last 24 hours.")
            except Exception as e:
                st.info("Timeline data not available due to timestamp format issues.")
        
        with tab4:
            st.markdown("#### 🗺️ Geographic Distribution")
            map_data = all_requests.dropna(subset=['lat', 'lon'])
            if not map_data.empty:
                st.map(map_data[['lat', 'lon']], zoom=10)
                st.markdown(f"**📍 Showing {len(map_data)} requests with location data**")
            else:
                st.info("No geographic data available for mapping.")
    
    # Enhanced data management section
    st.markdown("### 📋 Request Management Center")
    
    # Advanced filtering
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.selectbox(
            "📊 Filter by Status",
            ["All", "pending", "ongoing", "helped", "cancelled"]
        )
    with col2:
        need_filter = st.selectbox(
            "📋 Filter by Need Type",
            ["All"] + sorted(all_requests['need'].unique().tolist())
        )
    with col3:
        urgency_filter = st.selectbox(
            "⚡ Filter by Urgency",
            ["All", "High", "Medium", "Low"]
        )
    with col4:
        time_filter = st.selectbox(
            "⏰ Time Range",
            ["All Time", "Last Hour", "Last 6 Hours", "Last 24 Hours", "Last Week"]
        )
    
    # Apply filters
    filtered_data = all_requests.copy()
    
    if status_filter != "All":
        filtered_data = filtered_data[filtered_data['status'] == status_filter]
    if need_filter != "All":
        filtered_data = filtered_data[filtered_data['need'] == need_filter]
    if urgency_filter != "All":
        if 'urgency' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['urgency'].str.contains(urgency_filter, na=False)]
        else:
            # If urgency column doesn't exist, show all data when any urgency filter is selected
            pass
    
    # Time filtering with IST
    if time_filter != "All Time":
        now_ist = get_ist_now()
        time_deltas = {
            "Last Hour": pd.Timedelta(hours=1),
            "Last 6 Hours": pd.Timedelta(hours=6), 
            "Last 24 Hours": pd.Timedelta(hours=24),
            "Last Week": pd.Timedelta(days=7)
        }
        cutoff_time = now_ist - time_deltas[time_filter]
        
        # Filter requests based on IST timestamps
        try:
            filtered_requests = []
            for idx, request in filtered_data.iterrows():
                try:
                    request_ist = convert_to_ist(request['timestamp'])
                    if request_ist.replace(tzinfo=None) > cutoff_time.replace(tzinfo=None):
                        filtered_requests.append(idx)
                except:
                    continue
            
            if filtered_requests:
                filtered_data = filtered_data.loc[filtered_requests]
            else:
                filtered_data = filtered_data.iloc[0:0]  # Empty dataframe with same structure
        except Exception as e:
            st.warning("Time filter not applied due to timestamp format issues")
    
    # Display filtered results
    if not filtered_data.empty:
        st.markdown(f"#### 📊 Showing {len(filtered_data)} requests")
        
        # Format the display data with IST timestamps
        display_data = filtered_data.copy()
        try:
            # Format timestamps in IST
            display_data['timestamp_formatted'] = display_data['timestamp'].apply(
                lambda x: format_ist_time(x, 'short')
            )
        except:
            # Fallback if timestamp formatting fails
            display_data['timestamp_formatted'] = display_data['timestamp'].astype(str).str[:16]
        
        # Add emoji columns
        display_data['Type'] = display_data['need'].apply(lambda x: f"{get_need_emoji(x)} {x}")
        display_data['Status Badge'] = display_data['status'].apply(lambda x: f"{'🆘' if x=='pending' else '🚧' if x=='ongoing' else '✅'} {x.title()}")
        
        # Reorder and select columns for display
        column_order = ['timestamp_formatted', 'Type', 'name', 'phone', 'address', 'Status Badge', 'responder']
        if 'urgency' in display_data.columns and not display_data['urgency'].isna().all():
            column_order.insert(2, 'urgency')
            
        display_columns = [col for col in column_order if col in display_data.columns]
        
        st.dataframe(
            display_data[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp_formatted": st.column_config.TextColumn("🕒 Time (IST)", width="small"),
                "Type": st.column_config.TextColumn("📋 Need", width="medium"),
                "name": st.column_config.TextColumn("👤 Name", width="medium"),
                "phone": st.column_config.TextColumn("📞 Phone", width="medium"),
                "address": st.column_config.TextColumn("📍 Location", width="large"),
                "urgency": st.column_config.TextColumn("⚡ Priority", width="small"),
                "Status Badge": st.column_config.TextColumn("📊 Status", width="small"),
                "responder": st.column_config.TextColumn("🤝 Volunteer", width="medium"),
                "extra": st.column_config.TextColumn("📝 Notes", width="large")
            }
        )
        
        # Enhanced download options
        st.markdown("### 📥 Export Data")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # CSV download
            csv = filtered_data.to_csv(index=False)
            st.download_button(
                label="📊 Download as CSV",
                data=csv,
                file_name=f"disaster_requests_{get_ist_now().strftime('%Y%m%d_%H%M%S')}_IST.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # JSON download for API integration
            json_data = filtered_data.to_json(orient='records', date_format='iso')
            st.download_button(
                label="💾 Download as JSON", 
                data=json_data,
                file_name=f"disaster_requests_{get_ist_now().strftime('%Y%m%d_%H%M%S')}_IST.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col3:
            # Emergency contact list
            emergency_contacts = filtered_data[filtered_data['status'].isin(['pending', 'ongoing'])][['name', 'phone', 'need', 'address']]
            if not emergency_contacts.empty:
                emergency_csv = emergency_contacts.to_csv(index=False)
                st.download_button(
                    label="🚨 Emergency Contacts",
                    data=emergency_csv, 
                    file_name=f"emergency_contacts_{get_ist_now().strftime('%Y%m%d_%H%M%S')}_IST.csv",
                    mime="text/csv",
                    use_container_width=True
                )
    else:
        st.markdown('<div class="help-card">', unsafe_allow_html=True)
        st.markdown("### 🔍 No Results Found")
        st.markdown("No requests match your current filter criteria. Try adjusting the filters above.")
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    """Enhanced main application function."""
    # Initialize the app
    initialize_app()
    
    # Enhanced app header
    st.markdown("""
    <div style='text-align: center; padding: 1rem 0; background: linear-gradient(90deg, #ff6b6b, #ee5a52); color: white; border-radius: 10px; margin-bottom: 2rem;'>
        <h1>🚨 Disaster Relief Hub</h1>
        <p style='margin: 0; font-size: 1.2rem;'>Connecting communities in times of crisis</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Enhanced sidebar
    st.sidebar.markdown("# 🧭 Navigation")
    st.sidebar.markdown("---")
    
    # Role selection with enhanced descriptions
    view = st.sidebar.selectbox(
        "👤 Select Your Role",
        ["Victim", "Volunteer", "Admin"],
        help="Choose your role to access the appropriate interface"
    )
    
    # Map view selection to internal names
    view_mapping = {
        "Victim": "Victim",
        "Volunteer": "Volunteer", 
        "Admin": "Admin"
    }
    selected_view = view_mapping[view]
    
    # Enhanced sidebar info
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📞 Emergency Contacts")
    st.sidebar.error("🚨 **Life-threatening emergency:** Call 100")
    st.sidebar.info("🏥 **Medical emergency:** Call emergency 108")

    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ About This System")
    st.sidebar.info(
        "🤝 **Mission:** Connect people who need help with volunteers who can provide assistance during disasters and emergencies.\n\n"
        "🔄 **How it works:** Submit requests → Volunteers respond → Help gets delivered\n\n"
        "🌍 **Community-driven:** Powered by local volunteers and emergency coordinators"
    )
    
    # System status indicator
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🟢 System Status")
    if st.session_state.initialized:
        st.sidebar.success("✅ System Online")
        st.sidebar.info(f"🕒 Last updated: {get_ist_now().strftime('%I:%M %p IST')}")
    else:
        st.sidebar.error("❌ System Initializing...")
    
    # Quick stats in sidebar (if admin or volunteer view)
    if selected_view in ["Volunteer", "Admin"]:
        try:
            all_requests = read_all_requests()
            if not all_requests.empty:
                pending_count = len(all_requests[all_requests['status'] == 'pending'])
                if pending_count > 0:
                    st.sidebar.markdown("---")
                    st.sidebar.markdown("### ⚡ Quick Status")
                    st.sidebar.warning(f"🆘 {pending_count} people need help!")
        except:
            pass  # Don't break if data isn't available yet
    
    # Display the selected view
    st.markdown("---")
    
    if selected_view == "Victim":
        victim_view()
    elif selected_view == "Volunteer":
        volunteer_view()
    elif selected_view == "Admin":
        admin_view()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <p>🤝 <strong>Disaster Relief Hub</strong> - Connecting communities in times of need</p>
        <p><small>Built with ❤️ for emergency response and community support</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
