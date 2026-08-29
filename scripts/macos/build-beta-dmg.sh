#!/bin/zsh
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "DubLocal beta DMG packaging must run on macOS." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

VERSION="$(/usr/bin/sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | /usr/bin/head -n 1)"
[[ -n "$VERSION" ]] || { echo "Could not read DubLocal version from pyproject.toml." >&2; exit 1; }

BUILD_SHA="${DUBLOCAL_BUILD_SHA:-$(/usr/bin/git rev-parse HEAD)}"
[[ "$BUILD_SHA" =~ '^[0-9a-f]{7,40}$' ]] || { echo "Invalid build SHA: $BUILD_SHA" >&2; exit 1; }

BUILD_ROOT="$REPO_ROOT/build/macos-beta"
APP="$BUILD_ROOT/DubLocal.app"
ICON_RENDER="$BUILD_ROOT/icon-render"
ICONSET="$BUILD_ROOT/DubLocal.iconset"
ICON_FILE="$BUILD_ROOT/DubLocal.icns"
STAGE="$BUILD_ROOT/dmg-root"
DIST="$REPO_ROOT/dist"
DMG="$DIST/DubLocal-${VERSION}-macOS-unsigned.dmg"
CHECKSUM="$DMG.sha256"
ICON_SVG="$REPO_ROOT/assets/macos/DubLocal.svg"
BOOTSTRAP="$REPO_ROOT/scripts/macos/beta-bootstrap.sh"

/bin/rm -rf "$BUILD_ROOT"
/bin/mkdir -p "$BUILD_ROOT" "$DIST" "$ICON_RENDER" "$ICONSET" "$STAGE"
/bin/rm -f "$DMG" "$CHECKSUM"

[[ -f "$ICON_SVG" ]] || { echo "Missing app icon source: $ICON_SVG" >&2; exit 1; }
[[ -f "$BOOTSTRAP" ]] || { echo "Missing beta bootstrap: $BOOTSTRAP" >&2; exit 1; }

build_icon() {
  local rendered
  /usr/bin/qlmanage -t -s 1024 -o "$ICON_RENDER" "$ICON_SVG" >/dev/null 2>&1 || return 1
  rendered="$(/usr/bin/find "$ICON_RENDER" -maxdepth 1 -type f -name '*.png' | /usr/bin/head -n 1)"
  [[ -n "$rendered" && -f "$rendered" ]] || return 1

  /usr/bin/sips -z 16 16 "$rendered" --out "$ICONSET/icon_16x16.png" >/dev/null
  /usr/bin/sips -z 32 32 "$rendered" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
  /usr/bin/sips -z 32 32 "$rendered" --out "$ICONSET/icon_32x32.png" >/dev/null
  /usr/bin/sips -z 64 64 "$rendered" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
  /usr/bin/sips -z 128 128 "$rendered" --out "$ICONSET/icon_128x128.png" >/dev/null
  /usr/bin/sips -z 256 256 "$rendered" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
  /usr/bin/sips -z 256 256 "$rendered" --out "$ICONSET/icon_256x256.png" >/dev/null
  /usr/bin/sips -z 512 512 "$rendered" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
  /usr/bin/sips -z 512 512 "$rendered" --out "$ICONSET/icon_512x512.png" >/dev/null
  /usr/bin/sips -z 1024 1024 "$rendered" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
  /usr/bin/iconutil -c icns "$ICONSET" -o "$ICON_FILE"
}

build_icon || { echo "Could not render assets/macos/DubLocal.svg into a macOS app icon." >&2; exit 1; }

APPLESCRIPT="$BUILD_ROOT/DubLocal.applescript"
cat > "$APPLESCRIPT" <<'APPLESCRIPT_EOF'
on run
  set appRoot to POSIX path of (path to me)
  set bootstrapPath to appRoot & "Contents/Resources/beta-bootstrap.sh"
  do shell script "/bin/zsh " & quoted form of bootstrapPath & " >/dev/null 2>&1 &"
end run
APPLESCRIPT_EOF

/usr/bin/osacompile -o "$APP" "$APPLESCRIPT"
/bin/cp "$ICON_FILE" "$APP/Contents/Resources/applet.icns"
/bin/cp "$BOOTSTRAP" "$APP/Contents/Resources/beta-bootstrap.sh"
/bin/chmod 755 "$APP/Contents/Resources/beta-bootstrap.sh"

cat > "$APP/Contents/Resources/build-info.env" <<EOF
BETA_VERSION='$VERSION'
BUILD_SHA='$BUILD_SHA'
EOF

PLIST="$APP/Contents/Info.plist"
set_plist() {
  local key="$1" type="$2" value="$3"
  /usr/libexec/PlistBuddy -c "Set :$key $value" "$PLIST" >/dev/null 2>&1 \
    || /usr/libexec/PlistBuddy -c "Add :$key $type $value" "$PLIST" >/dev/null
}

set_plist CFBundleName string DubLocal
set_plist CFBundleDisplayName string DubLocal
set_plist CFBundleIdentifier string io.github.arrowsk.dublocal
set_plist CFBundleShortVersionString string "${VERSION%b1}"
set_plist CFBundleVersion string 601
set_plist LSMinimumSystemVersion string 13.0
set_plist NSHighResolutionCapable bool true
set_plist LSMultipleInstancesProhibited bool true
/usr/bin/plutil -lint "$PLIST" >/dev/null
/usr/bin/touch "$APP"

# The first beta is deliberately unsigned/not notarized. Fail the build if an identity
# or ad-hoc signature unexpectedly appears so release metadata never claims the wrong
# security state.
if /usr/bin/codesign -dv "$APP" >/dev/null 2>&1; then
  echo "DubLocal.app unexpectedly has a code signature; beta 1 must remain unsigned." >&2
  exit 1
fi

/bin/cp -R "$APP" "$STAGE/DubLocal.app"
/bin/ln -s /Applications "$STAGE/Applications"
/bin/cp "$REPO_ROOT/LICENSE" "$STAGE/License.txt"
/bin/cp "$REPO_ROOT/THIRD_PARTY_LICENSES.md" "$STAGE/Third-Party Licenses.txt"

cat > "$STAGE/FIRST LAUNCH.txt" <<EOF
DubLocal ${VERSION} — unsigned beta

1. Drag DubLocal.app to Applications.
2. Because this beta is unsigned, Control-click (or right-click) DubLocal.app and choose Open the first time.
3. If macOS still blocks it, open System Settings → Privacy & Security and choose Open Anyway for DubLocal.
4. Do not disable Gatekeeper globally.

The first launch prepares DubLocal's managed local checkout and Python environment.
AI models are NOT bundled and remain opt-in from DubLocal's Model Manager.

Documentation: https://github.com/ArrowSK/dublocal/blob/main/docs/BETA_INSTALLATION.md
EOF

/usr/bin/hdiutil create \
  -volname "DubLocal ${VERSION} Beta" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DMG" >/dev/null

/usr/bin/hdiutil verify "$DMG" >/dev/null
[[ -s "$DMG" ]] || { echo "DMG was not created." >&2; exit 1; }

/usr/bin/shasum -a 256 "$DMG" > "$CHECKSUM"

printf 'Built unsigned beta package:\n  %s\n' "$DMG"
printf 'Checksum:\n  %s\n' "$CHECKSUM"
printf 'Version: %s\nRevision: %s\n' "$VERSION" "$BUILD_SHA"
