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
#   3. Requires: Termux:API app + `pkg install termux-api`

set -euo pipefail

# ── Server selection: LAN when on home WiFi, Tailscale otherwise ───────────────

HOME_SSIDS=("Moota_Poochi" "Moota_Poochi_5G")

CURRENT_SSID=$(termux-wifi-connectioninfo 2>/dev/null \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('ssid',''))" 2>/dev/null \
  || echo "")

SERVER="${AUTOSPLIT_TAILSCALE:-http://100.x.x.x:8090}"
for ssid in "${HOME_SSIDS[@]}"; do
  if [[ "$CURRENT_SSID" == "$ssid" ]]; then
    SERVER="${AUTOSPLIT_LAN:-http://192.168.1.x:8090}"
    break
  fi
done

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

# Build comma-separated list for termux-dialog (append "New group..." option)
GROUP_LIST=$(echo "$GROUPS_JSON" | python3 -c "
import sys, json
groups = json.load(sys.stdin).get('groups', [])
groups.append('+ New group...')
# termux-dialog uses comma-separated values; escape any commas in names
print(','.join(g.replace(',', ';') for g in groups))
")

# ── Group selection dialog ─────────────────────────────────────────────────────

DIALOG_RESULT=$(termux-dialog radio -t "AutoSplit — select group" -v "$GROUP_LIST")
SELECTED=$(echo "$DIALOG_RESULT" | python3 -c "
import sys, json
r = json.load(sys.stdin)
# code -2 = back button / cancelled
if r.get('code', -2) == -2:
    sys.exit(1)
print(r.get('text', '').strip())
") || exit 0

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
