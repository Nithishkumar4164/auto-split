#!/data/data/com.termux/files/usr/bin/bash
# autosplit-upload.sh
#
# Share an invoice image from PhonePe (or any app) to Termux, then run this
# script with the shared file path as $1.
#
# Setup:
#   1. Add to ~/.bashrc:
#        export AUTOSPLIT_LAN="http://192.168.1.x:8090"       # server's LAN IP
#        export AUTOSPLIT_TAILSCALE="http://100.x.x.x:8090"   # server's Tailscale IP
#   2. Place this script in ~/.shortcuts/ and make it executable:
#        chmod +x ~/.shortcuts/autosplit-upload.sh
#   3. Requires: Termux:API app + `pkg install termux-api fzf`

set -euo pipefail

# ── Server selection: probe LAN first (500 ms), fall back to Tailscale ────────

SERVER="${AUTOSPLIT_TAILSCALE:-http://100.x.x.x:8090}"
if curl -sf --connect-timeout 0.5 "${AUTOSPLIT_LAN:-http://192.168.1.x:8090}/health" > /dev/null 2>&1; then
    SERVER="${AUTOSPLIT_LAN:-http://192.168.1.x:8090}"
fi

SHARED_FILE="${1:-}"

notify() {
  termux-notification --title "AutoSplit" --content "$1" --id autosplit
}

# ── Validate input ─────────────────────────────────────────────────────────────

if [[ -z "$SHARED_FILE" || ! -f "$SHARED_FILE" ]]; then
  notify "No image file received"
  exit 1
fi

# ── Fetch groups from server ───────────────────────────────────────────────────

GROUPS_JSON=$(curl -sf --connect-timeout 5 "$SERVER/groups" 2>/dev/null) || {
  notify "Cannot reach server: $SERVER"
  exit 1
}

AUTOSPLIT_FZF_LIST=$(echo "$GROUPS_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
active = data.get('active', [])
inactive = data.get('inactive', [])
lines = active
if inactive:
    lines.append('─── settled ───')
    lines.extend('· ' + g for g in inactive)
print('\n'.join(lines))
")

# ── Group selection with live fuzzy search ────────────────────────────────────

SELECTED=$(printf "%s\n+ New group..." "$AUTOSPLIT_FZF_LIST" | fzf \
  --prompt="Group: " \
  --height=50% \
  --border \
  --reverse \
  --no-sort \
  --header="Type to filter  Enter=select  Esc=cancel") || exit 0

# strip inactive prefix; abort if separator was selected
[[ "$SELECTED" == "─── settled ───" ]] && exit 0
SELECTED="${SELECTED#· }"

# ── New group prompt ───────────────────────────────────────────────────────────

if [[ "$SELECTED" == "+ New group..." ]]; then
  NEW_NAME_RESULT=$(termux-dialog text -t "AutoSplit — new group name" -i "e.g. Roommates")
  SELECTED=$(echo "$NEW_NAME_RESULT" | python3 -c "
import sys, json
r = json.load(sys.stdin)
if r.get('code', -2) == -2:
    sys.exit(1)
name = r.get('text', '').strip()
if not name:
    sys.exit(1)
print(name)
") || exit 0
fi

# ── Upload ─────────────────────────────────────────────────────────────────────

notify "Uploading to \"$SELECTED\"…"

RESPONSE=$(curl -sf --connect-timeout 10 -X POST "$SERVER/upload" \
  -F "image=@$SHARED_FILE" \
  -F "group=$SELECTED" 2>/dev/null) || {
  notify "Upload failed — check server logs"
  exit 1
}

JOB_ID=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if not data.get('success'):
    print('ERROR: ' + data.get('error', 'unknown'))
    sys.exit(1)
print(data.get('job_id', ''))
") || {
  notify "Server rejected upload: $(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',''))")"
  exit 1
}

notify "Queued for \"$SELECTED\" ✓  (job ${JOB_ID:0:8}…)"
