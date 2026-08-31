"""
Example 1: The 5-Line Telegram Music Bot
Shows how any bot developer can build a working Telegram Voice Chat music bot in just 5 lines of code.
"""
import requests

# 1. Developer receives Telegram update "/play Starboy"
# 2. Makes one single API call to Elite Music API:
response = requests.post(
    "http://localhost:8000/v1/rooms/-100192837465/play",
    headers={"X-API-Key": "client_live_your_api_key_here"},
    json={"query": "The Weeknd - Starboy", "requested_by": {"user_id": 123456, "name": "Alex"}}
)

# 3. Done! The API assigns a userbot, joins the group VC, transcodes in RAM, and streams the audio.
print(response.json())
