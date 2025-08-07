import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
import uuid
import gspread
from gspread.exceptions import SpreadsheetNotFound
from oauth2client.service_account import ServiceAccountCredentials
from finance_manager import FinanceManager  # Ensure your FinanceManager is in a file named finance_manager.py




HEADERS = ["date", "type", "description", "amount", "recurring_id", "recurring_active"]

# ---------------------------
# Google Sheets Setup
# ---------------------------
def connect_to_google_sheet(sheet_name="Financial_Calendar_Data"):
    """Connect to Google Sheets, create spreadsheet/headers if missing."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)

    try:
        spreadsheet = client.open(sheet_name)
    except SpreadsheetNotFound:
        spreadsheet = client.create(sheet_name)
        spreadsheet.share(st.secrets["gcp_service_account"]["client_email"], perm_type="user", role="writer")

    sheet = spreadsheet.sheet1
    values = sheet.get_all_values()
    if not values or values[0] != HEADERS:
        sheet.clear()
        sheet.append_row(HEADERS)

    return sheet

@st.cache_data(ttl=60)
def load_data_cached():
    """Cached Google Sheet loader to reduce API calls."""
    sheet = connect_to_google_sheet()
    values = sheet.get_all_values()
    if len(values) <= 1:
        return pd.DataFrame(columns=HEADERS)

    df = pd.DataFrame(values[1:], columns=values[0])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def save_data(new_entry):
    """Appends a new transaction to the sheet."""
    sheet = connect_to_google_sheet()
    sheet.append_row([
        new_entry["date"],
        new_entry["type"],
        new_entry["description"],
        new_entry["amount"],
        new_entry["recurring_id"],
        new_entry["recurring_active"]
    ])
    load_data_cached.clear()  # Clear cache after writing

# ---------------------------
# FinanceManager
# ---------------------------
class FinanceManager:
    def __init__(self):
        self.data = load_data_cached()

    def add_transaction(self, date, ttype, desc, amount, recurring=False):
        new_entry = {
            "date": pd.to_datetime(date).strftime('%Y-%m-%d'),
            "type": ttype,
            "description": desc,
            "amount": float(amount),
            "recurring_id": f"{desc}-{uuid.uuid4()}" if recurring and ttype == "Bill" else None,
            "recurring_active": True
        }
        save_data(new_entry)
        self.data = load_data_cached()

    def get_transactions_by_date(self, date):
        if self.data.empty:
            return self.data
        return self.data[self.data["date"].dt.date == pd.to_datetime(date).date()]

    def get_monthly_total(self, year, month):
        if self.data.empty:
            return 0
        month_data = self.data[(self.data["date"].dt.year == year) & (self.data["date"].dt.month == month)]
        return month_data.apply(lambda row: row["amount"] if row["type"] == "Income" else -row["amount"], axis=1).sum()

    def get_weekly_total(self, week_dates):
        if self.data.empty:
            return 0
        week_data = self.data[self.data["date"].dt.date.isin(week_dates)]
        return week_data.apply(lambda row: row["amount"] if row["type"] == "Income" else -row["amount"], axis=1).sum()

def get_transactions_by_date(date_str):
    # Returns a list of transactions for the given date_str (e.g., "2025-08-01")
    return [t for t in all_transactions if t['Date'] == date_str]

def add_transaction_callback(date_str):
    st.session_state['selected_date'] = date_str
    st.session_state['show_form'] = True

def get_weekly_total(start_date, end_date):
    total = sum(float(t['Amount']) for t in all_transactions if start_date <= t['Date'] <= end_date)
    return total


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

# # Calendar layout with borders and improved add button placement
# weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(
#     st.session_state.current_year, st.session_state.current_month
# )

# for week in weeks:
#     cols = st.columns(8)
#     week_dates = []

#     for i, day in enumerate(week):
#         week_dates.append(day)
#         with cols[i]:
#             day_data = manager.get_transactions_by_date(day)

#             # Border container
#             st.markdown(
#                 f"""
#                 <div style="
#                     border: 1px solid #ccc;
#                     border-radius: 8px;
#                     padding: 6px;
#                     min-height: 100px;
#                 ">
#                     <div style="display: flex; justify-content: space-between; align-items: center;">
#                         <strong>{day.day}</strong>
#                         <form action="#" method="post">
#                             <button type="button" 
#                                 style="
#                                     background-color: #f0f0f0;
#                                     border: none;
#                                     border-radius: 4px;
#                                     cursor: pointer;
#                                     padding: 0 6px;
#                                 "
#                                 onClick="window.location.href='?select={day}'">
#                                 ➕
#                             </button>
#                         </form>
#                     </div>
#                 """,
#                 unsafe_allow_html=True,
#             )

#             # Show transactions inside border
#             for _, row in day_data.iterrows():
#                 color = "blue" if row["type"] == "Income" else ("darkgreen" if row["type"] == "Bill" else "red")
#                 st.markdown(
#                     f"<div style='color:{color}; margin-top: 4px;'>{row['description']} ${row['amount']:.2f}</div>",
#                     unsafe_allow_html=True
#                 )

#             st.markdown("</div>", unsafe_allow_html=True)

#             # Handle button click with session state
#             if f"select-{day}" not in st.session_state:
#                 st.session_state[f"select-{day}"] = False
#             if st.query_params.get("select") == [str(day)]:
#                 st.session_state.selected_day = str(day)

#     with cols[7]:
#         week_total = manager.get_weekly_total(week_dates)
#         st.markdown(
#             f"""
#             <div style="border: 1px solid #aaa; border-radius: 8px; padding: 8px; text-align: center;">
#                 <strong>Weekly Total:</strong><br>
#                 ${week_total:.2f}
#             </div>
#             """,
#             unsafe_allow_html=True
#         )

# # Transaction input form
# if st.session_state.selected_day:
#     st.write(f"Adding transaction for **{st.session_state.selected_day}**")
#     with st.form(key="transaction_form"):
#         ttype = st.selectbox("Type", ["Income", "Expense", "Bill"])
#         desc = st.text_input("Description")
#         amount = st.number_input("Amount", min_value=0.0, step=0.01)
#         recurring = st.checkbox("Recurring (Bills only)")
#         submit = st.form_submit_button("Add Transaction")
#         if submit:
#             manager.add_transaction(st.session_state.selected_day, ttype, desc, amount, recurring)
#             st.success("Transaction added!")
#             st.session_state.selected_day = None
#             st.rerun()

# # Monthly total
# month_total = manager.get_monthly_total(st.session_state.current_year, st.session_state.current_month)
# st.subheader(f"Monthly Net: ${month_total:.2f}")

# Initialize manager
manager = FinanceManager()

# App title
st.title("📅 Financial Calendar")

# Get current date and selected month/year
now = datetime.now()
selected_year = st.sidebar.selectbox("Select Year", list(range(now.year - 5, now.year + 6)), index=5)
selected_month = st.sidebar.selectbox("Select Month", list(range(1, 13)), index=now.month - 1)

# Determine month layout
first_day = datetime(selected_year, selected_month, 1)
first_weekday = first_day.weekday()
days_in_month = monthrange(selected_year, selected_month)[1]
dates = [first_day + timedelta(days=i) for i in range(days_in_month)]

# Pad dates to align calendar correctly
padding_start = [""] * first_weekday
calendar_dates = padding_start + dates
while len(calendar_dates) % 7 != 0:
    calendar_dates.append("")

# Display calendar as grid
for i in range(0, len(calendar_dates), 7):
    cols = st.columns(7, gap="small")
    for j, day in enumerate(calendar_dates[i:i+7]):
        with cols[j]:
            if day != "":
                st.markdown(f"<div style='border:1px solid #ccc; padding:6px; height:170px'>", unsafe_allow_html=True)
                st.markdown(f"**{day.day}**")
                if st.button("➕", key=f"btn-{day}"):
                    st.session_state["selected_day"] = day
                    st.session_state["show_form"] = True
                day_data = manager.get_transactions_by_date(day)
                for _, row in day_data.iterrows():
                    color = "green" if row['type'] == "Income" else "red"
                    amount_display = f"<span style='color:{color}'>${row['amount']:.2f}</span>"
                    st.markdown(f"{row['description']}<br/>{amount_display}", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='padding:6px; height:170px'></div>", unsafe_allow_html=True)

# Transaction form
if st.session_state.get("show_form"):
    selected_day = st.session_state["selected_day"]
    with st.form("Add Transaction"):
        st.markdown(f"### Add Transaction for {selected_day.strftime('%Y-%m-%d')}")
        ttype = st.selectbox("Type", ["Income", "Expense", "Bill"])
        desc = st.text_input("Description")
        amount = st.number_input("Amount", min_value=0.0, format="%.2f")
        recurring = st.checkbox("Recurring" if ttype == "Bill" else "", value=False, disabled=(ttype != "Bill"))
        submitted = st.form_submit_button("Add")
        if submitted:
            manager.add_transaction(selected_day, ttype, desc, amount, recurring)
            st.success("Transaction added!")
            st.session_state["show_form"] = False
            st.experimental_rerun()

# Weekly and Monthly Totals
st.sidebar.markdown("---")
this_month_total = manager.get_monthly_total(selected_year, selected_month)
st.sidebar.metric("Monthly Net Total", f"${this_month_total:.2f}")

# Weekly total breakdown
st.sidebar.markdown("### Weekly Totals")
for i in range(0, len(calendar_dates), 7):
    week = calendar_dates[i:i+7]
    week_dates = [d.date() for d in week if d != ""]
    if week_dates:
        total = manager.get_weekly_total(week_dates)
        week_str = f"Week {week_dates[0]} to {week_dates[-1]}"
        st.sidebar.write(f"{week_str}: ${total:.2f}")

