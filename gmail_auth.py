"""Local Gmail OAuth login and automatic token refresh."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKEN = ROOT / 'data' / 'gmail-token.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def save(credentials):
    TOKEN.parent.mkdir(exist_ok=True)
    temporary = TOKEN.with_suffix('.tmp')
    temporary.write_text(credentials.to_json(), encoding='utf-8')
    temporary.replace(TOKEN)


def access_token():
    if not TOKEN.exists():
        return os.getenv('GMAIL_ACCESS_TOKEN')
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    try:
        credentials = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
        if not credentials.valid:
            if not credentials.refresh_token:
                raise ValueError('Sign in again using connect-gmail.ps1.')
            credentials.refresh(Request())
            save(credentials)
        return credentials.token
    except Exception:
        raise ValueError('Gmail authorization expired or refresh failed. Run connect-gmail.ps1 to sign in again.') from None


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow
    path = ROOT / 'credentials.json'
    if not path.exists():
        raise SystemExit('Save your Desktop OAuth client JSON as credentials.json in this folder.')
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES, autogenerate_code_verifier=True)
        credentials = flow.run_local_server(host='localhost', port=0, timeout_seconds=300,
            authorization_prompt_message='Opening Google sign-in in your browser. Complete it there.',
            success_message='Gmail connected to Support Sentinel. You can close this tab.',
            access_type='offline', prompt='consent')
        save(credentials)
        print('Gmail connected. Restart Support Sentinel if it is already running.')
    except Exception:
        raise SystemExit('Sign-in was not completed. Check that your Gmail address is an OAuth test user and try again.') from None


if __name__ == '__main__':
    main()
