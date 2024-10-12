import sys
sys.path.insert(0, 'vendor')

from flask import Flask, request, jsonify
import os
import requests
import random
import json

import psycopg2
from datetime import datetime

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

# this is for logging purpose; I want to collect the scam messages to see any patterns
# creates PostgreSQL to store messages
def log_deleted_message_to_db(message):
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST')
    )
    cur = conn.cursor()

    # Insert the deleted message into the table
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("INSERT INTO deleted_messages (timestamp, user_name, message_text) VALUES (%s, %s, %s)",
                (timestamp, message['name'], message['text']))

    conn.commit()
    cur.close()
    conn.close()


def get_memberships(group_id, token):
    response = requests.get(f'{API_ROOT}groups/{group_id}', params={'token': token}).json()['response']['members']
    return response

def get_membership_id(group_id, user_id, token):
    memberships = get_memberships(group_id, token)
    for membership in memberships:
        if membership['user_id'] == user_id:
            return membership['id']
    return None

def remove_member(group_id, membership_id, token):
    response = requests.post(f'{API_ROOT}groups/{group_id}/members/{membership_id}/remove', params={'token': token})
    print('Attempted to kick user, got response:')
    print(response.text)
    return response.ok  # Return whether the request was successful


def delete_message(group_id, message_id, token):
    response = requests.delete(f'{API_ROOT}conversations/{group_id}/messages/{message_id}', params={'token': token})
    return response.ok


def kick_user(group_id, user_id, token):
    membership_id = get_membership_id(group_id, user_id, token)
    if membership_id:
        return remove_member(group_id, membership_id, token)
    return False

@app.route('/')
def webhook():
    event = request.get_json()
    context = None  # Context is often used in cloud functions, not needed here
    return receive(event, context)

    


def receive(event, context):
    message = event['body']  # Assuming event['body'] contains the message JSON
    bot_id = message['bot_id']

    for phrase in FLAGGED_PHRASES:
        if phrase in message['text'].lower():
            # Attempt to kick the user and check if it was successful
            if kick_user(message['group_id'], message['user_id'], message['token']):
                delete_message(message['group_id'], message['id'], message['token'])
                log_deleted_message_to_db(message)
                send('Kicked ' + message['name'] + ' due to apparent spam post.', bot_id)
            else:
                print('Kick attempt failed or user is an admin.')
            break

    return {
        jsonify({'statusCode': 200, 'body': 'ok'})
    }


def send(text, bot_id):
    url = 'https://api.groupme.com/v3/bots/post'

    message = {
        'bot_id': bot_id,
        'text': text,
    }
    r = requests.post(url, json=message)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
