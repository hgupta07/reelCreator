#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_scheduler.sh
# Sets up a macOS LaunchAgent to run the content generator daily at 8:00 AM.
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.reelcreator.dailycontent"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_DIR="$SCRIPT_DIR/logs"
PYTHON=$(which python3)

# ── Create log directory ──────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Read post time from config (default 08:00) ────────────────────────────────
HOUR=8
MINUTE=0
if command -v python3 &>/dev/null; then
    HOUR=$(python3 -c "
import yaml, sys
try:
    cfg = yaml.safe_load(open('$SCRIPT_DIR/config.yaml'))
    t = cfg.get('posting',{}).get('post_time','08:00')
    print(t.split(':')[0].lstrip('0') or '0')
except: print(8)
" 2>/dev/null || echo 8)
    MINUTE=$(python3 -c "
import yaml
try:
    cfg = yaml.safe_load(open('$SCRIPT_DIR/config.yaml'))
    t = cfg.get('posting',{}).get('post_time','08:00')
    print(t.split(':')[1].lstrip('0') or '0')
except: print(0)
" 2>/dev/null || echo 0)
fi

echo "⏰ Scheduling daily run at ${HOUR}:$(printf '%02d' $MINUTE)"

# ── Write the LaunchAgent plist ───────────────────────────────────────────────
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/run.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/daily_content.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/daily_content_error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

# ── Load (or reload) the agent ────────────────────────────────────────────────
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load   "$PLIST_PATH"

echo ""
echo "✅  LaunchAgent installed and loaded."
echo ""
echo "   Schedule : Every day at ${HOUR}:$(printf '%02d' $MINUTE) local time"
echo "   Plist    : $PLIST_PATH"
echo "   Logs     : $LOG_DIR/daily_content.log"
echo "   Errors   : $LOG_DIR/daily_content_error.log"
echo ""
echo "   To run RIGHT NOW (for testing):"
echo "   launchctl start $PLIST_NAME"
echo ""
echo "   To disable the scheduler:"
echo "   launchctl unload $PLIST_PATH"
echo ""
