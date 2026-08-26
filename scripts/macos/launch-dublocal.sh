#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"
APP_HOME="$HOME/.dublocal"
LOG_DIR="$APP_HOME/logs"
PID_FILE="$APP_HOME/dublocal.pid"
REV_FILE="$APP_HOME/running-revision"
LOG_FILE="$LOG_DIR/dublocal.log"
URL="http://127.0.0.1:7861"

mkdir -p "$LOG_DIR"

notify() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"DubLocal\"" >/dev/null 2>&1 || true
}

is_ready() {
  /usr/bin/curl -fsS --max-time 1 "$URL/" >/dev/null 2>&1
}

open_dublocal() {
  /usr/bin/open "$URL"
}

current_revision() {
  /usr/bin/git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true
}

running_revision() {
  if [[ -f "$REV_FILE" ]]; then
    /usr/bin/head -n 1 "$REV_FILE" 2>/dev/null || true
  fi
}

short_revision() {
  local revision="$1"
  if [[ -n "$revision" ]]; then
    printf '%s' "$revision" | /usr/bin/cut -c1-12
  else
    printf '%s' "unknown"
  fi
}

is_dublocal_command() {
  local command="$1"
  [[ "$command" == *" -m dublocal.launcher_runtime"* \
    || "$command" == "dublocal" \
    || "$command" == "dublocal "* \
    || "$command" == *"/bin/dublocal" \
    || "$command" == *"/bin/dublocal "* ]]
}

dublocal_pids() {
  local line pid command
  while IFS= read -r line; do
    pid="${line%% *}"
    command="${line#* }"
    if [[ -n "$pid" ]] && is_dublocal_command "$command"; then
      printf '%s\n' "$pid"
    fi
  done < <(/bin/ps -axo pid=,command= | /usr/bin/sed 's/^[[:space:]]*//')
}

has_dublocal_instances() {
  [[ -n "$(dublocal_pids)" ]]
}

stop_all_instances() {
  local pids pid command
  pids="$(dublocal_pids)"
  if [[ -z "$pids" ]]; then
    /bin/rm -f "$PID_FILE" "$REV_FILE"
    return 0
  fi

  for pid in ${(f)pids}; do
    command="$(/bin/ps -p "$pid" -o command= 2>/dev/null || true)"
    if is_dublocal_command "$command"; then
      /bin/kill -TERM "$pid" 2>/dev/null || true
    fi
  done

  for _ in {1..30}; do
    if ! has_dublocal_instances; then
      /bin/rm -f "$PID_FILE" "$REV_FILE"
      return 0
    fi
    /bin/sleep 0.25
  done

  pids="$(dublocal_pids)"
  for pid in ${(f)pids}; do
    command="$(/bin/ps -p "$pid" -o command= 2>/dev/null || true)"
    if is_dublocal_command "$command"; then
      /bin/kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  /bin/rm -f "$PID_FILE" "$REV_FILE"
}

choose_action() {
  local detail current_rev running_rev default_button
  current_rev="$(current_revision)"
  running_rev="$(running_revision)"
  default_button="Launch / Open"
  detail="DubLocal can open/launch normally, or stop every running DubLocal process and start one clean instance."

  if is_ready; then
    detail="$detail\n\nA DubLocal instance is currently responding on 127.0.0.1:7861."
  elif has_dublocal_instances; then
    detail="$detail\n\nA DubLocal process exists but is not yet responding."
  fi

  if has_dublocal_instances && [[ -n "$current_rev" && -n "$running_rev" && "$current_rev" != "$running_rev" ]]; then
    detail="$detail\n\nDubLocal code has changed since the running instance started.\nRunning revision: $(short_revision "$running_rev")\nCurrent revision: $(short_revision "$current_rev")\n\nChoose Stop All & Launch to run the updated code."
    default_button="Stop All & Launch"
  elif has_dublocal_instances && [[ -n "$current_rev" && -z "$running_rev" ]]; then
    detail="$detail\n\nThe running instance revision is unknown. If you just pulled an update, choose Stop All & Launch."
  fi

  /usr/bin/osascript <<EOF 2>/dev/null
button returned of (display dialog "$detail" with title "DubLocal" buttons {"Cancel", "Launch / Open", "Stop All & Launch"} default button "$default_button" cancel button "Cancel")
EOF
}

REQUESTED_ACTION="${DUBLOCAL_LAUNCH_ACTION:-}"
if [[ "$REQUESTED_ACTION" == "restart" ]]; then
  ACTION="Stop All & Launch"
elif [[ "$REQUESTED_ACTION" == "open" ]]; then
  ACTION="Launch / Open"
else
  ACTION="$(choose_action || true)"
fi

if [[ -z "$ACTION" || "$ACTION" == "Cancel" ]]; then
  exit 0
fi

if [[ "$ACTION" == "Stop All & Launch" ]]; then
  stop_all_instances
else
  if is_ready; then
    open_dublocal
    exit 0
  fi
  if has_dublocal_instances; then
    for _ in {1..20}; do
      if is_ready; then
        open_dublocal
        exit 0
      fi
      /bin/sleep 0.5
    done
    notify "A DubLocal process is running but not responding. Reopen the launcher and choose Stop All & Launch."
    exit 1
  fi
fi

if [[ ! -x "$PYTHON" ]]; then
  notify "Python environment not found. Run the DubLocal installer first."
  /usr/bin/open "$REPO_ROOT/docs/INSTALLATION.md" >/dev/null 2>&1 || true
  exit 1
fi

CURRENT_REV="$(current_revision)"
cd "$REPO_ROOT" || exit 1

DUBLOCAL_INBROWSER=0 DUBLOCAL_PORT=7861 /usr/bin/nohup "$PYTHON" -m dublocal.launcher_runtime >>"$LOG_FILE" 2>&1 &
DUBLOCAL_PID=$!
printf '%s\n' "$DUBLOCAL_PID" > "$PID_FILE"
if [[ -n "$CURRENT_REV" ]]; then
  printf '%s\n' "$CURRENT_REV" > "$REV_FILE"
else
  /bin/rm -f "$REV_FILE"
fi

for _ in {1..120}; do
  if is_ready; then
    open_dublocal
    exit 0
  fi

  if ! /bin/kill -0 "$DUBLOCAL_PID" 2>/dev/null; then
    /bin/rm -f "$PID_FILE" "$REV_FILE"
    notify "DubLocal failed to start. Check ~/.dublocal/logs/dublocal.log"
    exit 1
  fi

  /bin/sleep 0.5
done

notify "DubLocal is still starting. Check the log if it does not appear shortly."
exit 1
