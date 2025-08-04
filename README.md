# 📅 Financial Calendar App

This is a Streamlit-based financial calendar that integrates with Google Sheets for persistent cloud storage.

## 🚀 Features
- Calendar-based expense and income tracking
- Password-protected login
- Cloud storage with Google Sheets
- Add, view, and manage transactions

## 🛠️ Setup
1. Clone this repository.
2. Create a Google Cloud Service Account and download the JSON key.
3. Share your Google Sheet (`Financial_Calendar_Data`) with the service account email.
4. Deploy on Streamlit Cloud and add your credentials to **Secrets**.

## 🔑 Secrets Example
```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"

app_password = "Tibblef15"
