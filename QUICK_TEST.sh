#!/bin/bash
# Quick test script for Discord Host Scheduler Bot

echo "🚀 Discord Host Scheduler Bot - Quick Test"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo ""
    echo "Please create .env file with:"
    echo "  DISCORD_BOT_TOKEN=your_token"
    echo "  GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id"
    echo "  GOOGLE_SHEETS_CREDENTIALS_FILE=service-account-key.json"
    echo ""
    echo "See QUICKSTART_TESTING.md for detailed setup instructions."
    exit 1
fi

# Check if service account key exists
CREDS_FILE=$(grep GOOGLE_SHEETS_CREDENTIALS_FILE .env | cut -d '=' -f2)
if [ ! -f "$CREDS_FILE" ]; then
    echo "❌ Service account credentials file not found: $CREDS_FILE"
    echo ""
    echo "See QUICKSTART_TESTING.md Step 2 for how to create service account."
    exit 1
fi

echo "✅ .env file found"
echo "✅ Service account credentials found"
echo ""

# Run syntax check
echo "🔍 Running syntax check..."
/usr/bin/python3 -m py_compile src/bot.py src/commands/*.py src/services/*.py src/models/*.py src/utils/*.py 2>&1
if [ $? -eq 0 ]; then
    echo "✅ No syntax errors found"
else
    echo "❌ Syntax errors detected"
    exit 1
fi
echo ""

# Run unit tests
echo "🧪 Running unit tests..."
/usr/bin/python3 -m pytest tests/unit/ -q
if [ $? -eq 0 ]; then
    echo "✅ All unit tests passed"
else
    echo "❌ Some tests failed"
    exit 1
fi
echo ""

echo "✨ Pre-flight checks complete!"
echo ""
echo "Ready to start the bot. Run:"
echo "  /usr/bin/python3 src/bot.py"
echo ""
echo "Or for detailed setup instructions, see:"
echo "  QUICKSTART_TESTING.md"
