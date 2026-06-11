#!/usr/bin/env bash
# Download GOV.UK Frontend precompiled release (paired with govuk-frontend-jinja 4.x → v6.0.0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${GOVUK_VERSION:-6.0.0}"
DEST="$ROOT/govuk_frontend"
ZIP="/tmp/release-v${VERSION}.zip"
URL="https://github.com/alphagov/govuk-frontend/releases/download/v${VERSION}/release-v${VERSION}.zip"

rm -rf "$DEST"
curl -fsSL -o "$ZIP" "$URL"
unzip -q "$ZIP" -d "$DEST"
echo "Installed GOV.UK Frontend ${VERSION} to ${DEST}"
