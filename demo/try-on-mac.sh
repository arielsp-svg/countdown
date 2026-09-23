#!/usr/bin/env bash
# Run Countdown from source on a Mac, in a sandbox that can be thrown away.
#
#   demo/try-on-mac.sh            run it
#   demo/try-on-mac.sh --reset    wipe the saved state, so the first run window returns
#   demo/try-on-mac.sh --admin    open the maintenance window
#
# Everything it writes stays in demo/sandbox. Your real home folder is untouched,
# and nothing is registered to start automatically: that part is Windows only.
set -euo pipefail
cd "$(dirname "$0")/.."

SANDBOX="$PWD/demo/sandbox"
VENV="$PWD/.venv"

if [[ "${1:-}" == "--reset" ]]; then
  rm -rf "$SANDBOX"
  echo "sandbox cleared; the next run starts from the first run window"
  shift
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "creating .venv ..."
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install -q --upgrade pip
  "$VENV/bin/python" -m pip install -q -r requirements.txt
fi

mkdir -p "$SANDBOX"
"$VENV/bin/python" demo/make_table.py "$SANDBOX/table.csv"

if [[ ! -f "$SANDBOX/countdown.txt" ]]; then
  cat > "$SANDBOX/countdown.txt" <<TXT
# Demo configuration. Only used when COUNTDOWN_HOME points here.
admin_username = admin
admin_password = secret

# A local file, so no SharePoint access is needed to try the app.
sharepoint_url = file://$SANDBOX/table.csv

departments = Avionics, Logistics, Maintenance
TXT
fi

echo
echo "sandbox:    $SANDBOX"
echo "table:      $SANDBOX/table.csv"
echo "admin:      admin / secret"
echo "department: choose Avionics to see alerts"
echo

COUNTDOWN_HOME="$SANDBOX" "$VENV/bin/python" main.py "$@"
