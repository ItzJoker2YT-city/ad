from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests

app = Flask(__name__)
# Enable CORS so your index.html can communicate with this API
CORS(app)

@app.route('/')
def serve_index():
    # Serve the AFK page when you visit http://127.0.0.1:5000/
    return send_file('index.html')

CTRLPANEL_URL = 'https://dash.runhost.qzz.io'
CTRLPANEL_API_KEY = 'nVxnWuL57PJyvrfQ9R5R5TsUsjnrnX5hikasbLxeQryWFB83'

HEADERS = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {CTRLPANEL_API_KEY}'
}

@app.route('/api/verify', methods=['GET'])
def verify_user():
    username = request.args.get('username')
    if not username:
        return jsonify({"error": "Username is required"}), 400

    # CtrlPanel uses /api/users with filter[name]
    url = f"{CTRLPANEL_URL}/api/users?filter[name]={username}"
    
    try:
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            # If data array is not empty, check if we found a match
            if data.get('data') and len(data['data']) > 0:
                # Get the first user
                user_data = data['data'][0]
                # Return success with the user's ID and current credits
                return jsonify({
                    "exists": True, 
                    "user": {
                        "id": user_data.get('id'),
                        "name": user_data.get('name'),
                        "credits": user_data.get('credits')
                    }
                })
            else:
                return jsonify({"exists": False, "error": "User not found"}), 404
                
        # If there's an authentication error or other API issue
        return jsonify({
            "exists": False, 
            "error": f"Panel API Error: {response.status_code}",
            "details": response.text
        }), response.status_code

    except Exception as e:
        return jsonify({"exists": False, "error": str(e)}), 500


@app.route('/api/claim', methods=['POST'])
def claim_credits():
    data = request.json
    username = data.get('username')
    credits_to_add = data.get('credits')

    if not username or not credits_to_add:
        return jsonify({"error": "Missing username or credits"}), 400

    try:
        # Step 1: Fetch the user's ID
        get_url = f"{CTRLPANEL_URL}/api/users?filter[name]={username}"
        get_res = requests.get(get_url, headers=HEADERS)
        
        if get_res.status_code != 200:
            return jsonify({"error": "Failed to fetch user from panel"}), get_res.status_code
            
        user_data_resp = get_res.json()
        if not user_data_resp.get('data') or len(user_data_resp['data']) == 0:
            return jsonify({"error": "User not found"}), 404
            
        user = user_data_resp['data'][0]
        user_id = user['id']

        # Step 2: Increment the user's credits securely using the API's native increment endpoint
        increment_url = f"{CTRLPANEL_URL}/api/users/{user_id}/increment"
        payload = {
            "credits": float(credits_to_add)
        }

        patch_res = requests.patch(increment_url, headers=HEADERS, json=payload)
        
        if patch_res.status_code in [200, 201, 204]:
            # Step 3: Send a notification to the user
            notif_url = f"{CTRLPANEL_URL}/api/notifications/send-to-users"
            notif_payload = {
                "via": "database", # database means it shows up as a bell icon notification on the panel
                "users": [user_id],
                "title": "AFK Rewards Claimed",
                "content": f"{username} successfully claimed {credits_to_add} coins from AFK!"
            }
            try:
                requests.post(notif_url, headers=HEADERS, json=notif_payload)
            except Exception as e:
                print(f"Warning: Failed to send notification: {e}")

            return jsonify({"success": True})
        else:
            return jsonify({
                "error": f"Failed to update credits: {patch_res.status_code}",
                "details": patch_res.text
            }), patch_res.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting AFK Backend API...")
    print("Press CTRL+C to stop.")
    try:
        from waitress import serve
        print("Running in PRODUCTION mode via Waitress on port 5000.")
        serve(app, host='0.0.0.0', port=5000)
    except ImportError:
        print("Waitress not installed. Falling back to development server...")
        app.run(host='0.0.0.0', port=5000)
