"""
Interactive Setup & Authentication Utility for Live Gmail.
Guides you through connecting your actual Gmail account and authenticating via OAuth 2.0.
"""

import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console with unbuffered lines
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from fleet.config import DATA_DIR
from fleet.integrations.gmail_client import (
    CATEGORY_LABEL_MAP,
    CREDENTIALS_FILE,
    SCOPES,
    TOKEN_FILE,
    GmailManager,
)


def print_step_by_step_guide():
    print("\n" + "=" * 70)
    print("  🔑 HOW TO GET YOUR GMAIL CREDENTIALS (3-MINUTE SETUP)")
    print("=" * 70)
    print("""
1. Open Google Cloud Console:
   👉 https://console.cloud.google.com/

2. Create a Project:
   - Click the project dropdown at the top -> 'New Project'.
   - Name it 'Personal Fleet' and click 'Create'.

3. Enable Gmail API:
   - In the search bar at top, type 'Gmail API' and press Enter.
   - Click 'Gmail API' -> Click 'Enable'.

4. Configure OAuth Consent Screen:
   - Go to: 'APIs & Services' -> 'OAuth consent screen'.
   - Select 'External' (or 'Internal' if Workspace) -> Click 'Create'.
   - App name: 'Personal Fleet', enter your email -> Click 'Save and Continue'.
   - On 'Test Users' screen, click '+ Add Users' and add your Gmail address!
   - Save and Finish.

5. Create Desktop Credentials:
   - Go to: 'APIs & Services' -> 'Credentials'.
   - Click '+ Create Credentials' at top -> Select 'OAuth client ID'.
   - Application type: Select 'Desktop app'.
   - Name: 'Personal Fleet Laptop'.
   - Click 'Create'.

6. Download JSON File:
   - Click the Download button (⬇️) next to the created Client ID.
   - Save the downloaded file exactly to this path on your laptop:
""")
    target_path = CREDENTIALS_FILE.resolve()
    print(f"      📍 {target_path}")
    print("=" * 70)
    print("\nOnce you place 'credentials.json' in that folder, run this script again:\n  python -m fleet.setup_gmail\n")


def authenticate_and_verify():
    print("\n" + "=" * 70)
    print("  🚀 CONNECTING TO LIVE GMAIL ACCOUNT...")
    print("=" * 70)
    print(f"Detected credentials file: {CREDENTIALS_FILE.name}")
    print("Opening browser for one-time Google Account authorization...\n")

    try:
        mgr = GmailManager()
        creds = mgr.authenticate_interactive()
        print(f"✅ Authorization successful! Token saved to: {TOKEN_FILE.name}")

        service = mgr.service
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "Unknown")
        total_messages = profile.get("messagesTotal", 0)

        print("\n" + "-" * 70)
        print(f"🎉 Connected to Gmail Account: {email_address}")
        print(f"📊 Total messages in account:   {total_messages}")
        print("-" * 70)

        # Ensure labels exist in live account
        print("\nChecking / creating 5 Fleet Folders in your Gmail...")
        existing_labels = service.users().labels().list(userId="me").execute().get("labels", [])
        name_to_id = {l["name"]: l["id"] for l in existing_labels}

        for cat_id, label_name in CATEGORY_LABEL_MAP.items():
            if label_name in name_to_id:
                print(f"  • Existing label: {label_name}")
            else:
                new_lbl = service.users().labels().create(
                    userId="me",
                    body={
                        "name": label_name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show"
                    }
                ).execute()
                print(f"  ✨ Created new label: {label_name}")

        print("\n" + "=" * 70)
        print("  ⚡ RUNNING INITIAL 2-MONTH LIVE CLASSIFICATION SCAN")
        print("=" * 70)
        mgr = GmailManager()
        result = mgr.sync_and_classify(dry_run=False)

        counts = result.get("counts", {})
        print(f"\n✅ Successfully processed {result.get('total_processed', 0)} emails across this & last month:")
        print(f"   📅 0) Meetings: {counts.get('Meetings', 0)}")
        print(f"   💬 1) Respond:  {counts.get('Respond', 0)}")
        print(f"   📝 2) Note:     {counts.get('Note', 0)}")
        print(f"   ℹ️ 3) FYI:      {counts.get('FYI', 0)}")
        print(f"   🚫 4) Ignore:   {counts.get('Ignore', 0)}")
        print("\nCheck your Gmail sidebar — your 5 Fleet folders are now active and populated!\n")

    except Exception as e:
        print(f"\n❌ Error during authentication: {e}")
        print("Please verify your credentials.json file and ensure your Gmail address is added as a Test User in Google Cloud Console.")


def main():
    if not CREDENTIALS_FILE.exists():
        print(f"\n⚠️  Missing file: {CREDENTIALS_FILE.resolve()}")
        print_step_by_step_guide()
    else:
        authenticate_and_verify()


if __name__ == "__main__":
    main()

