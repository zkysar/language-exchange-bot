# Scripts Directory

Helper scripts for setting up and maintaining the Discord Host Scheduler Bot.

## Available Scripts

### setup_google_sheets.py

Automated setup script for creating and configuring Google Sheets structure.

**Purpose:**
- Creates all required worksheet tabs (Configuration, Schedule, RecurringPatterns, AuditLog)
- Adds proper headers to each sheet
- Populates Configuration sheet with default settings
- Verifies the setup is correct

**Usage:**
```bash
python3 scripts/setup_google_sheets.py
```

**Prerequisites:**
- `.env` file configured with `GOOGLE_SHEETS_SPREADSHEET_ID` and `GOOGLE_SHEETS_CREDENTIALS_FILE`
- Valid Google Service Account credentials file
- Google Spreadsheet created and shared with service account

**Features:**
- ✅ Idempotent - safe to run multiple times
- ✅ Only creates missing sheets and data
- ✅ Detailed progress output
- ✅ Validates environment configuration
- ✅ Provides helpful error messages

**Example Output:**
```
============================================================
Google Sheets Setup for Discord Host Scheduler Bot
============================================================
🔐 Authenticating with Google Sheets API...
✅ Authentication successful

📋 Opening spreadsheet: 1mEc4OqwKmNVDhn51yRLQOe276XXQDsRduz9AKXS1wwM
✅ Opened: Language Exchange Bot Test Sheet
   URL: https://docs.google.com/spreadsheets/d/...

📄 Found 2 existing sheet(s): ['Sheet1', 'Sheet2']

🔧 Setting up: Configuration
   Purpose: Bot configuration settings
   ➕ Creating new sheet...
   📝 Setting headers (5 columns)
   📝 Adding 10 data rows
   ✅ Data added successfully

🔧 Setting up: Schedule
   Purpose: Host assignments by date
   ✓ Sheet already exists
   ✓ Headers are correct
   ℹ️  No default data to add (user-populated sheet)

============================================================
🎉 Google Sheets Setup Complete!
============================================================

📊 Spreadsheet: Language Exchange Bot Test Sheet
🔗 URL: https://docs.google.com/spreadsheets/d/...

📋 Sheets Summary:
   📝 Has data Configuration: 10 data rows
   ✓ Ready Schedule: 0 data rows
   ✓ Ready RecurringPatterns: 0 data rows
   ✓ Ready AuditLog: 0 data rows

✅ Your bot is now ready to use!
   Run: python3 -m src.bot
```

**Troubleshooting:**

*"Missing required environment variables"*
- Ensure `.env` file exists in project root
- Check that `GOOGLE_SHEETS_SPREADSHEET_ID` and `GOOGLE_SHEETS_CREDENTIALS_FILE` are set

*"Credentials file not found"*
- Verify the path in `GOOGLE_SHEETS_CREDENTIALS_FILE` is correct
- Ensure the credentials JSON file exists at that location

*"Spreadsheet not found"*
- Check the Spreadsheet ID in `.env` is correct
- Verify the spreadsheet is shared with your service account email

*"Authentication failed"*
- Verify the credentials JSON file is valid
- Check that Google Sheets API is enabled in your Google Cloud project
- Ensure the service account hasn't been deleted

## Adding New Scripts

When adding new scripts to this directory:

1. Add a shebang line: `#!/usr/bin/env python3`
2. Include comprehensive docstring explaining purpose and usage
3. Make it executable: `chmod +x scripts/your_script.py`
4. Add validation for required environment variables
5. Provide helpful error messages
6. Make it idempotent when possible (safe to run multiple times)
7. Update this README with documentation

## Script Development Guidelines

- Use `python-dotenv` to load environment variables
- Include try/except blocks for external API calls
- Provide clear progress output for long-running operations
- Exit with appropriate error codes (0 for success, 1 for errors)
- Document all command-line arguments if applicable
- Include usage examples in docstrings
