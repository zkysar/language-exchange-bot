# Discord Host Scheduler Bot

A Discord bot that manages host volunteering for recurring meetups through a Google Sheets backend, with automated reminders and warnings.

## Features

- **Volunteer for Hosting**: Hosts can claim available dates via Discord commands
- **Recurring Patterns**: Set up regular hosting commitments (e.g., "every 2nd Tuesday")
- **Schedule Viewing**: See upcoming hosts and unassigned dates
- **Warning System**: Automated alerts for dates without hosts
- **Google Sheets Integration**: All data stored in editable spreadsheet
- **Offline Resilience**: Local cache keeps bot functional during API outages
- **Audit Trail**: Complete history of all actions for accountability

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Discord bot token
- Google Sheets document with required sheets
- Google Service Account credentials

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd language-exchange-bot
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. Set up Google Sheets structure:
   ```bash
   python3 scripts/setup_google_sheets.py
   ```
   This automated script will create all required sheets with proper headers and configuration.

5. Run the bot:
   ```bash
   python3 -m src.bot
   ```

For detailed setup instructions, see [SETUP.md](SETUP.md).

## Documentation

- **[SETUP.md](SETUP.md)** - Detailed setup and deployment instructions
- **[COMMANDS.md](COMMANDS.md)** - Complete command reference
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and architecture

## Key Commands

- `/volunteer [date]` - Volunteer to host on a specific date
- `/volunteer recurring [pattern]` - Set up recurring hosting pattern
- `/schedule` - View upcoming host schedule
- `/unvolunteer [date]` - Cancel your hosting commitment
- `/help` - Show all available commands

## Architecture

The bot uses:
- **discord.py** for Discord API integration
- **gspread** for Google Sheets API
- **Local JSON cache** for resilience and performance
- **Google Sheets** as authoritative data source

## Contributing

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design details before contributing.

## License

MIT
