from googleapiclient.discovery import build
from google.oauth2 import service_account

# Path to your service account JSON key file
SERVICE_ACCOUNT_FILE = "C:/Users/marek/adwis_v2/adwis_api/adwis_secret2.json"

# Define the required scope
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

# Authenticate with the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# Build the API client
service = build("androidpublisher", "v3", credentials=credentials)

# Replace with your actual values
PACKAGE_NAME = "com.wannepain.adwis"
SUBSCRIPTION_ID = "adwis_unlimited"
PURCHASE_TOKEN = "ajnmmejffclbaclkhpidlhak.AO-J1OwP0O9-BxGAj7o27BWfzKwQmTv9EPVK4ZHzg-9pZ8o-QOkRxaC0Pe2ByK0fHncag8ox-7IEyXUkRKqedpEJYkrSvU8GfA"

try:
    response = (
        service.purchases()
        .subscriptions()
        .get(
            packageName=PACKAGE_NAME,
            subscriptionId=SUBSCRIPTION_ID,
            token=PURCHASE_TOKEN,
        )
        .execute()
    )

    print("Subscription Details:", response)

except Exception as e:
    print("Error:", e)
