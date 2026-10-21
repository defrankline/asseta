"""Export the versioned OpenAPI contract to contracts/openapi.json (CI fails if it drifts: `--check`)."""

import json
import sys
from pathlib import Path

from asseta.main import create_app
from asseta.modules.identity.tokens import OidcTokenVerifier

TARGET = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


class _NoKeys:
    def key_for(self, token: str) -> object:
        raise RuntimeError("not used during export")


def main() -> int:
    app = create_app(token_verifier=OidcTokenVerifier(_NoKeys(), "n/a", "n/a"), idp_admin=None)
    rendered = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text() != rendered:
            print(f"{TARGET} is out of date; run scripts/export_openapi.py", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(rendered)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
