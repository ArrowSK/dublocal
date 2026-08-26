#!/bin/zsh
set -u

APP_HOME="$HOME/.dublocal"
PID_FILE="$APP_HOME/dublocal.pid"
REV_FILE="$APP_HOME/running-revision"

notify() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"DubLocal\"" >/dev/null 2>&1 || true
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

PIDS="$(dublocal_pids)"
if [[ -z "$PIDS" ]]; then
  /bin/rm -f "$PID_FILE" "$REV_FILE"
  notify "DubLocal is not running."
  exit 0
fi

COUNT=0
for PID in ${(f)PIDS}; do
  COMMAND="$(/bin/ps -p "$PID" -o command= 2>/dev/null || true)"
  if is_dublocal_command "$COMMAND"; then
    /bin/kill -TERM "$PID" 2>/dev/null || true
    COUNT=$((COUNT + 1))
  fi
done

for _ in {1..30}; do
  if [[ -z "$(dublocal_pids)" ]]; then
    /bin/rm -f "$PID_FILE" "$REV_FILE"
    notify "Stopped $COUNT DubLocal instance(s)."
    exit 0
  fi
  /bin/sleep 0.25
done

PIDS="$(dublocal_pids)"
for PID in ${(f)PIDS}; do
  COMMAND="$(/bin/ps -p "$PID" -o command= 2>/dev/null || true)"
  if is_dublocal_command "$COMMAND"; then
    /bin/kill -KILL "$PID" 2>/dev/null || true
  fi
done

/bin/rm -f "$PID_FILE" "$REV_FILE"
notify "DubLocal stop completed."
