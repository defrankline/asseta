"""Seed ONE full demo tenant into a local docker-compose stack through the real API (run after demo_reset.py).

Usage (from backend/): uv run python scripts/demo_seed.py ../.env ../.demo/credentials.json

Creates "Kilimanjaro Earthworks" (verified, ACTIVE subscription at a negotiated TZS rate) with an owner, supervisor
and accountant (Keycloak users with generated passwords), machine categories, an operating area, job sites with
geofences, expense categories, five machines (four with simulated GPS trackers reporting through the real Traccar
gateway, one deliberately untracked), customers, hourly rate cards, bank-paid orders of machine hours (verified by the
accountant), the supervisor assigned to two machines with approved opening reports and one machine report waiting
for the owner's approval (ADR-008). A throwaway platform user and Keycloak client do the provisioning and are
deleted at the end. Demo passwords are written only to the credentials file (mode 600, gitignored), never printed."""

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from field_e2e_setup import TIMEOUT, Keycloak, Stack, check, cleanup, read_env, write_private

from asseta.tools.gps_simulator import route, send_osmand

TENANT = "Kilimanjaro Earthworks"
DOMAIN = "kilimanjaro-earthworks.example"
USERS = {  # role -> (email, first, last)
    "owner": (f"owner@{DOMAIN}", "Demo", "Owner"),
    "supervisor": (f"supervisor@{DOMAIN}", "Demo", "Supervisor"),
    "accountant": (f"accountant@{DOMAIN}", "Demo", "Accountant"),
}
SITES = [  # code, name, (lat, lon)
    ("KIG", "Kigamboni Bridge Approach", (-6.8390, 39.3060)),
    ("MBZ", "Mbezi Quarry", (-6.7135, 39.1580)),
    ("YRD", "Vingunguti Plant Yard", (-6.8445, 39.2350)),
]
MACHINES = [  # code, name, category, manufacturer, model, site (None = untracked)
    ("EX-01", "CAT 320 Excavator", "Excavators", "Caterpillar", "320", "KIG"),
    ("EX-02", "Komatsu PC200 Excavator", "Excavators", "Komatsu", "PC200-8", "MBZ"),
    ("WL-01", "CAT 950 Wheel Loader", "Wheel loaders", "Caterpillar", "950GC", "MBZ"),
    ("GR-01", "CAT 140 Motor Grader", "Graders", "Caterpillar", "140K", "YRD"),
    ("TP-01", "Howo 25t Tipper", "Tippers", "Sinotruk", "Howo 371", None),
]


RATES = {"Excavators": "95000", "Wheel loaders": "80000", "Graders": "110000", "Tippers": "65000"}  # per hour
ORDERS = [("RBL", "EX-01", "40"), ("DMK", "WL-01", "30")]  # customer, machine, prepaid hours


def square(lat: float, lon: float, half: float) -> dict[str, Any]:
    ring = [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half], [lon - half, lat + half]]
    return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


class Api:
    def __init__(self, stack: Stack, kc: Keycloak, email: str, tenant_id: str | None = None):
        self.s, self.kc, self.email, self.tenant_id = stack, kc, email, tenant_id

    def h(self) -> dict[str, str]:
        h = {**self.kc.bearer(self.email), "Idempotency-Key": str(uuid.uuid4())}
        if self.tenant_id:
            h["X-Tenant-ID"] = self.tenant_id
        return h

    def post(self, path: str, body: Any, what: str, status: int = 201) -> dict[str, Any]:
        return check(httpx.post(f"{self.s.api}{path}", headers=self.h(), json=body, timeout=TIMEOUT), status, what)

    def get(self, path: str, what: str) -> Any:
        r = httpx.get(f"{self.s.api}{path}", headers=self.h(), timeout=TIMEOUT)
        if r.status_code != 200:
            raise RuntimeError(f"{what}: HTTP {r.status_code}")
        return r.json()


def adopt(kc: Keycloak, email: str, first: str, last: str) -> str:
    """Give an API-created Keycloak user a generated password and a proper display name."""
    uid = kc.user(email, None)
    httpx.put(
        f"{kc.s.admin}/users/{uid}", headers=kc.h, json={"firstName": first, "lastName": last}, timeout=TIMEOUT
    ).raise_for_status()
    return uid


def onboard(stack: Stack, kc: Keycloak, platform: Api) -> str:
    today = datetime.now(UTC).date().isoformat()
    existing = platform.get("/platform/tenants?page_size=100", "list tenants")["items"]
    if any(t["display_name"] == TENANT for t in existing):
        raise SystemExit(f"refusing: tenant '{TENANT}' already exists (run demo_reset.py first)")
    email, first, last = USERS["owner"]
    created = platform.post(
        "/platform/tenants",
        {
            "legal_name": f"{TENANT} Ltd",
            "display_name": TENANT,
            "contact_name": f"{first} {last}",
            "contact_email": email,
            "timezone": "Africa/Dar_es_Salaam",
            "currency": "TZS",
            "owner": {"email": email, "first_name": first, "last_name": last},
            "subscription": {
                "start_date": today,
                "payment_terms_days": 14,
                "rate": {
                    "currency": "TZS",
                    "cadence": "MONTHLY",
                    "unit_price": "75000",
                    "minimum_billable_assets": 3,
                    "tax_name": "VAT",
                    "tax_rate_percent": "18",
                },
            },
        },
        "onboard tenant",
    )
    tid, sub = str(created["tenant"]["id"]), str(created["subscription_id"])
    platform.post(f"/platform/tenants/{tid}/verification", {"status": "VERIFIED", "note": "Demo"}, "verify", 200)
    platform.post(
        f"/platform/subscriptions/{sub}/transitions",
        {"to_status": "ACTIVE", "effective_date": today, "reason": "Demo agreement signed"},
        "activate",
        200,
    )
    adopt(kc, email, first, last)
    return tid


def seed_fleet(o: Api, platform: Api, stack: Stack, now: datetime) -> tuple[dict[str, str], dict[str, str]]:
    """Returns (machine ids by asset code, category ids by name)."""
    today = now.date().isoformat()
    cats = {
        n: o.post("/tenant/machine-categories", {"name": n}, f"category {n}")["id"] for n in {m[2] for m in MACHINES}
    }
    area = o.post("/tenant/operating-areas", {"code": "DSM", "name": "Dar es Salaam"}, "operating area")["id"]
    for code, name, (lat, lon) in SITES:
        o.post(
            "/tenant/job-sites",
            {"code": code, "name": name, "center": {"type": "Point", "coordinates": [lon, lat]}},
            f"site {code}",
        )
        o.post(
            "/tenant/geofences",
            {"name": f"{name} boundary", "kind": "ALLOWED_AREA", "polygon": square(lat, lon, 0.004)},
            f"geofence {code}",
        )
    model = platform.post(
        "/platform/tracker-models",
        {
            "manufacturer": "Simulated",
            "model": f"OsmAnd demo {uuid.uuid4().hex[:4]}",
            "adapter": "TRACCAR",
            "protocol": "osmand",
            "declared_capabilities": ["GNSS", "ACCURACY", "IGNITION"],
        },
        "tracker model",
    )["id"]
    sites = {code: pos for code, _, pos in SITES}
    traccar = f"http://localhost:{stack.env.get('ASSETA_TRACCAR_OSMAND_PORT', '5055')}"
    machines: dict[str, str] = {}
    for code, name, cat, make, mdl, site in MACHINES:
        mid = o.post(
            "/tenant/machines",
            {
                "asset_code": code,
                "name": name,
                "category_id": cats[cat],
                "operating_area_id": area,
                "manufacturer": make,
                "model": mdl,
                "meter_decimal_places": 1,
            },
            f"machine {code}",
        )["id"]
        machines[code] = mid
        o.post("/tenant/billing/enrollments", {"machine_id": mid, "effective_from": today}, f"enroll {code}")
        if site is None:
            continue  # deliberately untracked: the map must show it as unknown, not invent a position
        device = "35" + str(uuid.uuid4().int)[:13]
        tracker = o.post(
            "/tenant/trackers",
            {"tracker_model_id": model, "external_id": device, "label": f"{code} tracker"},
            f"tracker {code}",
        )["id"]
        start = now - timedelta(minutes=4)
        o.post(
            f"/tenant/trackers/{tracker}/assign",
            {"machine_id": mid, "effective_from": (start - timedelta(minutes=1)).isoformat()},
            f"assign tracker {code}",
        )
        lat, lon = sites[site]
        # A short move that ends parked with the engine off: an idle demo fleet must not report engines running.
        fixes = route(
            [(lat - 0.001, lon - 0.001), (lat + 0.001, lon + 0.001)],
            start,
            6.0,
            12,
            dwell_points=1,
            park_engine_off=True,
        )
        if send_osmand(traccar, device, fixes) != len(fixes):
            raise RuntimeError(f"Traccar rejected fixes for {code}")
    return machines, cats


def photo(api: Api, key: str) -> str:
    """A placeholder meter photo (unique bytes; the server flags a photo used twice), uploaded as METER_PHOTO."""
    h = {k: v for k, v in api.h().items() if k != "Content-Type"}
    data = b"\xff\xd8\xff\xe0" + uuid.uuid5(uuid.NAMESPACE_URL, key).bytes * 4 + uuid.uuid4().bytes
    r = httpx.post(
        f"{api.s.api}/tenant/attachments",
        headers=h,
        files={"file": (f"{key}.jpg", data, "image/jpeg")},
        data={"purpose": "METER_PHOTO"},
        timeout=TIMEOUT,
    )
    return str(check(r, 201, f"meter photo {key}")["id"])


def report(
    sup: Api, machine_id: str, code: str, reading: str, at: datetime, site: tuple[float, float], lines: list[Any]
) -> dict[str, Any]:
    """A machine report as the supervisor's app sends it: a DAILY reading (photo + OCR) and the lines (none for an
    opening report: the machine's first reading)."""
    lat, lon = site
    capture = {
        "id": str(uuid.uuid4()),
        "machine_id": machine_id,
        "kind": "DAILY",
        "capture_mode": "AUTOMATIC",
        "reading": reading,
        "ocr_value": reading,
        "ocr_confidence": 0.96,
        "ocr_engine": "demo-seed",
        "photo_attachment_id": photo(sup, f"{code}-{reading}"),
        "gps": {
            "status": "FIX",
            "latitude": lat,
            "longitude": lon,
            "accuracy_m": 8.0,
            "captured_at": (at - timedelta(seconds=5)).isoformat(),
            "provider": "fused",
        },
        "device_id": "demo-seed-phone",
        "captured_at": at.isoformat(),
    }
    body = {"id": str(uuid.uuid4()), "machine_id": machine_id, "opening": not lines, "lines": lines, "capture": capture}
    return sup.post("/tenant/machine-reports", body, f"{'opening' if not lines else 'machine'} report {code}")


def seed_work(o: Api, kc: Keycloak, machines: dict[str, str], categories: dict[str, str], now: datetime) -> None:
    # Expense categories: without them nothing can be recorded on the Expenses screen or in the field apps.
    for code, name in (
        ("SPARES", "Repairs and spares"),
        ("TYRES", "Tyres"),
        ("TRANSPORT", "Low-bed transport"),
        ("ALLOWANCE", "Operator allowances"),
        ("SITE", "Site sundries"),
    ):
        o.post("/tenant/expense-categories", {"code": code, "name": name}, f"expense category {code}")
    customers = {
        code: o.post("/tenant/customers", {"code": code, "name": name}, f"customer {code}")["id"]
        for code, name in (("RBL", "Road Builders Ltd"), ("DMK", "Dam Makers Co"), ("CTY", "City Works Department"))
    }
    # The hourly rate card per machine category prices the hours customers buy.
    for name, cat in categories.items():
        o.post(
            "/tenant/rate-cards",
            {"machine_category_id": cat, "hourly_rate": RATES[name], "minimum_hours": "4", "reason": "Standard rate"},
            f"rate card {name}",
        )
    people = {}
    for role in ("supervisor", "accountant"):
        email, first, last = USERS[role]
        o.post(
            "/tenant/access/members",
            {"email": email, "first_name": first, "last_name": last, "role_key": role},
            f"invite {role}",
        )
        people[role] = adopt(kc, email, first, last)
    staff = o.post(
        "/tenant/staff",
        {"full_name": "Demo Supervisor", "kind": "SUPERVISOR", "keycloak_subject": people["supervisor"]},
        "supervisor staff",
    )["id"]
    o.post("/tenant/staff", {"full_name": "Demo Operator", "kind": "OPERATOR"}, "operator staff")
    assigned = now - timedelta(hours=4)
    for code in ("EX-01", "WL-01"):
        o.post(
            f"/tenant/machines/{machines[code]}/assignments",
            {"staff_member_id": staff, "role": "SUPERVISOR", "effective_from": assigned.isoformat()},
            f"assign supervisor {code}",
        )
    # Customer hours (orders): the owner records bank-paid orders, the accountant verifies the money (hours active).
    accountant = Api(o.s, kc, USERS["accountant"][0], o.tenant_id)
    for number, (customer, machine, hours) in enumerate(ORDERS, start=1):
        order = o.post(
            "/tenant/hours-purchases",
            {
                "customer_id": customers[customer],
                "machine_id": machines[machine],
                "hours": hours,
                "payment": {"method": "BANK", "reference": f"CRDB-DEMO-{number:03d}", "received_at": now.isoformat()},
                "note": "Prepaid machine hours",
            },
            f"order {customer} {machine}",
        )
        accountant.post(
            f"/tenant/customer-payments/{order['payment']['id']}/decision",
            {"verified": True, "note": "Seen on the bank statement"},
            f"verify order {customer} {machine}",
            200,
        )
    # Machine reports: each supervised machine starts with an opening report (approved by the owner); EX-01 then
    # reports its first hours for RBL, left waiting for the owner's approval.
    sup = Api(o.s, kc, USERS["supervisor"][0], o.tenant_id)
    sites = {code: pos for code, _, pos in SITES}
    site_of = {m[0]: str(m[5]) for m in MACHINES}
    for code, reading in (("EX-01", "1250.0"), ("WL-01", "860.0")):
        opening = report(sup, machines[code], code, reading, now - timedelta(hours=3), sites[site_of[code]], [])
        o.post(f"/tenant/machine-reports/{opening['id']}/approve", {"note": "Starting reading"}, f"approve {code}", 200)
    report(
        sup,
        machines["EX-01"],
        "EX-01",
        "1252.5",
        now - timedelta(minutes=5),
        sites[site_of["EX-01"]],
        [{"kind": "CUSTOMER", "customer_id": customers["RBL"], "hours": "2.5"}],
    )


def main(argv: list[str]) -> int:
    stack, out = Stack(read_env(argv[0])), argv[1]
    kc = Keycloak(stack)
    kc.create_client()
    platform_email = f"field-e2e-demo-seeder-{uuid.uuid4().hex[:6]}@asseta.local"  # throwaway; deleted below
    seeder_uid = kc.user(platform_email, "/platform/platform-owner")
    try:
        platform = Api(stack, kc, platform_email)
        tid = onboard(stack, kc, platform)
        o = Api(stack, kc, USERS["owner"][0], tid)
        now = datetime.now(UTC)
        machines, categories = seed_fleet(o, platform, stack, now)
        seed_work(o, kc, machines, categories, datetime.now(UTC))
        creds = {
            "web": "http://localhost:5173",
            "tenant": TENANT,
            "tenant_id": tid,
            "accounts": {role: {"email": e, "password": kc.passwords[e]} for role, (e, _, _) in USERS.items()},
        }
        write_private(out, creds)
    finally:
        cleanup(stack, {"client_uuid": kc.client_uuid, "user_ids": [seeder_uid]})
    print(f"DEMO OK tenant={TENANT} id={tid} machines={len(machines)} credentials={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
