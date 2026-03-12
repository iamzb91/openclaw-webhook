#!/usr/bin/env python3
"""
OpenClaw Meta Webhook Receiver + WhatsApp Coexistence Signup
"""

import os
import json
import time
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("webhook")

META_APP_ID = os.environ.get("META_APP_ID", "1583882806167359")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "openclaw_verify_2026")
WA_CONFIG_ID = os.environ.get("WA_CONFIG_ID", "")

DATA_DIR = os.environ.get("DATA_DIR", "/tmp/openclaw_data")
os.makedirs(DATA_DIR, exist_ok=True)
MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")


def load_messages():
    if os.path.exists(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE) as f:
                return json.load(f)
        except:
            pass
    return []


def save_message(msg):
    messages = load_messages()
    messages.append(msg)
    if len(messages) > 10000:
        messages = messages[-10000:]
    with open(MESSAGES_FILE, "w") as f:
        json.dump(messages, f, indent=2)
    return len(messages)


def verify_signature(payload, signature):
    if not META_APP_SECRET or not signature:
        return True
    expected = hmac.new(
        META_APP_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


SIGNUP_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw - WhatsApp Coexistence Setup</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { max-width: 600px; padding: 40px; text-align: center; }
        h1 { font-size: 28px; color: #25D366; margin-bottom: 12px; }
        .subtitle { font-size: 16px; color: #888; margin-bottom: 32px; line-height: 1.5; }
        .btn-whatsapp { background: #25D366; color: #fff; border: none; border-radius: 8px; padding: 16px 40px; font-size: 18px; font-weight: 600; cursor: pointer; transition: all 0.2s; display: inline-block; }
        .btn-whatsapp:hover { background: #20bd5a; transform: translateY(-1px); }
        .btn-whatsapp:disabled { background: #333; color: #666; cursor: not-allowed; transform: none; }
        .status { margin-top: 24px; padding: 16px; border-radius: 8px; display: none; font-size: 14px; line-height: 1.5; }
        .status.success { display: block; background: #0d2818; border: 1px solid #25D366; color: #25D366; }
        .status.error { display: block; background: #2d0a0a; border: 1px solid #e74c3c; color: #e74c3c; }
        .status.info { display: block; background: #0a1a2d; border: 1px solid #3498db; color: #3498db; }
        .steps { text-align: left; margin: 24px 0; padding: 20px; background: #111; border-radius: 8px; border: 1px solid #222; }
        .steps h3 { color: #25D366; margin-bottom: 12px; font-size: 16px; }
        .steps ol { padding-left: 20px; color: #aaa; font-size: 14px; line-height: 1.8; }
        .no-config { background: #2d1a0a; border: 1px solid #e67e22; color: #e67e22; padding: 16px; border-radius: 8px; margin-bottom: 24px; font-size: 14px; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WhatsApp Coexistence Setup</h1>
        <p class="subtitle">Connect your WhatsApp Business App number to the Cloud API.  
Keep using the app normally - messages sync to both.</p>
        {% if not config_id %}
        <div class="no-config">
            <strong>Configuration ID needed.</strong>  

            Go to your Meta App Dashboard, Facebook Login for Business, Configurations, Create from template
            "WhatsApp Embedded Signup Configuration With 60 Expiration Token".
            Copy the Configuration ID and set it as the WA_CONFIG_ID environment variable on Render.
        </div>
        {% endif %}
        <div class="steps">
            <h3>What happens when you click the button:</h3>
            <ol>
                <li>Facebook login popup opens</li>
                <li>Select "Connect your existing WhatsApp Business App"</li>
                <li>Enter your phone number (980-213-7398)</li>
                <li>You'll get a verification code - enter it in your WhatsApp Business App</li>
                <li>Confirm in the app to share chat history</li>
                <li>Done! Your number works on both the app AND the API</li>
            </ol>
        </div>
        <button id="signup-btn" class="btn-whatsapp" onclick="launchWhatsAppSignup()" {% if not config_id %}disabled{% endif %}>Connect WhatsApp Business</button>
        <div id="status" class="status"></div>
    </div>
    <script async defer crossorigin="anonymous" src="https://connect.facebook.net/en_US/sdk.js"></script>
    <script>
        const APP_ID = '{{ app_id }}';
        const CONFIG_ID = '{{ config_id }}';
        window.fbAsyncInit = function( ) {
            FB.init({ appId: APP_ID, autoLogAppEvents: true, xfbml: true, version: 'v25.0' });
        };
        window.addEventListener('message', (event) => {
            if (!event.origin.endsWith('facebook.com')) return;
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'WA_EMBEDDED_SIGNUP') {
                    if (data.event === 'FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING' || data.event === 'FINISH') {
                        const phoneId = data.data?.phone_number_id;
                        const wabaId = data.data?.waba_id;
                        showStatus('success', '<strong>WhatsApp connected!</strong>  
Phone Number ID: ' + phoneId + '  
WABA ID: ' + wabaId);
                        fetch('/api/wa-signup-complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone_number_id: phoneId, waba_id: wabaId, business_id: data.data?.business_id, event: data.event }) });
                    } else if (data.event === 'CANCEL') {
                        showStatus('error', 'Setup was cancelled.');
                    }
                }
            } catch (e) {}
        });
        const fbLoginCallback = (response) => {
            if (response.authResponse) {
                const code = response.authResponse.code;
                showStatus('info', 'Exchanging token... please wait.');
                fetch('/api/exchange-token', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: code }) })
                .then(r => r.json())
                .then(data => {
                    if (data.success) { showStatus('success', '<strong>Token exchanged successfully!</strong>  
WhatsApp Cloud API is now active.'); }
                    else { showStatus('error', 'Token exchange failed: ' + (data.error || 'Unknown error')); }
                })
                .catch(err => { showStatus('error', 'Network error: ' + err.message); });
            } else { showStatus('error', 'Login was not completed.'); }
        };
        function launchWhatsAppSignup() {
            if (!CONFIG_ID) { showStatus('error', 'Configuration ID is not set.'); return; }
            FB.login(fbLoginCallback, { config_id: CONFIG_ID, response_type: 'code', override_default_response_type: true, extras: { setup: {}, featureType: 'whatsapp_business_app_onboarding', sessionInfoVersion: '3' } });
        }
        function showStatus(type, html) { const el = document.getElementById('status'); el.className = 'status ' + type; el.innerHTML = html; }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(SIGNUP_PAGE, app_id=META_APP_ID, config_id=WA_CONFIG_ID)


@app.route("/health")
def health():
    msg_count = len(load_messages())
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "messages_stored": msg_count, "wa_configured": bool(WA_CONFIG_ID)})


@app.route("/api/exchange-token", methods=["POST"])
def exchange_token():
    data = request.get_json()
    code = data.get("code")
    if not code:
        return jsonify({"success": False, "error": "No code provided"}), 400
    if not META_APP_SECRET:
        return jsonify({"success": False, "error": "App secret not configured"}), 500
    try:
        resp = requests.get("https://graph.facebook.com/v25.0/oauth/access_token", params={"client_id": META_APP_ID, "client_secret": META_APP_SECRET, "code": code}, timeout=15 )
        result = resp.json()
        if "access_token" in result:
            token = result["access_token"]
            log.info(f"Token exchanged successfully! Token starts with: {token[:20]}...")
            state_file = os.path.join(DATA_DIR, "wa_token.json")
            with open(state_file, "w") as f:
                json.dump({"access_token": token, "exchanged_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)
            return jsonify({"success": True, "token_prefix": token[:20]})
        else:
            log.error(f"Token exchange failed: {result}")
            return jsonify({"success": False, "error": result.get("error", {}).get("message", "Unknown")}), 400
    except Exception as e:
        log.error(f"Token exchange error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/wa-signup-complete", methods=["POST"])
def wa_signup_complete():
    data = request.get_json()
    log.info(f"WhatsApp signup complete: {json.dumps(data, indent=2)}")
    state_file = os.path.join(DATA_DIR, "wa_signup.json")
    with open(state_file, "w") as f:
        json.dump({**data, "completed_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)
    return jsonify({"success": True})


@app.route("/webhook", methods=["GET"])
def webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        log.info(f"Webhook verified! Challenge: {challenge}")
        return challenge, 200
    else:
        log.warning(f"Webhook verification failed. Token: {token}")
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_receive():
    payload = request.get_data()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if META_APP_SECRET and signature:
        if not verify_signature(payload, signature):
            log.warning("Invalid webhook signature!")
            return "Invalid signature", 403
    body = request.get_json()
    if not body:
        return "OK", 200
    obj_type = body.get("object", "")
    entries = body.get("entry", [])
    log.info(f"Webhook received: object={obj_type}, entries={len(entries)}")
    for entry in entries:
        if obj_type == "whatsapp_business_account":
            process_whatsapp_entry(entry)
        elif obj_type == "instagram":
            process_instagram_entry(entry)
        elif obj_type == "page":
            process_messenger_entry(entry)
        else:
            log.info(f"Unknown webhook object type: {obj_type}")
    return "OK", 200


def process_whatsapp_entry(entry):
    changes = entry.get("changes", [])
    for change in changes:
        field = change.get("field", "")
        value = change.get("value", {})
        if field == "messages":
            contacts = value.get("contacts", [])
            messages = value.get("messages", [])
            metadata = value.get("metadata", {})
            contact_map = {c.get("wa_id", ""): c.get("profile", {}).get("name", "") for c in contacts}
            for msg in messages:
                wa_id = msg.get("from", "")
                msg_record = {"platform": "whatsapp", "received_at": datetime.now(timezone.utc).isoformat(), "timestamp": msg.get("timestamp", ""), "from_number": wa_id, "from_name": contact_map.get(wa_id, ""), "message_id": msg.get("id", ""), "type": msg.get("type", ""), "text": msg.get("text", {}).get("body", "") if msg.get("type") == "text" else f"[{msg.get('type', 'unknown')}]", "phone_number_id": metadata.get("phone_number_id", "")}
                count = save_message(msg_record)
                log.info(f"WA message from {msg_record['from_name']} ({wa_id}): {msg_record['text'][:80]}... [total: {count}]")
        elif field == "history":
            log.info("WA history sync event received")
            messages = value.get("messages", [])
            for msg in messages:
                msg_record = {"platform": "whatsapp", "source": "history_sync", "received_at": datetime.now(timezone.utc).isoformat(), "timestamp": msg.get("timestamp", ""), "from_number": msg.get("from", ""), "message_id": msg.get("id", ""), "type": msg.get("type", ""), "text": msg.get("text", {}).get("body", "") if msg.get("type") == "text" else f"[{msg.get('type', 'unknown')}]"}
                save_message(msg_record)
        elif field == "smb_message_echoes":
            log.info("WA Business App message echo received")
            messages = value.get("messages", [])
            for msg in messages:
                msg_record = {"platform": "whatsapp", "source": "app_echo", "received_at": datetime.now(timezone.utc).isoformat(), "timestamp": msg.get("timestamp", ""), "to_number": msg.get("to", ""), "message_id": msg.get("id", ""), "type": msg.get("type", ""), "text": msg.get("text", {}).get("body", "") if msg.get("type") == "text" else f"[{msg.get('type', 'unknown')}]"}
                save_message(msg_record)
        else:
            log.info(f"WA webhook field: {field}")


def process_instagram_entry(entry):
    messaging = entry.get("messaging", [])
    for event in messaging:
        sender = event.get("sender", {})
        recipient = event.get("recipient", {})
        message = event.get("message", {})
        if message:
            msg_record = {"platform": "instagram", "received_at": datetime.now(timezone.utc).isoformat(), "timestamp": str(event.get("timestamp", "")), "from_id": sender.get("id", ""), "to_id": recipient.get("id", ""), "message_id": message.get("mid", ""), "text": message.get("text", ""), "is_echo": message.get("is_echo", False)}
            count = save_message(msg_record)
            direction = "echo/sent" if msg_record["is_echo"] else "received"
            log.info(f"IG message ({direction}) from {sender.get('id', '?')}: {msg_record['text'][:80]}... [total: {count}]")
    for change in entry.get("changes", []):
        log.info(f"IG change field: {change.get('field', '')}")


def process_messenger_entry(entry):
    messaging = entry.get("messaging", [])
    for event in messaging:
        sender = event.get("sender", {})
        recipient = event.get("recipient", {})
        message = event.get("message", {})
        if message:
            msg_record = {"platform": "messenger", "received_at": datetime.now(timezone.utc).isoformat(), "timestamp": str(event.get("timestamp", "")), "from_id": sender.get("id", ""), "to_id": recipient.get("id", ""), "message_id": message.get("mid", ""), "text": message.get("text", ""), "is_echo": message.get("is_echo", False)}
            count = save_message(msg_record)
            direction = "echo/sent" if msg_record["is_echo"] else "received"
            log.info(f"FB message ({direction}) from {sender.get('id', '?')}: {msg_record['text'][:80]}... [total: {count}]")


@app.route("/api/messages")
def get_messages():
    messages = load_messages()
    platform = request.args.get("platform")
    if platform:
        messages = [m for m in messages if m.get("platform") == platform]
    since = request.args.get("since")
    if since:
        messages = [m for m in messages if m.get("received_at", "") > since]
    limit = request.args.get("limit", 100, type=int)
    messages = messages[-limit:]
    return jsonify({"count": len(messages), "messages": messages})


@app.route("/api/messages/summary")
def messages_summary():
    messages = load_messages()
    summary = {}
    for m in messages:
        p = m.get("platform", "unknown")
        summary[p] = summary.get(p, 0) + 1
    return jsonify({"total": len(messages), "by_platform": summary, "last_message": messages[-1] if messages else None})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log.info(f"Starting OpenClaw Webhook Receiver on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
