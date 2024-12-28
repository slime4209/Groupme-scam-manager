# Note: membership_id and user_id are two different things! The scope of those two are different.
#     membership_id (or often just represented as "id"): 
#         ID used specifically in the group only, meaning a user will have the same # of membership_id
#         as the # of group chats they belong to.
#     user_id: 
#         ID used in the entire GroupMe, meaning a user will have only one user_id assigned to them.

import sys
sys.path.insert(0, 'vendor')

from flask import Flask, request, jsonify
import os
import requests
import random
import json

app = Flask(__name__)

API_ROOT = 'https://api.groupme.com/v3/'
FLAGGED_PHRASES = (
    'essay written by professionals',
    'paper writing service',
    'academic writing service',
    'student paper assignments',
    'getting professional academic help from us is easy',
    'cutt.us',
    'inyurl.com/muxz7h',
    'u.to/xavt',
    'we write your papers',
    'best in the writing service industry',
    'side job offer for you which',
    'getting $1000 within week',
    'lost my daughter to cancer about a week ago,she was',
    'to cancer about a week ago',
    'play station 5',
    'ps5',
    'ticket',
    'tickets',
    'essay writer',
    'super writer',
    'cute writer',
    'hentai',
)

# Edit these variables to customize your groupme auth token and bot id
token = '<your groupme auth token>'
bot_id = '<your groupme bot id>'

def get_memberships(group_id):
    response = requests.get(f'{API_ROOT}groups/{group_id}?token={token}')
    responses = response.json()
    return responses

def get_membership_id(group_id, user_id):
    memberships = get_memberships(group_id)
    memberships = memberships['response']
    memberships = memberships['members']
    for membership in memberships:
        if membership['user_id'] == user_id:
            return membership['id']
    return None

def kick_user(group_id, user_id):
    membership_id = get_membership_id(group_id, user_id)
    if membership_id:
        response = requests.post(f'{API_ROOT}groups/{group_id}/members/{membership_id}/remove?token={token}') #, params={'token': token})
        print('Attempted to kick user, got response:')
        print(response.text)
        return response.ok  # Return whether the request was successful
    return False

# tries to figure out if the user is new by seeing how long they have existed in the group chat
# GroupMe's timestamps are in seconds
def new_user(group_id, user_id, message_time):
    messages = requests.get(f'{API_ROOT}groups/{group_id}/messages?token={token}')['response']['messages']
    joined_time = 0
    for message in messages:
        if message['event']['type'] == "membership.announce.joined" and message['event']['data']['user']['id'] == user_id:
            joined_time = message['created_at']
            break
    if (message_time - joined_time) <= 259200: # 259200 seconds, or 3 days
        return True
    return False    

def delete_message(group_id, message_id):
    response = requests.delete(f'{API_ROOT}conversations/{group_id}/messages/{message_id}', params={'token': token})
    return response.ok

# ===================================================================================================================

def receive(event):
    message = event #json.loads(event['text'])
    for phrase in FLAGGED_PHRASES:
        if phrase in message['text'].lower() and new_user(message['group_id'], message['user_id'], message['created_at']:
            if kick_user(message['group_id'], message['user_id']):
                delete_message(message['group_id'], message['id'])
                send('Kicked ' + message['name'] + ' due to apparent spam post.', bot_id)
            else:
                print('Kick attempt failed or user is an admin.')
            break
            print(group)

    return {
        'statusCode': 200,
        'body': 'ok'
    }


def send(text, bot_id):
    url = 'https://api.groupme.com/v3/bots/post'

    message = {
        'bot_id': bot_id,
        'text': text,
    }
    r = requests.post(url, json=message)


@app.route('/', methods=['POST'])  # Ensure this route handles POST requests
def webhook():
    if request.is_json:  # Check if the incoming request is JSON
        event = request.get_json()
        return receive(event)
    else:
        return jsonify({'error': 'Request must be JSON'}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
