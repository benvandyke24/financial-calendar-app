import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
import uuid
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------------
# Google Sheets Integration
# ---------------------------

HEADERS = ["date", "type", "description", "amount", "recurring_id", "recurring_active"]

def connect_to_google_sheet(sheet_name="Financial_Calendar_Data"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1

    # Ensure headers exist
    existing_values = sheet.get_all_values()
    if not existing_values:  
        sheet.append_row(HEADERS)
    else:
        # If first row isn't headers, set them
        if existing_values[0] != HEADERS:
            sheet.delete_rows(1)  # remove wrong headers
            sheet.insert_row(HEADERS, 1)
    
    return sheet

def load_data():
    sheet = connect_to_google_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(new_entry):
    sheet = connect_to_google_sheet()
    sheet.append_row([
        new_entry["date"],
        new_entry["type"],
        new_entry["description"],
        new_entry["amount"],
        new_entry["recurring_id"],
        new_entry["recurring_active"]
    ])

# ---------------------------
# FinanceManager
# ---------------------------

class FinanceManager:
    def __init__(self):
        try:
            self.data = load_data()
            if self.data.empty:
                self.data = pd.DataFrame(columns=HEADERS)
        except Exception:
            self.data = pd.DataFrame(columns=HEADERS)

    def save(self, new_entry):
        save_data(new_entry)
        self.data = load_data()

    def add_transaction(self, date, ttype, desc, amount, recurring=False):
        new_entry = {
            "date": pd.to_datetime(date).strftime('%Y-%m-%d'),
            "type": ttype,
            "description": desc,
            "amount": amount,
            "recurring_id": None,
            "recurring_active": True
        }
        if recurring and ttype == "Bill":
            new_entry["recurring_id"] = f"{desc}-{uuid.uuid4()}"
        self.save(new_entry)

    def get_transactions_by_date(self, date):
        data = load_data()
        if data.empty:
            return data
        data["date"] = pd.to_datetime(data["date"], errors='coerce')
        return data[data["date"].dt.date == pd.to_datetime(date).date()]

    def get_monthly_total(self, year, month):
        data = load_data()
        if data.empty:
            return 0
        data["date"] = pd.to_datetime(data["date"], errors='coerce')
        month_data = data[
            (data["date"].dt.year == year) & (data["date"].dt.month == month)
        ]
        return sum(row["amount"] if row["type"] == "Income" else -row["amount"] for _, row in month_data.iterrows())

    def get_weekly_total(self, week_dates):
        data = load_data()
        if data.empty:
            return 0
        data["date"] = pd.to_datetime(data["date"], errors='coerce')
        week_data = data[data["date"].dt.date.isin(week_dates)]
        return sum(row["amount"] if row["type"] == "Income" else -row["amount"] for _, row in week_data.iterrows())

# ---------------------------
# Streamlit App
# ---------------------------

st.set_page_config(layout="wide")
st.title("📅 Financial Calendar")

manager = FinanceManager()

# Password protection
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    with st.form("login_form"):
        password = st.text_input("Enter password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if password == st.secrets.get("app_password", "changeme"):
                st.session_state.authenticated = True
                st.success("✅ Login successful!")
            else:
                st.error("Incorrect password")
    st.stop()

# Logout
if st.button("Logout"):
    st.session_state.authenticated = False
    st.rerun()

# Calendar state
today = datetime.today()
if "current_month" not in st.session_state:
    st.session_state.current_month = today.month
if "current_year" not in st.session_state:
    st.session_state.current_year = today.year
if "selected_day" not in st.session_state:
    st.session_state.selected_day = None

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅️ Previous"):
        if st.session_state.current_month == 1:
            st.session_state.current_month = 12
            st.session_state.current_year -= 1
        else:
            st.session_state.current_month -= 1
with col3:
    if st.button("Next ➡️"):
        if st.session_state.current_month == 12:
            st.session_state.current_month = 1
            st.session_state.current_year += 1
        else:
            st.session_state.current_month += 1

st.subheader(f"{calendar.month_name[st.session_state.current_month]} {st.session_state.current_year}")

# Calendar layout with weekly total column
weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(st.session_state.current_year, st.session_state.current_month)
for week in weeks:
    cols = st.columns(8)
    week_dates = []
    for i, day in enumerate(week):
        week_dates.append(day)
        with cols[i]:
            st.markdown(f"### {day.day}")
            day_data = manager.get_transactions_by_date(day)
            for _, row in day_data.iterrows():
                color = "blue" if row["type"] == "Income" else ("darkgreen" if row["type"] == "Bill" else "red")
                st.markdown(f"<span style='color:{color}'>{row['description']} ${row['amount']:.2f}</span>", unsafe_allow_html=True)
            if st.button("➕", key=f"select-{day}"):
                st.session_state.selected_day = str(day)
    with cols[7]:
        week_total = manager.get_weekly_total(week_dates)
        st.markdown(f"**Weekly Total:** ${week_total:.2f}")

# Transaction input form
if st.session_state.selected_day:
    st.write(f"Adding transaction for **{st.session_state.selected_day}**")
    with st.form(key="transaction_form"):
        ttype = st.selectbox("Type", ["Income", "Expense", "Bill"])
        desc = st.text_input("Description")
        amount = st.number_input("Amount", min_value=0.0, step=0.01)
        recurring = st.checkbox("Recurring (Bills only)")
        submit = st.form_submit_button("Add Transaction")
        if submit:
            manager.add_transaction(st.session_state.selected_day, ttype, desc, amount, recurring)
            st.success("Transaction added!")
            st.session_state.selected_day = None
            st.rerun()

# Monthly total
month_total = manager.get_monthly_total(st.session_state.current_year, st.session_state.current_month)
st.subheader(f"Monthly Net: ${month_total:.2f}")
