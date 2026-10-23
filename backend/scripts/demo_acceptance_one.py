"""Live demonstration of prompt.md §10 #1 against a local docker-compose stack, through the real API and Keycloak.

Usage (from backend/): uv run python scripts/demo_acceptance_one.py ../.env ../.demo/acceptance-one.json

The Platform Owner creates two isolated tenants with different negotiated prices: "Solo Excavation Demo" (1 asset,
monthly) and "Mega Fleet Demo" (100 assets, yearly, discount, VAT, minimum commitment). It enrolls the machines,
swaps the tracker on the solo machine, generates each tenant's first subscription invoice and checks the totals,
that the swap did not add a billable asset, and that neither tenant can read the other's data. The tenants stay in
the stack so they can be inspected in the platform console. Evidence is written to
docs/evidence/acceptance/<date>-criterion-1.md; generated owner passwords only to the credentials file (mode 600,
gitignored), never printed. A throwaway platform user and Keycloak client do the provisioning and are deleted."""

import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_seed import Api, adopt
from field_e2e_setup import TIMEOUT, Keycloak, Stack, cleanup, read_env, write_private

SOLO = (
    "Solo Excavation Demo",
    "solo-excavation.example",
    1,
    {"cadence": "MONTHLY", "unit_price": "75000", "minimum_billable_assets": 1},
)
FLEET = (
    "Mega Fleet Demo",
    "mega-fleet.example",
    100,
    {"cadence": "YEARLY", "unit_price": "600000", "discount_percent": "10", "minimum_billable_assets": 50},
)
EVIDENCE = Path(__file__).resolve().parents[2] / "docs/evidence/acceptance"


def onboard(platform: Api, kc: Keycloak, name: str, domain: str, rate: dict[str, Any], today: str) -> dict[str, str]:
    email = f"owner@{domain}"
    created = platform.post(
        "/platform/tenants",
        {
            "legal_name": f"{name} Ltd",
            "display_name": name,
            "contact_name": "Demo Owner",
            "contact_email": email,
            "timezone": "Africa/Dar_es_Salaam",
            "currency": "TZS",
            "owner": {"email": email, "first_name": "Demo", "last_name": "Owner"},
            "subscription": {
                "start_date": today,
                "payment_terms_days": 14,
                "rate": {"currency": "TZS", "tax_name": "VAT", "tax_rate_percent": "18", **rate},
            },
        },
        f"onboard {name}",
    )
    tid, sub = str(created["tenant"]["id"]), str(created["subscription_id"])
    platform.post(
        f"/platform/tenants/{tid}/verification", {"status": "VERIFIED", "note": "Acceptance #1"}, "verify", 200
    )
    platform.post(
        f"/platform/subscriptions/{sub}/transitions",
        {"to_status": "ACTIVE", "effective_date": today, "reason": "Acceptance #1 agreement"},
        "activate",
        200,
    )
    adopt(kc, email, "Demo", "Owner")
    return {"tenant_id": tid, "subscription_id": sub, "email": email}


def add_machines(o: Api, prefix: str, count: int, today: str) -> list[str]:
    cat = o.post("/tenant/machine-categories", {"name": "Excavators"}, "category")["id"]
    ids = []
    for i in range(1, count + 1):
        mid = o.post(
            "/tenant/machines",
            {
                "asset_code": f"{prefix}-{i:03d}",
                "name": f"Excavator {i:03d}",
                "category_id": cat,
                "meter_decimal_places": 1,
            },
            f"machine {prefix}-{i:03d}",
        )["id"]
        o.post("/tenant/billing/enrollments", {"machine_id": mid, "effective_from": today}, f"enroll {prefix}-{i:03d}")
        ids.append(mid)
    return ids


def main(argv: list[str]) -> int:
    stack, out = Stack(read_env(argv[0])), argv[1]
    kc = Keycloak(stack)
    kc.create_client()
    platform_email = f"acceptance-one-{uuid.uuid4().hex[:6]}@asseta.local"  # throwaway; deleted below
    seeder_uid = kc.user(platform_email, "/platform/platform-owner")
    lines: list[str] = []
    try:
        platform = Api(stack, kc, platform_email)
        existing = {t["display_name"] for t in platform.get("/platform/tenants?page_size=100", "tenants")["items"]}
        if existing & {SOLO[0], FLEET[0]}:
            raise SystemExit("refusing: acceptance tenants already exist")
        now = datetime.now(UTC)
        today = now.date().isoformat()
        tenants = {}
        for name, domain, count, rate in (SOLO, FLEET):
            t = onboard(platform, kc, name, domain, rate, today)
            o = Api(stack, kc, t["email"], t["tenant_id"])
            t["machines"] = add_machines(o, "SOLO" if count == 1 else "FLEET", count, today)  # type: ignore[assignment]
            tenants[name] = (t, o)
        (solo, so), (fleet, _) = tenants[SOLO[0]], tenants[FLEET[0]]

        # Tracker swap on the solo machine: the replacement takes over as primary; billing still counts one asset.
        model = platform.post(
            "/platform/tracker-models",
            {
                "manufacturer": "Simulated",
                "model": f"Acceptance {uuid.uuid4().hex[:4]}",
                "adapter": "TRACCAR",
                "protocol": "osmand",
                "declared_capabilities": ["GNSS"],
            },
            "tracker model",
        )["id"]
        machine = solo["machines"][0]
        old, new = (
            so.post(
                "/tenant/trackers",
                {"tracker_model_id": model, "external_id": "35" + str(uuid.uuid4().int)[:13], "label": label},
                label,
            )["id"]
            for label in ("SOLO-001 tracker (original)", "SOLO-001 tracker (replacement)")
        )
        so.post(f"/tenant/trackers/{old}/assign", {"machine_id": machine, "effective_from": now.isoformat()}, "assign")
        so.post(
            f"/tenant/trackers/{new}/assign",
            {
                "machine_id": machine,
                "effective_from": datetime.now(UTC).isoformat(),
                "replace_existing_primary": True,
                "reason": "Original unit failed",
            },
            "swap",
        )
        sub = platform.get(f"/platform/tenants/{solo['tenant_id']}/subscription", "solo subscription")
        assert sub["enrolled_assets"] == 1, sub

        invoices = {}
        for name, (t, _) in tenants.items():
            r = platform.post(
                f"/platform/subscriptions/{t['subscription_id']}/invoices/generate",
                {"as_of": today},
                f"invoice {name}",
                200,
            )
            [inv] = r["created"]
            invoices[name] = inv
        s, f = invoices[SOLO[0]], invoices[FLEET[0]]
        # 1 x 75,000 + 18% VAT; 100 x 600,000 = 60,000,000 - 10% = 54,000,000 + 18% VAT = 63,720,000
        assert Decimal(s["total"]) == Decimal("88500") and s["billable_assets"] == 1, s
        assert [ln["line_type"] for ln in s["lines"]].count("ASSET_SUBSCRIPTION") == 1, s["lines"]
        assert Decimal(f["total"]) == Decimal("63720000") and f["billable_assets"] == 100, f

        # Isolation: each owner sees only its own invoices; the other tenant's ids and header are refused.
        assert [i["id"] for i in so.get("/tenant/billing/invoices", "solo invoices")] == [s["id"]]
        foreign = httpx.get(f"{stack.api}/tenant/machines/{fleet['machines'][0]}", headers=so.h(), timeout=TIMEOUT)
        assert foreign.status_code == 404, foreign.text
        hdr = {**so.h(), "X-Tenant-ID": fleet["tenant_id"]}
        crossed = httpx.get(f"{stack.api}/tenant/machines", headers=hdr, timeout=TIMEOUT)
        assert crossed.status_code == 403, crossed.text

        lines = [
            f"# Acceptance §10 #1 — live demonstration ({today})",
            "",
            "Run: `uv run python scripts/demo_acceptance_one.py ../.env ../.demo/acceptance-one.json` against the "
            "local Compose stack (real API, Keycloak, PostgreSQL RLS). Tenants left in place for inspection.",
            "",
            "| Tenant | Assets | Negotiated rate | Invoice | Period | Billable | Total (TZS) |",
            "|---|---|---|---|---|---|---|",
            f"| {SOLO[0]} | 1 | 75,000 / asset / month, VAT 18% | {s['invoice_number']} | {s['period_start']} → "
            f"{s['period_end']} | {s['billable_assets']} | {Decimal(s['total']):,.2f} |",
            f"| {FLEET[0]} | 100 | 600,000 / asset / year, discount 10%, VAT 18%, minimum 50 | {f['invoice_number']} | "
            f"{f['period_start']} → {f['period_end']} | {f['billable_assets']} | {Decimal(f['total']):,.2f} |",
            "",
            "* Tracker swap on SOLO-001 (original → replacement, `replace_existing_primary`): subscription still has "
            f"{sub['enrolled_assets']} enrolled asset; the invoice has exactly one ASSET_SUBSCRIPTION line.",
            "* Isolation: the solo owner lists only its own platform invoice; reading a Mega Fleet machine id returns "
            f"{foreign.status_code}; sending Mega Fleet's id in X-Tenant-ID returns {crossed.status_code} "
            f"{crossed.json()['error']['code']}.",
            "* Invoice amounts are Decimal strings from the API; invoice numbers are distinct per tenant.",
        ]
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / f"{today}-criterion-1.md").write_text("\n".join(lines) + "\n")
        write_private(
            out,
            {
                n: {"tenant_id": t["tenant_id"], "email": t["email"], "password": kc.passwords[t["email"]]}
                for n, (t, _) in tenants.items()
            },
        )
    finally:
        cleanup(stack, {"client_uuid": kc.client_uuid, "user_ids": [seeder_uid]})
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
