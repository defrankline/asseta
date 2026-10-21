#!/usr/bin/env bash
# Renders branding/asseta-mark.svg into the 1024x1024 iOS app icon (opaque, no alpha).
# Requires: rsvg-convert (brew install librsvg) and sips (macOS).
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
svg="$here/../../branding/asseta-mark.svg"
out="$here/Apps/Shared/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# Fill the transparent rounded corners with brand Slate; iOS applies its own mask.
rsvg-convert -w 1024 -h 1024 -b '#0F2A3D' "$svg" -o "$tmp/icon.png"
# App Store icons must not contain an alpha channel: round-trip through JPEG (max quality).
sips -s format jpeg -s formatOptions 100 "$tmp/icon.png" --out "$tmp/icon.jpg" >/dev/null
sips -s format png "$tmp/icon.jpg" --out "$out" >/dev/null
sips -g pixelWidth -g pixelHeight -g hasAlpha "$out"
