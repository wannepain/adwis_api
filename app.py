import time
from flask import Flask, json, jsonify
from flask import request
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
import os
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
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

load_dotenv()


try:
    print(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_PATH"))
    firebase_admin.initialize_app(
        firebase_admin.credentials.Certificate(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS_PATH")
        )
    )
    print("Firebase app inicialized successfully")
except Exception as e:
    print(f"Error initializing Firebase app:{e}")
    raise

# app config
app = Flask(__name__)
app.config["CORS_HEADERS"] = "Content-Type"

cors = CORS(app)


@app.route("/")
def respond_test():
    return jsonify({"hello": "world"})


@app.route("/subscription/check", methods=["POST"])
@cross_origin()
def check_subscription_new():
    request_data = request.get_json()
    purchase_token = request_data.get("purchaseToken")
    uid = request_data.get("uid")  # ✅ Safer way to get uid

    if not purchase_token or not uid:
        return (
            jsonify(
                {
                    "success": False,
                    "subscriptionActive": False,
                    "nextCharge": None,
                    "message": "no purchase token or no uid",
                }
            ),
            400,
        )
    try:
        db = firestore.client()
        response = (
            service.purchases()
            .subscriptions()
            .get(
                packageName="com.wannepain.adwis",
                subscriptionId="adwis_unlimited",
                token=purchase_token,
            )
            .execute()
        )

        print("Subscription Details:", response)

        start_time = int(response["startTimeMillis"]) // 1000  # Convert to seconds
        end_time = (
            int(response["expiryTimeMillis"]) // 1000
        )  # ✅ FIXED: Convert expiry time

        current_time = int(time.time())

        subscription_active = (
            current_time < end_time
        )  # True if subscription is still active
        subscription_type = "Monthly" if subscription_active else "Free"

        # ✅ Update Firestore with latest subscription status
        db.collection("users").document(uid).update(
            {
                "subscriptionActive": subscription_active,
                "subscriptionType": subscription_type,
                "nextCharge": end_time if subscription_active else None,
            }
        )

        return jsonify(
            {
                "success": True,
                "subscriptionActive": subscription_active,
                "subscriptionType": subscription_type,
                "nextCharge": end_time if subscription_active else None,
                "message": "Subscription status updated",
            }
        )

    except Exception as e:
        print("Error:", e)
        return (
            jsonify(
                {
                    "success": False,
                    "subscriptionActive": False,
                    "nextCharge": None,
                    "message": "Internal server error",
                }
            ),
            500,
        )  # ✅ Return a


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(
        host="0.0.0.0",
        port=port,
    )
