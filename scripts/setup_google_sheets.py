#!/usr/bin/env python3
"""
Google Sheets Setup Script for Discord Host Scheduler Bot

This script automatically creates and configures the required Google Sheets structure
for the Discord Host Scheduler Bot. It's safe to run multiple times - it will only
create missing sheets and add missing data.

Usage:
    python3 scripts/setup_google_sheets.py

Requirements:
    - .env file with GOOGLE_SHEETS_SPREADSHEET_ID and GOOGLE_SHEETS_CREDENTIALS_FILE
    - Valid Google Service Account credentials file
    - Python packages: gspread, google-auth, python-dotenv
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path to import from src if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("❌ Missing required packages. Please install them:")
    print("   pip install gspread google-auth python-dotenv")
    sys.exit(1)


class GoogleSheetsSetup:
    """Handles the setup of Google Sheets structure for the bot."""

    # Define the complete structure for all sheets
    SHEETS_STRUCTURE = {
        "Configuration": {
            "headers": [
                "setting_key",
                "setting_value",
                "setting_type",
                "description",
                "updated_at",
            ],
            "data": [
                [
                    "warning_passive_days",
                    "7",
                    "integer",
                    "Days before event to post passive warning",
                    "",
                ],
                [
                    "warning_urgent_days",
                    "3",
                    "integer",
                    "Days before event to post urgent warning",
                    "",
                ],
                [
                    "daily_check_time",
                    "09:00",
                    "string",
                    "Time of day for daily warning check (PST)",
                    "",
                ],
                [
                    "schedule_window_weeks",
                    "8",
                    "integer",
                    "Default weeks to show in schedule view",
                    "",
                ],
                [
                    "organizer_role_ids",
                    "[]",
                    "json",
                    "Discord role IDs that can use admin commands",
                    "",
                ],
                [
                    "host_privileged_role_ids",
                    "[]",
                    "json",
                    "Discord role IDs that can volunteer for others",
                    "",
                ],
                [
                    "schedule_channel_id",
                    "",
                    "string",
                    "Discord channel ID for schedule displays",
                    "",
                ],
                ["warnings_channel_id", "", "string", "Discord channel ID for warning posts", ""],
                [
                    "cache_ttl_seconds",
                    "300",
                    "integer",
                    "Cache TTL for Google Sheets data (5 minutes)",
                    "",
                ],
                [
                    "max_batch_size",
                    "100",
                    "integer",
                    "Maximum rows to batch in Google Sheets API calls",
                    "",
                ],
            ],
            "description": "Bot configuration settings",
        },
        "Schedule": {
            "headers": [
                "date",
                "host_discord_id",
                "host_username",
                "recurring_pattern_id",
                "assigned_at",
                "assigned_by",
                "notes",
            ],
            "data": [],
            "description": "Host assignments by date",
        },
        "RecurringPatterns": {
            "headers": [
                "pattern_id",
                "host_discord_id",
                "host_username",
                "pattern_description",
                "pattern_rule",
                "start_date",
                "end_date",
                "created_at",
                "is_active",
            ],
            "data": [],
            "description": "Recurring hosting patterns",
        },
        "AuditLog": {
            "headers": [
                "entry_id",
                "timestamp",
                "action_type",
                "user_discord_id",
                "target_user_discord_id",
                "event_date",
                "recurring_pattern_id",
                "outcome",
                "error_message",
                "metadata",
            ],
            "data": [],
            "description": "Audit trail of all bot actions",
        },
    }

    def __init__(self):
        """Initialize the setup with environment configuration."""
        # Load environment variables
        load_dotenv()

        self.spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        self.credentials_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")

        self.validate_environment()

    def validate_environment(self):
        """Validate that required environment variables are set."""
        if not self.spreadsheet_id:
            print("❌ Error: GOOGLE_SHEETS_SPREADSHEET_ID not found in .env file")
            print("   Please add your Google Spreadsheet ID to the .env file")
            sys.exit(1)

        if not self.credentials_file:
            print("❌ Error: GOOGLE_SHEETS_CREDENTIALS_FILE not found in .env file")
            print("   Please add the path to your credentials file in the .env file")
            sys.exit(1)

        if not Path(self.credentials_file).exists():
            print(f"❌ Error: Credentials file not found: {self.credentials_file}")
            print("   Please ensure the credentials file exists at the specified path")
            sys.exit(1)

    def connect(self):
        """Connect to Google Sheets API."""
        print("🔐 Authenticating with Google Sheets API...")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        try:
            creds = Credentials.from_service_account_file(self.credentials_file, scopes=scopes)
            self.client = gspread.authorize(creds)
            print("✅ Authentication successful")
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            sys.exit(1)

    def open_spreadsheet(self):
        """Open the target spreadsheet."""
        print(f"\n📋 Opening spreadsheet: {self.spreadsheet_id}")

        try:
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            print(f"✅ Opened: {self.spreadsheet.title}")
            print(f"   URL: {self.spreadsheet.url}")
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ Spreadsheet not found with ID: {self.spreadsheet_id}")
            print("   Please check the GOOGLE_SHEETS_SPREADSHEET_ID in your .env file")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to open spreadsheet: {e}")
            sys.exit(1)

    def get_existing_sheets(self):
        """Get dictionary of existing worksheets."""
        worksheets = self.spreadsheet.worksheets()
        return {ws.title: ws for ws in worksheets}

    def setup_sheet(self, sheet_name, config, existing_sheets):
        """
        Set up a single sheet with headers and data.

        Args:
            sheet_name: Name of the sheet to set up
            config: Dictionary with headers, data, and description
            existing_sheets: Dictionary of existing worksheets
        """
        print(f"\n🔧 Setting up: {sheet_name}")
        print(f"   Purpose: {config['description']}")

        # Create sheet if it doesn't exist
        if sheet_name not in existing_sheets:
            print("   ➕ Creating new sheet...")
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name, rows=100, cols=len(config["headers"])
            )
            existing_sheets[sheet_name] = worksheet
        else:
            worksheet = existing_sheets[sheet_name]
            print("   ✓ Sheet already exists")

        # Check and fix headers
        all_values = worksheet.get_all_values()

        if len(all_values) == 0 or all_values[0] != config["headers"]:
            print(f"   📝 Setting headers ({len(config['headers'])} columns)")
            worksheet.update(values=[config["headers"]], range_name="A1")
        else:
            print("   ✓ Headers are correct")

        # Add data if configured and missing
        if config["data"]:
            # Re-fetch after potential header update
            all_values = worksheet.get_all_values()

            if len(all_values) <= 1:  # Only headers or empty
                print(f"   📝 Adding {len(config['data'])} data rows")
                worksheet.update(values=config["data"], range_name="A2")
                print("   ✅ Data added successfully")
            else:
                print(f"   ✓ Data already exists ({len(all_values) - 1} rows)")
        else:
            print("   ℹ️  No default data to add (user-populated sheet)")

    def print_summary(self):
        """Print a summary of the final state."""
        print("\n" + "=" * 60)
        print("🎉 Google Sheets Setup Complete!")
        print("=" * 60)

        print(f"\n📊 Spreadsheet: {self.spreadsheet.title}")
        print(f"🔗 URL: {self.spreadsheet.url}")

        print("\n📋 Sheets Summary:")
        for ws in self.spreadsheet.worksheets():
            row_count = len(ws.get_all_values())
            data_rows = row_count - 1  # Subtract header row
            status = "📝 Has data" if data_rows > 0 else "✓ Ready"
            print(f"   {status} {ws.title}: {data_rows} data rows")

        print("\n✅ Your bot is now ready to use!")
        print("   Run: python3 -m src.bot")

    def run(self):
        """Execute the full setup process."""
        print("=" * 60)
        print("Google Sheets Setup for Discord Host Scheduler Bot")
        print("=" * 60)

        self.connect()
        self.open_spreadsheet()

        existing_sheets = self.get_existing_sheets()
        print(f"\n📄 Found {len(existing_sheets)} existing sheet(s): {list(existing_sheets.keys())}")

        # Set up each sheet
        for sheet_name, config in self.SHEETS_STRUCTURE.items():
            self.setup_sheet(sheet_name, config, existing_sheets)

        self.print_summary()


def main():
    """Main entry point."""
    try:
        setup = GoogleSheetsSetup()
        setup.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
