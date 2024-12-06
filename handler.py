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
    print(memberships)
    for membership in memberships:
        if membership['user_id'] == user_id:
            return membership['id']
    return None

def remove_member(group_id, membership_id):
    response = requests.post(f'{API_ROOT}groups/{group_id}/members/{membership_id}/remove?token={token}') #, params={'token': token})
    print('Attempted to kick user, got response:')
    print(response.text)
    return response.ok  # Return whether the request was successful


def delete_message(group_id, message_id):
    response = requests.delete(f'{API_ROOT}conversations/{group_id}/messages/{message_id}', params={'token': token})
    return response.ok


def kick_user(group_id, user_id):
    membership_id = get_membership_id(group_id, user_id)
    if membership_id:
        return remove_member(group_id, membership_id)
    return False

def receive(event):
    message = event #json.loads(event['text'])
    for phrase in FLAGGED_PHRASES:
        if phrase in message['text'].lower():
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
