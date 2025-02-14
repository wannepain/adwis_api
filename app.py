from flask import Flask, json, jsonify
from flask import request
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
import os
import stripe
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

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
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_ENDPOINT_SECRET")
# app config
app = Flask(__name__)
app.config["CORS_HEADERS"] = "Content-Type"

cors = CORS(app)


@app.route("/")
def respond_test():
    return jsonify({"hello": "world"})


@app.route("/api/sign", methods=["POST"])
@cross_origin()
def sign_in():  # first check if the customer exists, then act accordingly
    request_data = request.get_json()
    user = request_data.get("user")

    if not user:
        return jsonify({"success": False, "error": "User not specified"}), 400

    try:
        db = firestore.client()
        user_ref = db.collection("users").document(user["uid"]).get()

        if not user_ref.exists:
            return (
                jsonify({"success": False, "error": "User not found"}),
                404,
            )

        user_data = user_ref.to_dict()
        stored_customer_id = user_data.get(
            "stripeCustomerId",
        )  # Correct way to get the field

        if stored_customer_id:
            return jsonify({"success": True, "error": None}), 200

        # Create Stripe customer
        customer = stripe.Customer.create(email=user["email"], name=user["name"])

        # Store Stripe customer ID in Firestore

        db.collection("users").document(user["uid"]).set(
            {"stripeCustomerId": customer.id}, merge=True
        )

        return jsonify({"success": True, "error": None}), 200

    except Exception as e:
        print(f"error in sign_in \n {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/create-subscription", methods=["POST"])
@cross_origin()
def create_subscription():
    data = request.json
    if not data or not data["uid"]:
        return jsonify({"error": "no uid"}), 404

    user_id = data["uid"]

    # Get user from Firestore
    db = firestore.client()
    user_ref = db.collection("users").document(user_id).get()
    if not user_ref.exists:
        return jsonify({"error": "User not found"}), 404

    user_data = user_ref.to_dict()
    stripe_customer_id = user_data["stripeCustomerId"]

    # Create a Stripe subscription
    try:
        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[
                {"price": "price_1QqF1UGg7dfr3NgwqDeBnb1T"}
            ],  # Set Stripe Price ID here
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"],
        )

        return jsonify(
            {
                "subscriptionId": subscription.id,
                "clientSecret": subscription.latest_invoice.payment_intent.client_secret,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/cancel-subscription", methods=["POST"])
@cross_origin()
def cancel_subscription():
    data = request.json
    subscription_id = data["subscriptionId"]

    try:
        stripe.Subscription.delete(subscription_id)

        return jsonify({"message": "Subscription canceled successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/webhook", methods=["POST"])
def webhook():
    event = None
    payload = request.data

    try:
        event = json.loads(payload)
    except json.decoder.JSONDecodeError as e:
        print("⚠️  Webhook error while parsing basic request." + str(e))
        return jsonify(success=False)

    if endpoint_secret:
        sig_header = request.headers.get("stripe-signature")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except stripe.error.SignatureVerificationError as e:
            print("⚠️  Webhook signature verification failed." + str(e))
            return jsonify(success=False)

    db = firestore.client()

    if event["type"] == "invoice.payment_succeeded":
        subscription_id = event["data"]["object"]["subscription"]
        customer_id = event["data"]["object"]["customer"]

        print(f"subscription_id:{subscription_id}")
        print(f"customer_id:{customer_id}")
        users_ref = (
            db.collection("users")
            .where(filter=FieldFilter("stripeCustomerId", "==", customer_id))
            .stream()
        )

        for user_doc in users_ref:
            user_doc.reference.update(
                {"subscriptionActive": True, "subscriptionId": subscription_id}
            )

    elif event["type"] == "customer.subscription.deleted":
        customer_id = event["data"]["object"]["customer"]

        users_ref = (
            db.collection("users")
            .where(filter=FieldFilter("stripeCustomerId", "==", customer_id))
            .stream()
        )

        for user_doc in users_ref:
            user_doc.reference.update({"subscriptionActive": False})

    else:
        print("Unhandled event type {}".format(event["type"]))

    return jsonify(success=True)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(
        host="0.0.0.0",
        port=port,
    )
