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

def connect_to_google_sheet(sheet_name="Financial_Calendar_Data"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    return sheet

def load_data():
    sheet = connect_to_google_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(df):
    sheet = connect_to_google_sheet()
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# ---------------------------
# FinanceManager with Google Sheets
# ---------------------------

class FinanceManager:
    def __init__(self):
        try:
            self.data = load_data()
            if self.data.empty:
                self.data = pd.DataFrame(columns=["date", "type", "description", "amount", "recurring_id", "recurring_active"])
        except Exception:
            self.data = pd.DataFrame(columns=["date", "type", "description", "amount", "recurring_id", "recurring_active"])

    def save(self):
        save_data(self.data)

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
        self.data = pd.concat([self.data, pd.DataFrame([new_entry])], ignore_index=True)
        self.save()

    def get_transactions_by_date(self, date):
        date = pd.to_datetime(date).date()
        self.data["date"] = pd.to_datetime(self.data["date"], errors='coerce')
        return self.data[self.data["date"].dt.date == date]

    def get_monthly_total(self, year, month):
        self.data["date"] = pd.to_datetime(self.data["date"], errors='coerce')
        month_data = self.data[
            (self.data["date"].dt.year == year) & (self.data["date"].dt.month == month)
        ]
        total = 0
        for _, row in month_data.iterrows():
            total += row["amount"] if row["type"] == "Income" else -row["amount"]
        return total

# ---------------------------
# Streamlit App
# ---------------------------

st.set_page_config(layout="wide")
st.title("📅 Financial Calendar")

manager = FinanceManager()

# ---------------------------
# Password protection
# ---------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("Enter password", type="password")
    if st.button("Login"):
        if password == st.secrets.get("app_password", "changeme"):
            st.session_state.authenticated = True
            st.rerun()  # safer rerun
        else:
            st.error("Incorrect password")
    st.stop()

# Logout button
if st.session_state.authenticated:
    if st.button("🔒 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# ---------------------------
# Navigation
# ---------------------------
today = datetime.today()
if "current_month" not in st.session_state:
    st.session_state.current_month = today.month
if "current_year" not in st.session_state:
    st.session_state.current_year = today.year

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

# ---------------------------
# Layout: Calendar (left) + Weekly Summary (right)
# ---------------------------
left_col, right_col = st.columns([3, 1])

# Build calendar grid
with left_col:
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(st.session_state.current_year, st.session_state.current_month)

    # Calculate weekly totals
    weekly_totals = []
    for week in weeks:
        week_total = 0
        for day in week:
            day_data = manager.get_transactions_by_date(day)
            for _, row in day_data.iterrows():
                week_total += row["amount"] if row["type"] == "Income" else -row["amount"]
        weekly_totals.append(week_total)

    for week_index, week in enumerate(weeks):
        cols = st.columns(8)  # 7 days + weekly total
        for i, day in enumerate(week):
            with cols[i]:
                st.markdown(f"### {day.day}")
                day_data = manager.get_transactions_by_date(day)

                # Daily sum
                day_total = 0
                for _, row in day_data.iterrows():
                    color = "blue" if row["type"] == "Income" else ("darkgreen" if row["type"] == "Bill" else "red")
                    st.markdown(f"<span style='color:{color}'>{row['description']} ${row['amount']:.2f}</span>", unsafe_allow_html=True)
                    day_total += row["amount"] if row["type"] == "Income" else -row["amount"]

                st.markdown(f"**Daily Total: ${day_total:.2f}**")

                # Add button
                if st.button("➕", key=f"add-{day}"):
                    with st.form(key=f"form-{day}"):
                        ttype = st.selectbox("Type", ["Income", "Expense", "Bill"])
                        desc = st.text_input("Description")
                        amount = st.number_input("Amount", min_value=0.0, step=0.01)
                        recurring = st.checkbox("Recurring (Bills only)")
                        submit = st.form_submit_button("Add")
                        if submit:
                            manager.add_transaction(day, ttype, desc, amount, recurring)
                            st.success("Transaction added!")
                            st.rerun()

        # Weekly total column
        with cols[7]:
            st.markdown("### Week Total")
            st.markdown(f"**${weekly_totals[week_index]:.2f}**")

# ---------------------------
# Weekly summary panel (right)
# ---------------------------
with right_col:
    st.markdown("## 📊 Weekly Summary")
    for i, total in enumerate(weekly_totals):
        st.markdown(f"**Week {i+1}: ${total:.2f}**")

# ---------------------------
# Monthly total
# ---------------------------
month_total = manager.get_monthly_total(st.session_state.current_year, st.session_state.current_month)
st.subheader(f"Monthly Net: ${month_total:.2f}")
