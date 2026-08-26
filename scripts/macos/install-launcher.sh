#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APPLICATIONS_DIR="$HOME/Applications"
LAUNCH_APP="$APPLICATIONS_DIR/DubLocal.app"
STOP_APP="$APPLICATIONS_DIR/Stop DubLocal.app"
LAUNCH_SCRIPT="$SCRIPT_DIR/launch-dublocal.sh"
STOP_SCRIPT="$SCRIPT_DIR/stop-dublocal.sh"
ICON_SVG="$REPO_ROOT/assets/macos/DubLocal.svg"
APP_HOME="$HOME/.dublocal"
BUILD_DIR="$APP_HOME/build"
ICONSET_DIR="$BUILD_DIR/DubLocal.iconset"
ICON_FILE="$BUILD_DIR/DubLocal.icns"
VENV="$REPO_ROOT/.venv"
PYTHON="$VENV/bin/python"

mkdir -p "$APPLICATIONS_DIR" "$BUILD_DIR"
chmod +x "$LAUNCH_SCRIPT" "$STOP_SCRIPT" "$SCRIPT_DIR/install-launcher.sh"

ask_yes_no() {
  local prompt="$1"
  local default_answer="$2"
  local reply
  if [[ "$default_answer" == "yes" ]]; then
    read -r "reply?$prompt [Y/n] "
    reply="${reply:-y}"
  else
    read -r "reply?$prompt [y/N] "
    reply="${reply:-n}"
  fi
  [[ "$reply" == [Yy]* ]]
}

find_python() {
  local candidate path
  for candidate in python3.13 python3.12 python3.11 python3; do
    path="$(command -v "$candidate" 2>/dev/null || true)"
    if [[ -n "$path" ]] && "$path" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
      printf '%s\n' "$path"
      return 0
    fi
  done
  return 1
}

ensure_core() {
  "$PYTHON" -m pip install --upgrade pip
  "$PYTHON" -m pip install -e "$REPO_ROOT"
}

if [[ ! -x "$PYTHON" ]]; then
  PYTHON_BASE="$(find_python || true)"
  if [[ -z "$PYTHON_BASE" ]]; then
    echo "DubLocal requires Python 3.11 or newer."
    echo "Install Python 3.11+ and rerun:"
    echo "  zsh scripts/macos/install-launcher.sh"
    exit 1
  fi

  echo "Creating DubLocal environment with: $PYTHON_BASE"
  "$PYTHON_BASE" -m venv "$VENV"
  ensure_core
else
  echo "Existing DubLocal environment found. Refreshing the local package."
  "$PYTHON" -m pip install -e "$REPO_ROOT"
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo
  echo "FFmpeg/ffprobe were not found. YouTube caption discovery can still work,"
  echo "but local media inspection/extraction requires FFmpeg."
  if command -v brew >/dev/null 2>&1; then
    if ask_yes_no "Install FFmpeg with Homebrew now?" yes; then
      brew install ffmpeg
    else
      echo "Skipping FFmpeg. Install it later before processing local media."
    fi
  else
    echo "Homebrew was not found, so FFmpeg was not installed automatically."
  fi
fi

build_icon() {
  local render_dir rendered
  render_dir="$BUILD_DIR/icon-render"
  /bin/rm -rf "$render_dir" "$ICONSET_DIR" "$ICON_FILE"
  /bin/mkdir -p "$render_dir" "$ICONSET_DIR"

  if [[ ! -f "$ICON_SVG" ]]; then
    echo "Missing logo source: $ICON_SVG"
    return 1
  fi

  /usr/bin/qlmanage -t -s 1024 -o "$render_dir" "$ICON_SVG" >/dev/null 2>&1 || return 1
  rendered="$(/usr/bin/find "$render_dir" -maxdepth 1 -type f -name '*.png' | /usr/bin/head -n 1)"
  if [[ -z "$rendered" || ! -f "$rendered" ]]; then
    return 1
  fi

  /usr/bin/sips -z 16 16 "$rendered" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
  /usr/bin/sips -z 32 32 "$rendered" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
  /usr/bin/sips -z 32 32 "$rendered" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
  /usr/bin/sips -z 64 64 "$rendered" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
  /usr/bin/sips -z 128 128 "$rendered" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
  /usr/bin/sips -z 256 256 "$rendered" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
  /usr/bin/sips -z 256 256 "$rendered" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
  /usr/bin/sips -z 512 512 "$rendered" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
  /usr/bin/sips -z 512 512 "$rendered" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
  /usr/bin/sips -z 1024 1024 "$rendered" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
  /usr/bin/iconutil -c icns "$ICONSET_DIR" -o "$ICON_FILE"
}

if build_icon; then
  echo "DubLocal icon generated from assets/macos/DubLocal.svg."
else
  echo "Could not generate the branded icon with macOS Quick Look/iconutil."
  echo "Launcher installation will stop rather than silently use a generic icon."
  exit 1
fi

set_plist_value() {
  local plist="$1"
  local key="$2"
  local type="$3"
  local value="$4"
  /usr/libexec/PlistBuddy -c "Set :$key $value" "$plist" >/dev/null 2>&1 \
    || /usr/libexec/PlistBuddy -c "Add :$key $type $value" "$plist" >/dev/null
}

make_app() {
  local output="$1"
  local target_script="$2"
  local display_name="$3"
  local bundle_id="$4"
  local temp_script plist

  temp_script="$(/usr/bin/mktemp -t dublocal-launcher).applescript"
  cat > "$temp_script" <<EOF
on run
  do shell script "/bin/zsh " & quoted form of "$target_script" & " >/dev/null 2>&1 &"
end run
EOF

  /bin/rm -rf "$output"
  /usr/bin/osacompile -o "$output" "$temp_script"
  /bin/rm -f "$temp_script"

  /bin/cp "$ICON_FILE" "$output/Contents/Resources/applet.icns"
  plist="$output/Contents/Info.plist"
  set_plist_value "$plist" "CFBundleName" "string" "$display_name"
  set_plist_value "$plist" "CFBundleDisplayName" "string" "$display_name"
  set_plist_value "$plist" "CFBundleIdentifier" "string" "$bundle_id"
  set_plist_value "$plist" "CFBundleShortVersionString" "string" "0.1"
  set_plist_value "$plist" "CFBundleVersion" "string" "1"
  /usr/bin/touch "$output"
}

make_app "$LAUNCH_APP" "$LAUNCH_SCRIPT" "DubLocal" "io.github.arrowsk.dublocal"
make_app "$STOP_APP" "$STOP_SCRIPT" "Stop DubLocal" "io.github.arrowsk.dublocal.stop"

echo
echo "Installed:"
echo "  $LAUNCH_APP"
echo "  $STOP_APP"
echo
echo "The launcher uses the branded DubLocal icon and opens the local UI on port 7861."
echo "Logs: ~/.dublocal/logs/dublocal.log"
echo "You can drag DubLocal.app from ~/Applications to the Dock."
