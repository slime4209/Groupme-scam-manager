# Note: membership_id and user_id are two different things! The scope of those two are different.
#     membership_id (or often just represented as "id"): 
#         ID used specifically in the group only, meaning a user will have the same # of membership_id
#         as the # of group chats they belong to.
#     user_id: 
#         ID used in the entire GroupMe, meaning a user will have only one user_id assigned to them.

import sys
sys.path.insert(0, 'vendor')

from flask import Flask, request, render_template, jsonify
import os
import requests
import random
import json
import sqlite3
import configparser

app = Flask(__name__)

API_ROOT = 'https://api.groupme.com/v3/'

# Load the config.ini file
config = configparser.ConfigParser()
config.read("config.ini")

token = config.get("Settings", "TOKEN")
bot_id = config.get("Settings", "BOT_ID")
sub_group_id = config.getint("Settings", "SUB_GROUP_ID") 
cap_time = config.getint("Settings", "CAP_TIME")
flagged_phrases_str = config.get("Settings", "FLAGGED_PHRASES")
flagged_phrases = flagged_phrases_str.split(",\n")


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
# GroupMe's timestamps are in seconds (epoch)
def new_user(message): 
    with sqlite3.connect('databases/new_users.db') as conn:
        cursor = conn.cursor()
        user_id = int(message['user_id'])
        try: 
            cursor.execute(f"SELECT timestamp FROM users WHERE user_id = {user_id} ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone() 
        except sqlite3.OperationalError: 
            print('Table doesnt exist, so not new user')
            return False
        if row:  
            if (message['created_at'] - row[0]) <= cap_time:
                print(message['created_at'], row[0], message['user_id'])
                print('New user spotted')
                return True
            else: 
                print(message['created_at'], row[0], message['user_id'])
                print('Not new user')
                return False
        else:
            print('No matching user found.')
            return False
    print('Connection to database closed')
    # Connection is automatically closed here

def delete_message(group_id, message_id):
    response = requests.delete(f'{API_ROOT}conversations/{group_id}/messages/{message_id}', params={'token': token})
    return response.ok

def add_user_db_entry(timestamp, username, user_id, event_name):
    with sqlite3.connect('databases/new_users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS users (timestamp INTEGER, username TEXT, user_id INTEGER, event_name TEXT, PRIMARY KEY (timestamp, user_id))')
        print('User Table created')
        # adds entry to database
        cursor.execute(
            f"INSERT INTO users VALUES (?, ?, ?, ?)",
            (timestamp, username, user_id, event_name)
        )
        print('user info inserted')
        conn.commit()
        cursor.execute(f"DELETE FROM users WHERE timestamp < strftime('%s', 'now', '-30 days')")
        print('old users deleted')
        conn.commit()
    print('Connection to database closed')
    # Connection is automatically closed here

def add_db_entry(timestamp, username, user_id, message):
    # Use context manager
    with sqlite3.connect('databases/scam_messages.db') as conn:
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS scarab (timestamp INTEGER PRIMARY KEY, username TEXT, user_id INTEGER, message TEXT)')
        # adds entry to database
        cursor.execute(
            "INSERT INTO scarab VALUES (?, ?, ?, ?)",
            (timestamp, username, user_id, message)
        )
        conn.commit()
    print('Connection to database closed')
    # Connection is automatically closed here

# ===================================================================================================================
# the REALLY important functions
def receive(event):
    # message = event #json.loads(event['text'])
    print(event)
    user_kicked = False
  
    if event['sender_id'] == "system":
        print('event found')
        group_id = event['group_id']
        messages = requests.get(f'{API_ROOT}groups/{group_id}/messages?token={token}').json()
        messages = messages['response']['messages']
        for message in messages: 
            if event['id'] == message['id']:
                if message['event']['type'] == "membership.announce.added":
                    for user in message['event']['data']['added_users']:
                        add_user_db_entry(message['created_at'], 
                                          user['nickname'], 
                                          user['id'], 
                                          'membership.announce.added')
                elif message['event']['type'] == "membership.announce.joined":
                    add_user_db_entry(message['created_at'], 
                                      message['event']['data']['user']['nickname'], 
                                      message['event']['data']['user']['id'], 
                                      'membership.announce.joined')
            
    for phrase in flagged_phrases:
        if phrase in event['text'].lower() and new_user(event):
            add_db_entry(event['created_at'], event['name'], event['user_id'], event['text'])
            
            # kicks user and deletes message
            if kick_user(event['group_id'], event['user_id']):
                user_kicked = True
                delete_message(event['group_id'], event['id'])
                send('Kicked ' + event['name'] + ' due to apparent spam post.', bot_id)
            else:
                print('Kick attempt failed or user is an admin.')
            break
            print(group)

    submessages = requests.get(f'{API_ROOT}groups/{sub_group_id}/messages?token={token}').json()
    submessages = submessages['response']['messages']
    for submessage in submessages: 
        if submessage['user_id'] == event['user_id'] and user_kicked == True:
            delete_message(submessage['group_id'], submessage['id'])
  
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

# ==========================================================================================
# web interface stuff
@app.route('/index')
def home():
    return render_template('webtest.html')

# Route to fetch new_users database content
@app.route('/new-users-content', methods=['GET'])
def new_users_content():
    # Example database content
    with sqlite3.connect('databases/new_users.db') as conn:
        conn.row_factory = sqlite3.Row  
        cursor = conn.cursor()
        cursor.execute("SELECT datetime(timestamp, 'unixepoch') AS timestamp, * FROM users")
        rows = cursor.fetchall() 
        dict_row = [dict(row) for row in rows]
        return jsonify(dict_row)

# Route to fetch scam_messages database content
@app.route('/scam-msg-content', methods=['GET'])
def scam_msg_content():
    # Example database content
    with sqlite3.connect('databases/scam_messages.db') as conn:
        conn.row_factory = sqlite3.Row  
        cursor = conn.cursor()
        cursor.execute("SELECT datetime(timestamp, 'unixepoch') AS timestamp, * FROM scarab")
        rows = cursor.fetchall() 
        dict_row = [dict(row) for row in rows]
        return jsonify(dict_row)

# =========================================================================================
# Flask stuff 
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
