import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete your local token.json file.
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def get_calendar_service():
    """
    Authenticates the user and returns an authorized Google Calendar service client.
    Handles token caching and automatic token refreshing.
    """
    creds = None

    # The file token.json stores the user's access and refresh tokens.
    # It is created automatically when the authorization flow completes for the first time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If there are no valid credentials available, prompt the user to log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired access token...")
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError(
                    "Missing 'credentials.json'. Download it from Google Cloud Console "
                    "(APIs & Services > Credentials > OAuth 2.0 Client IDs - Desktop App)."
                )

            print("Initiating Google OAuth login flow in browser...")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for subsequent executions
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def create_test_event():
    """Inserts a test event starting 2 hours from now."""
    try:
        service = get_calendar_service()

        # Compute dynamic start and end times (2 hours from now, 30 min duration)
        now = datetime.datetime.now(datetime.timezone.utc)
        start_time = now + datetime.timedelta(hours=2)
        end_time = start_time + datetime.timedelta(minutes=30)

        event_payload = {
            "summary": "AI Voice Agent - Calendar Test",
            "location": "Google Meet",
            "description": "Verification event created by test_calendar.py script.",
            "start": {
                "dateTime": start_time.isoformat(),
            },
            "end": {
                "dateTime": end_time.isoformat(),
            },
            # Requests Google to automatically generate a Google Meet link
            "conferenceData": {
                "createRequest": {
                    "requestId": f"test-meet-{int(now.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"}
                }
            }
        }

        print("Sending event insertion request to Google Calendar...")
        created_event = service.events().insert(
            calendarId="primary",
            body=event_payload,
            conferenceDataVersion=1
        ).execute()

        print("\n Event successfully created!")
        print(f"Summary:       {created_event.get('summary')}")
        print(f"Start Time:    {created_event.get('start', {}).get('dateTime')}")
        print(f"Calendar Link: {created_event.get('htmlLink')}")
        if created_event.get("hangoutLink"):
            print(f"Meet Link:     {created_event.get('hangoutLink')}")

    except HttpError as error:
        print(f"\n Google API Error: {error}")
    except Exception as e:
        print(f"\n Execution Error: {e}")

{"installed":{"client_id":"286178266236-ghbf5a6uho1ru60iubrkfl42kdcs9hje.apps.googleusercontent.com","project_id":"calender-api-510719","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"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","redirect_uris":["http://localhost"]}}

if __name__ == "__main__":
    create_test_event()