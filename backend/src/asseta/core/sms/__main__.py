"""Manual test send using the configured provider (`ASSETA_SMS_PROVIDER`; console by default, which sends nothing).

cd backend && uv run python -m asseta.core.sms --to 0712345678 --text "Asseta test"
"""

import argparse
import uuid

from asseta.core.sms import build_sms_client, get_sms_settings


def main() -> None:
    p = argparse.ArgumentParser(description="Send a test SMS through the configured provider")
    p.add_argument("--to", action="append", required=True, help="recipient number (repeatable)")
    p.add_argument("--text", required=True)
    a = p.parse_args()
    settings = get_sms_settings()
    result = build_sms_client(settings).send(a.to, a.text, reference=f"manual-{uuid.uuid4().hex[:12]}")
    print(f"SMS {result.provider}: {len(result.recipients)} recipient(s), reference {result.reference}")


if __name__ == "__main__":
    main()
