from flask import Flask, request, jsonify
from dotenv import load_dotenv
import requests
import os
import hashlib
import hmac
import time
app = Flask(__name__)

# Env Variables
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_API_URL_ALL = os.getenv("SLACK_API_URL_ALL")
SLACK_API_URL_EPHEMERAL = os.getenv("SLACK_API_URL_EPHEMERAL")
frozen_repos = set()

# Only process requests from Slack
def verify_slack_request(req):
    timestamp = req.headers.get("X-Slack-Request-Timestamp")
    slack_signature = req.headers.get("X-Slack-Signature")
    if not timestamp or not slack_signature:
        return False 
    if abs(time.time() - int(timestamp)) > 300:
        return False  
    body = req.get_data(as_text=True)
    base = f"v0:{timestamp}:{body}"
    computed_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed_signature, slack_signature)

# Helper for sending Slack
def send_slack_message(channel_id, message, ephemeral, user_id):
    payload = {"channel": channel_id, "text": message}
    if ephemeral: 
        payload["user"] = user_id
    response = requests.post(
        SLACK_API_URL_EPHEMERAL if ephemeral else SLACK_API_URL_ALL,
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json=payload
    )   
    if response.json().get("ok"):
        return "", 200
    else:
        return "Error occurred", 500
    

@app.route("/slack/command", methods=["POST"])
def slack_command():
    if not verify_slack_request(request):
        return jsonify({"error": "Unauthorized request"}), 401
    
    # Extract command, parameters, and the channel id
    data = request.form
    command = data.get("command")
    command_text = data.get("text", "").strip()
    channel_id = data.get("channel_id")
    user_id = data.get("user_id")
    
    # Available commands
    command_handlers = {
        "/help": lambda: handle_help(channel_id, user_id),
        "/check": lambda: handle_check(channel_id, user_id),
        "/freeze": lambda: handle_freeze(command_text,channel_id, user_id),
        "/unfreeze": lambda: handle_unfreeze(command_text,channel_id, user_id)
    }
    
    if command in command_handlers:
        return command_handlers[command]()

    # Invalid command handling
    return jsonify({"text": "Unknown command 🤖"}), 400

def handle_help(channel_id, user_id):
    message = "👋 Hi there! I'm *Freezy*, your code freeze assistant. Here’s what I can do:\n\n🔍 *Check:* `/check` - View code freeze status\n❄️ *Freeze:* `/freeze [repo]` - Place code freeze on a repository\n🔥 *Unfreeze:* `/unfreeze [repo]` - Lift code freeze on a repository\n\nExample commands:\n✅ `/freeze api, cdm`\n✅ `/unfreeze cdm, api`\n\nLet me know how I can assist you! 🚀"
    return send_slack_message(channel_id, message, True, user_id)

def handle_check(channel_id, user_id):
    if not frozen_repos:
        message = "✅ No repositories are currently on code freeze."
    else:
        frozen_list = "\n".join(f"- *{repo}*" for repo in frozen_repos)
        message = f"🚨 The following repositories are on code freeze:\n{frozen_list}"
    return send_slack_message(channel_id, message, True, user_id)

def handle_freeze(repo_name, channel_id, user_id):
    if not repo_name:
        message = "❄️ Please specify a repository to freeze. Example: `/freeze api`"
        return send_slack_message(channel_id, message, True, user_id)
    repos = {repo.strip().upper() for repo in repo_name.split(",") if repo.strip()}
    frozen_repos.update(repos)
    message = f"❄️ Code freeze placed on: *{', '.join(repos)}*."
    return send_slack_message(channel_id, message, False, user_id)

def handle_unfreeze(repo_name, channel_id, user_id):
    if not repo_name:
        message = "🔥 Please specify a repository to unfreeze. Example: `/unfreeze api`"
        return send_slack_message(channel_id, message, True, user_id)
    
    if repo_name.lower() == "all":  
        if not frozen_repos:
            message = "✅ No repositories are currently on code freeze."
        else:
            frozen_repos.clear()
            message = "🔥 Code freeze lifted on *all* repositories."
        return send_slack_message(channel_id, message, False, user_id)
        
    repos = {repo.strip().upper() for repo in repo_name.split(",") if repo.strip()}
    unfrozen = repos.intersection(frozen_repos)
    if not unfrozen:
        message = "⚠️ None of the specified repositories are on code freeze."
        return send_slack_message(channel_id, message, True, user_id)
    
    frozen_repos.difference_update(unfrozen)
    message = f"🔥 Code freeze lifted on: *{', '.join(unfrozen)}*."
    return send_slack_message(channel_id, message, False, user_id)

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=int(os.getenv("PORT", 3000)), debug=os.getenv("DEBUG", "False") == "True")
    