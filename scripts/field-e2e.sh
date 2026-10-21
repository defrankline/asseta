#!/usr/bin/env bash
# Gate 4 live E2E: the native apps' REAL sync clients against the running docker compose stack (API + Keycloak).
#   scripts/field-e2e.sh            # uses ./.env (or ASSETA_ENV_FILE)
# For each platform: build the tests first, then create a fresh fixture (throwaway Keycloak client/users, tenant,
# APPROVED job, supervisor; access tokens live 300 s) and run that platform's live test right away. The fixture file
# (mode 600, private temp dir) is the only place secrets go; nothing secret is printed. Keycloak throwaways are
# deleted on exit, pass or fail. Exits non-zero if a live test fails or was skipped.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ASSETA_ENV_FILE:-$ROOT/.env}"
WORK="$(mktemp -d)"
chmod 700 "$WORK"
FIXTURES=()

cleanup() {
  for f in "${FIXTURES[@]+"${FIXTURES[@]}"}"; do
    (cd "$ROOT/backend" && uv run python scripts/field_e2e_setup.py --cleanup "$ENV_FILE" "$f") || true
  done
  rm -rf "$WORK"
}
trap cleanup EXIT

setup() { # $1 = fixture file (registered for cleanup before it is created)
  FIXTURES+=("$1")
  (cd "$ROOT/backend" && uv run python scripts/field_e2e_setup.py "$ENV_FILE" "$1")
}

curl -fsS -o /dev/null "http://localhost:${ASSETA_API_PORT:-8000}/api/v1/health/live" \
  || { echo "API is not reachable: start the stack with docker compose up -d"; exit 1; }

echo "== build (before minting short-lived tokens)"
(cd "$ROOT/mobile/ios/AssetaKit" && swift build --build-tests)
(cd "$ROOT/mobile/android" && ./gradlew :core:sync:compileDebugUnitTestKotlin --console=plain -q)

echo "== iOS live sync (AssetaSyncLiveTests)"
IOS_FIXTURE="$WORK/ios.json"
setup "$IOS_FIXTURE"
IOS_LOG="$WORK/ios.log"
set +e
(cd "$ROOT/mobile/ios/AssetaKit" && ASSETA_LIVE_E2E="$IOS_FIXTURE" swift test --skip-build --filter AssetaSyncLiveTests) \
  >"$IOS_LOG" 2>&1
IOS_STATUS=$?
set -e
grep -E "^(✔|✘|◇ Test|.*error)" "$IOS_LOG" || true
if [[ $IOS_STATUS -ne 0 ]] || ! grep -q "✔ Test openingCaptureWithPhotoSyncsExactlyOnceAgainstTheLiveBackend() passed" "$IOS_LOG"; then
  echo "iOS live sync FAILED (or was skipped)"; grep -E "Expectation failed|recorded an issue" "$IOS_LOG" || true; exit 1
fi
echo "iOS live sync PASSED"

echo "== Android live sync (SyncLiveTest)"
ANDROID_FIXTURE="$WORK/android.json"
setup "$ANDROID_FIXTURE"
RESULT="$ROOT/mobile/android/core/sync/build/test-results/testDebugUnitTest/TEST-com.asseta.core.sync.SyncLiveTest.xml"
rm -f "$RESULT"
set +e
(cd "$ROOT/mobile/android" && ASSETA_LIVE_E2E="$ANDROID_FIXTURE" ./gradlew :core:sync:testDebugUnitTest \
  --tests com.asseta.core.sync.SyncLiveTest --rerun --console=plain -q 2>&1 | grep -v "^WARNING")
set -e
SUMMARY="$(grep -o 'tests="[0-9]*" skipped="[0-9]*" failures="[0-9]*" errors="[0-9]*"' "$RESULT" 2>/dev/null | head -n 1 || true)"
echo "Android result: ${SUMMARY:-missing}"
if [[ "$SUMMARY" != 'tests="1" skipped="0" failures="0" errors="0"' ]]; then
  echo "Android live sync FAILED (or was skipped)"; grep -A3 "<failure" "$RESULT" 2>/dev/null | head -n 8 || true; exit 1
fi
echo "Android live sync PASSED"
echo "FIELD E2E PASSED"
