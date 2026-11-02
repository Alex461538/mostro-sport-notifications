import base64
import os
import pickle
from email.mime.text import MIMEText

from flask import Flask, jsonify, request
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
CREDENTIALS_DIR = os.path.join(os.path.dirname(__file__), 'credentials')
CLIENT_SECRET_FILE = os.path.join(CREDENTIALS_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, 'token.pickle')

def authenticate_gmail():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(CREDENTIALS_DIR, exist_ok=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def create_message(sender, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes())
    return {'raw': raw_message.decode()}

def send_message(service, user_id, message):
    sent_message = service.users().messages().send(userId=user_id, body=message).execute()
    return sent_message

def send_email_message(sender, to, subject, message_text):
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    message = create_message(sender, to, subject, message_text)
    return send_message(service, 'me', message)

def create_app():
    app = Flask(__name__)

    @app.get('/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.post('/send-email')
    def send_email():
        payload = request.get_json(silent=True) or {}

        to = payload.get('to')
        subject = payload.get('subject')
        message_text = payload.get('message')
        sender = payload.get('sender') or os.environ.get('GMAIL_SENDER') or 'me'

        if not to or not subject or not message_text:
            return jsonify({
                'error': 'Se requieren los campos: to, subject y message'
            }), 400

        try:
            result = send_email_message(sender, to, subject, message_text)
            return jsonify({
                'success': True,
                'message_id': result.get('id'),
                'data': result
            })
        except Exception as exc:
            app.logger.exception('Error sending email')
            return jsonify({
                'success': False,
                'error': str(exc)
            }), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
