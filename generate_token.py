import os
import pickle
import logging
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from pathlib import Path

# --- Configuration matching extractor.py ---
CLIENT_SECRETS_FILE = 'client_secrets.json'
YOUTUBE_API_TOKEN_FILE = 'youtube_api_creds.pickle'
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl', 'https://www.googleapis.com/auth/youtube.readonly']
# ---

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def run_local_oauth_flow():
    """
    Runs the OAuth 2.0 Device Authorization Flow and saves the credentials.
    """
    API_TOKEN_PATH = Path(YOUTUBE_API_TOKEN_FILE)
    creds = None
    
    # 1. Check for existing token
    if API_TOKEN_PATH.exists():
        try:
            with open(API_TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)
            logger.info("Existing token found. Checking validity...")
            
            if creds and creds.expired and creds.refresh_token:
                logger.info("Token expired. Attempting refresh...")
                creds.refresh(Request())
            
            if creds and creds.valid:
                logger.info("Token is valid. No action needed.")
                return
        except Exception as e:
            logger.error(f"Error loading or refreshing credentials: {e}. Forcing new authentication.")
            creds = None

    # 2. Start new authorization flow
    if not creds or not creds.valid:
        
        client_secrets_path = CLIENT_SECRETS_FILE

        if not Path(client_secrets_path).exists():
            logger.error(f"Client secrets file not found at {client_secrets_path}. Please place 'client_secrets.json' in the current directory.")
            return

        try:
            # Use the InstalledAppFlow to handle the desktop/console flow
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            
            # This is the key line: it triggers the device flow, asks the user to visit a URL
            # in their browser, and waits for authorization.
            logger.info("Starting OAuth Device Flow...")
            creds = flow.run_local_server(port=0)

            # 3. Save the credentials (includes the crucial refresh token)
            with open(API_TOKEN_PATH, 'wb') as token:
                pickle.dump(creds, token)
            
            logger.info(f"\n✅ OAuth flow completed successfully!")
            logger.info(f"   Credentials saved to: {API_TOKEN_PATH}")
            logger.info("   You can now upload the contents of this file to your Vercel environment.")

        except Exception as e:
            logger.error(f"\n❌ Error during OAuth flow or file saving: {e}")
            creds = None
    
    # Optional: Test service creation
    if creds and creds.valid:
        try:
            build('youtube', 'v3', credentials=creds)
            logger.info("YouTube API service object built successfully with new credentials.")
        except Exception as e:
            logger.error(f"Failed to build YouTube service: {e}")


if __name__ == '__main__':
    run_local_oauth_flow()