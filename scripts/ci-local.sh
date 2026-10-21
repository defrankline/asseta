#!/usr/bin/env bash
# Runs the same gates as .github/workflows/ci.yml locally. Use before every commit:
#   scripts/ci-local.sh            # backend + web
#   scripts/ci-local.sh --all      # + Android + iOS
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== backend"
cd "$ROOT/backend"
uv run ruff check src tests migrations scripts
uv run ruff format --check src tests migrations scripts
uv run mypy src tests scripts
uv run alembic check
uv run python scripts/export_openapi.py --check
uv run pytest -q -p no:warnings

echo "== web"
cd "$ROOT/web"
before="$(shasum src/api/generated/schema.ts)"
node scripts/gen-api.mjs --strict >/dev/null
if [[ "$before" != "$(shasum src/api/generated/schema.ts)" ]]; then
  echo "web/src/api/generated/schema.ts was stale vs contracts/openapi.json (now regenerated) — review and commit"; exit 1
fi
npm run lint
npm run typecheck
npm test -- --run
npm run build

if [[ "${1:-}" == "--all" ]]; then
  echo "== android"
  (cd "$ROOT/mobile/android" && ./gradlew assembleDebug testDebugUnitTest lint --console=plain)
  echo "== ios"
  (cd "$ROOT/mobile/ios" && xcodegen generate && (cd AssetaKit && swift test) && \
   for s in AssetaSupervisor AssetaOwner; do
     xcodebuild -project Asseta.xcodeproj -scheme "$s" -destination 'generic/platform=iOS Simulator' \
       CODE_SIGNING_ALLOWED=NO build -quiet; done)
fi
echo "ALL GATES PASSED"
