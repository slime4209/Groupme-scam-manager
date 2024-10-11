import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_ID = os.environ.get('BOT_ID')
GROUP_ID = os.environ.get('GROUP_ID')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')

PROHIBITED_KEYWORDS = ['keyword1', 'keyword2', 'keyword3']

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if data['name'] != 'Your Bot Name':
        if any(keyword in data['text'].lower() for keyword in PROHIBITED_KEYWORDS):
            # Post warning message
            post_message("The previous message violated group rules and the user has been removed.")
            
            # Remove user
            remove_user(data['group_id'], data['user_id'])
    
    return "OK", 200

def post_message(msg):
    url = 'https://api.groupme.com/v3/bots/post'
    data = {
        'bot_id': BOT_ID,
        'text': msg
    }
    requests.post(url, json=data)

def remove_user(group_id, user_id):
    url = f'https://api.groupme.com/v3/groups/{group_id}/members/{user_id}/remove'
    headers = {'X-Access-Token': ACCESS_TOKEN}
    requests.post(url, headers=headers)

if __name__ == '__main__':
    app.run()
