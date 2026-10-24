"""Demo data for ONE existing tenant on a live (production) stack, through the real API (docs/deployment-live.md,
"Demo tenant data"). Run through scripts/seed-demo-tenant.sh, which starts it in a throwaway container of the API
image on the compose network.

  seed    Finds the tenant (registration number, else exact name), checks it is verified, ACTIVE and entitled, then
          acts on it under a temporary managed-service mandate (DEC-018): machines, sites + geofences, enrollments,
          simulated trackers, staff, two demo users (supervisor, accountant), customers, contracts, jobs. Sends a
          few hours of GPS history and leaves the fleet parked. Refuses when the tenant already has machines.
  feed    Keeps the demo fleet live for --minutes: working machines move slowly on their site with the engine on
          (in work runs shorter than the tenant's unreported-engine-activity threshold), parked machines report
          stationary with the ignition off. Time only moves forward (one writer, a lock file, the last sent time
          persisted), so no overlapping batches and no "Implausible GPS jump" alerts. No API access needed.
  field   (--dry-run) Plays a recent field history as the demo supervisor, through the offline sync protocol the
          phones use (device session, resumable evidence upload, POST /sync/push), so every server rule applies
          (meter checks, phone GPS vs tracker, exceptions, expense policy, cash custody, audit). J-2026-103 started
          and completed with a customer acknowledgement, J-2026-101/102 started and running, work logs, fuel,
          cash expenses, one customer cash collection and one handover; J-2026-104 stays ready to start. Never
          before the jobs' approval. Refuses once any field activity exists; a re-run after a failure re-sends the
          same operations (kept in the state file), which the server answers as duplicates.
  status  Platform-level facts; without --quick also counts the tenant's data (under a short mandate).
  retire  (--yes) Soft-removes what `seed` created: cancels jobs, retires trackers, ends enrollments, deactivates
          machines, sites, geofences, contracts, customers and staff, revokes and disables the demo users. Nothing
          is deleted (the audit trail and history stay).

Production safety: the platform side uses a throwaway platform user + Keycloak confidential client, both deleted in
`finally`. Tenant changes happen only under the mandate (every audit event carries it); the mandate is granted for
today and tomorrow only and is ended in `finally`. No existing user is ever read, changed or logged in as: the demo
users must not exist yet, and their generated passwords go only to the credentials file (mode 600). `field` signs
in only as the demo supervisor `seed` created: the e-mail must be supervisor.<slug>@<demo domain> in both the
credentials and the state file, the Keycloak user id and the app user id must be the ones `seed` recorded, and the
password is read from the credentials file only (never printed). It uses its own throwaway Keycloak client (deleted
in `finally`); the cash float, which only the office can issue, goes through the same temporary mandate as `seed`.

Endpoints (environment; defaults are the production compose network):
  ASSETA_DEMO_API_URL (http://api:8000), ASSETA_DEMO_KEYCLOAK_URL (http://keycloak:8080/auth),
  ASSETA_DEMO_OSMAND_URL (http://traccar:5055), ASSETA_DEMO_TRACCAR_API_URL (http://traccar:8082)
Secrets (environment only, never printed): KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD; optional
  ASSETA_TRACCAR_GATEWAY_KEY (direct gateway delivery when Traccar refuses unregistered devices) and
  TRACCAR_ADMIN_EMAIL / TRACCAR_ADMIN_PASSWORD (register the simulated devices in Traccar instead, DEC-017).
"""

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import random
import secrets
import signal
import struct
import sys
import time
import uuid
import zlib
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # local runs (uv); the image has it installed
from asseta.tools.gps_simulator import KMH_TO_KNOTS, Fix, traccar_payload

TIMEOUT = 30.0
EARTH_M_PER_DEG = 111_320.0


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, "") or default


API = env("ASSETA_DEMO_API_URL", "http://api:8000").rstrip("/") + "/api/v1"
KC = env("ASSETA_DEMO_KEYCLOAK_URL", "http://keycloak:8080/auth").rstrip("/")
OSMAND = env("ASSETA_DEMO_OSMAND_URL", "http://traccar:5055").rstrip("/")
TRACCAR_API = env("ASSETA_DEMO_TRACCAR_API_URL", "http://traccar:8082").rstrip("/")
WEB = env("ASSETA_DEMO_WEB_URL", "https://asseta.co.tz")


class Refuse(Exception):
    """A precondition failed: explain and stop (exit status 2) without changing anything further."""

    def __init__(self, *lines: str):
        super().__init__("REFUSED: " + "\n  ".join(lines))


class ApiError(RuntimeError):
    def __init__(self, what: str, r: httpx.Response):
        code, message = "", ""
        with contextlib.suppress(ValueError, AttributeError):
            err = r.json().get("error", {})
            code, message = str(err.get("code", "")), str(err.get("message", ""))
        self.status, self.code = r.status_code, code
        super().__init__(f"{what}: HTTP {r.status_code} {code} {message}".strip())  # never the request (tokens)


def log(msg: str) -> None:
    print(f"[demo] {msg}", flush=True)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def norm(s: str | None) -> str:
    return " ".join((s or "").split()).casefold()


# --- demo content ----------------------------------------------------------------------------------------------
REGIONS: dict[str, dict[str, Any]] = {  # 3 sites: road works, quarry, plant yard (lat, lon)
    "dar-es-salaam": {
        "area": ("DSM", "Dar es Salaam"),
        "sites": [
            ("KBM", "Kibamba-Kiluvya Road Widening", (-6.7445, 39.0905)),
            ("KGQ", "Kigamboni Gravel Quarry", (-6.8650, 39.3180)),
            ("TBY", "Tabata Plant Yard", (-6.8330, 39.2320)),
        ],
    },
    "dodoma": {
        "area": ("DOD", "Dodoma"),
        "sites": [
            ("IHR", "Ihumwa Ring Road Earthworks", (-6.1735, 35.8890)),
            ("MSQ", "Msalato Murram Pit", (-6.0950, 35.8010)),
            ("NZY", "Nzuguni Plant Yard", (-6.1830, 35.7810)),
        ],
    },
    "arusha": {
        "area": ("ARU", "Arusha"),
        "sites": [
            ("USR", "Usa River Bypass Works", (-3.3700, 36.8530)),
            ("KSQ", "Kisongo Quarry", (-3.3880, 36.5900)),
            ("NJY", "Njiro Plant Yard", (-3.4040, 36.7020)),
        ],
    },
    "mwanza": {
        "area": ("MWZ", "Mwanza"),
        "sites": [
            ("IGR", "Igogo-Buhongwa Road Works", (-2.5350, 32.8950)),
            ("BHQ", "Buhongwa Quarry", (-2.5980, 32.8780)),
            ("IGY", "Igoma Plant Yard", (-2.4730, 32.9520)),
        ],
    },
}
# code, name, category, make, model, year, site index (None = deliberately untracked), mode, engine hours
MACHINES: list[tuple[str, str, str, str, str, int, int | None, str, float]] = [
    ("EX-01", "CAT 320D2 Excavator", "Excavators", "Caterpillar", "320D2", 2019, 0, "work", 6421.4),
    ("EX-02", "Komatsu PC210 Excavator", "Excavators", "Komatsu", "PC210-10M0", 2021, 1, "work", 3180.2),
    ("WL-01", "CAT 950GC Wheel Loader", "Wheel loaders", "Caterpillar", "950GC", 2020, 1, "work", 5012.7),
    ("TP-01", "Sinotruk Howo 371 Tipper 25t", "Tippers", "Sinotruk", "Howo 371 6x4", 2022, 0, "work", 2210.5),
    ("GR-01", "CAT 140K Motor Grader", "Graders", "Caterpillar", "140K", 2018, 0, "idle", 8940.0),
    ("RL-01", "Bomag BW 213 Vibratory Roller", "Rollers", "Bomag", "BW 213 D-5", 2017, 2, "idle", 7302.9),
    ("TP-02", "Sinotruk Howo 371 Tipper 25t", "Tippers", "Sinotruk", "Howo 371 6x4", 2022, None, "untracked", 0.0),
]
HOME_OFFSETS = [(0.0009, -0.0007), (-0.0006, 0.0010), (0.0011, 0.0004), (-0.0010, -0.0008), (0.0004, 0.0012)]
CUSTOMERS = [("PRC", "Pwani Road Contractors Ltd"), ("MBD", "Msasani Bay Developers Ltd"), ("MMH", "Mji Mpya Housing")]
# job number, customer, machine, hourly rate, final state
JOBS = [
    ("J-2026-101", "PRC", "EX-01", "95000", "APPROVED"),
    ("J-2026-102", "MBD", "EX-02", "90000", "APPROVED"),
    ("J-2026-103", "MBD", "WL-01", "80000", "APPROVED"),
    ("J-2026-104", "PRC", "TP-01", "65000", "APPROVED"),
    ("J-2026-105", "MMH", "GR-01", "110000", "PENDING_APPROVAL"),
    ("J-2026-106", "MMH", "RL-01", "70000", "DRAFT"),
]
EXPENSE_CATEGORIES = [
    ("FUEL", "Diesel and lubricants"),
    ("SPARES", "Repairs and spares"),
    ("TYRES", "Tyres"),
    ("TRANSPORT", "Low-bed transport"),
    ("ALLOWANCE", "Operator allowances"),
]
OPERATORS = ["Juma Mwakyusa", "Baraka Kimaro", "Neema Massawe", "Hassan Mfinanga", "Salma Ngowi", "Peter Lyimo"]
USERS = {"supervisor": ("Daudi", "Mollel"), "accountant": ("Rehema", "Nyirenda")}


# --- Keycloak (admin REST + the throwaway confidential client) ---------------------------------------------------
class KeycloakAdmin:
    def __init__(self) -> None:
        self.user, self.password = env("KEYCLOAK_ADMIN_USER"), env("KEYCLOAK_ADMIN_PASSWORD")
        if not self.user or not self.password:
            raise Refuse("KEYCLOAK_ADMIN_USER / KEYCLOAK_ADMIN_PASSWORD are not set (the wrapper passes them)")
        self.realm = f"{KC}/admin/realms/asseta"
        self._token, self._expires = "", 0.0

    def h(self) -> dict[str, str]:
        if time.monotonic() >= self._expires:  # master-realm admin tokens live ~60 s: renew as needed
            r = httpx.post(
                f"{KC}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": self.user,
                    "password": self.password,
                },
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                raise Refuse(
                    f"Keycloak admin login failed (HTTP {r.status_code}) at {KC}.",
                    "Check KEYCLOAK_ADMIN_USER / KEYCLOAK_ADMIN_PASSWORD in .env.production (they must name a",
                    "working master-realm admin; see docs/deployment-live.md 'Keycloak admin console').",
                )
            body = r.json()
            self._token = str(body["access_token"])
            self._expires = time.monotonic() + max(5, int(body.get("expires_in", 60)) - 15)
        return {"Authorization": f"Bearer {self._token}"}

    def _ok(self, r: httpx.Response, what: str, *ok: int) -> httpx.Response:
        if r.status_code not in (ok or (200,)):
            detail = ""
            with contextlib.suppress(ValueError, AttributeError):
                body = r.json()
                detail = str(body.get("errorMessage") or body.get("error") or "")[:200]
            raise RuntimeError(f"Keycloak {what}: HTTP {r.status_code} {detail}".strip())
        return r

    def users_by_email(self, email: str) -> list[dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        for key in ("email", "username"):
            r = httpx.get(
                f"{self.realm}/users", params={key: email, "exact": "true"}, headers=self.h(), timeout=TIMEOUT
            )
            for u in self._ok(r, "user lookup").json():
                found[str(u["id"])] = u
        return list(found.values())

    def create_user(self, email: str, first: str, last: str, group_path: str) -> tuple[str, str]:
        """A NEW user (refuses if the e-mail exists) with a generated password, in `group_path`."""
        if self.users_by_email(email):
            raise Refuse(f"Keycloak user {email} already exists; nothing was changed")
        password = "Dm-" + secrets.token_urlsafe(24)
        r = httpx.post(
            f"{self.realm}/users",
            headers=self.h(),
            json={
                "username": email,
                "email": email,
                "firstName": first,
                "lastName": last,
                "enabled": True,
                "emailVerified": True,
            },
            timeout=TIMEOUT,
        )
        self._ok(r, "create user", 201)
        uid = r.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        self.set_password(uid, password)
        gid = self._ok(
            httpx.get(f"{self.realm}/group-by-path/{group_path.strip('/')}", headers=self.h(), timeout=TIMEOUT),
            f"group {group_path}",
        ).json()["id"]
        self._ok(
            httpx.put(f"{self.realm}/users/{uid}/groups/{gid}", headers=self.h(), timeout=TIMEOUT), "join group", 204
        )
        return uid, password

    def set_password(self, uid: str, password: str) -> None:
        """Only ever called for demo users `seed` created (on creation, or `field --reset-demo-password`)."""
        self._ok(
            httpx.put(
                f"{self.realm}/users/{uid}",
                headers=self.h(),
                json={"requiredActions": [], "emailVerified": True},
                timeout=TIMEOUT,
            ),
            "update user",
            204,
        )
        self._ok(
            httpx.put(
                f"{self.realm}/users/{uid}/reset-password",
                headers=self.h(),
                json={"type": "password", "value": password, "temporary": False},
                timeout=TIMEOUT,
            ),
            "set password",
            204,
        )

    def clear_lockout(self, uid: str) -> None:
        """Lifts a brute-force lockout (temporary disable after failed sign-ins), if any."""
        self._ok(
            httpx.delete(f"{self.realm}/attack-detection/brute-force/users/{uid}", headers=self.h(), timeout=TIMEOUT),
            "clear lockout",
            204,
            404,
        )

    def get_user(self, uid: str) -> dict[str, Any] | None:
        r = httpx.get(f"{self.realm}/users/{uid}", headers=self.h(), timeout=TIMEOUT)
        return None if r.status_code == 404 else dict(self._ok(r, "get user").json())

    def update_user(self, uid: str, fields: dict[str, Any]) -> None:
        self._ok(httpx.put(f"{self.realm}/users/{uid}", headers=self.h(), json=fields, timeout=TIMEOUT), "update", 204)

    def delete_user(self, uid: str) -> None:
        self._ok(httpx.delete(f"{self.realm}/users/{uid}", headers=self.h(), timeout=TIMEOUT), "delete user", 204, 404)

    def create_client(self) -> "Client":
        web = self._ok(
            httpx.get(f"{self.realm}/clients", params={"clientId": "asseta-web"}, headers=self.h(), timeout=TIMEOUT),
            "read asseta-web",
        ).json()[0]
        client_id, secret = f"demo-seeder-{uuid.uuid4().hex[:8]}", secrets.token_urlsafe(32)
        self._ok(
            httpx.post(
                f"{self.realm}/clients",
                headers=self.h(),
                json={
                    "clientId": client_id,
                    "name": "Temporary demo seeder (scripts/seed-demo-tenant.sh)",
                    "secret": secret,
                    "publicClient": False,
                    "directAccessGrantsEnabled": True,
                    "standardFlowEnabled": False,
                    "protocolMappers": [{k: v for k, v in m.items() if k != "id"} for m in web["protocolMappers"]],
                },
                timeout=TIMEOUT,
            ),
            "create client",
            201,
        )
        found = self._ok(
            httpx.get(f"{self.realm}/clients", params={"clientId": client_id}, headers=self.h(), timeout=TIMEOUT),
            "find client",
        ).json()
        return Client(client_id, secret, str(found[0]["id"]))

    def delete_client(self, client_uuid: str) -> None:
        self._ok(
            httpx.delete(f"{self.realm}/clients/{client_uuid}", headers=self.h(), timeout=TIMEOUT),
            "delete client",
            204,
            404,
        )


class LoginFailed(RuntimeError):
    """Keycloak refused a password grant; the message carries Keycloak's error code and description, never secrets."""


@dataclass
class Client:
    client_id: str
    secret: str
    uuid: str


class Login:
    """Password grant for the throwaway platform user through the throwaway client (token cached until near expiry)."""

    def __init__(self, client: Client, email: str, password: str):
        self.client, self.email, self._password = client, email, password
        self._token, self._expires = "", 0.0

    def refresh(self) -> None:
        self._expires = 0.0

    def bearer(self) -> dict[str, str]:
        if time.monotonic() >= self._expires:
            r = httpx.post(
                f"{KC}/realms/asseta/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": self.client.client_id,
                    "client_secret": self.client.secret,
                    "username": self.email,
                    "password": self._password,
                    "scope": "openid",
                },
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                reason = ""
                with contextlib.suppress(ValueError, AttributeError):
                    err = r.json()
                    reason = f" ({err.get('error')}: {err.get('error_description')})"
                raise LoginFailed(f"login of {self.email} failed: HTTP {r.status_code}{reason}")
            body = r.json()
            self._token = str(body["access_token"])
            self._expires = time.monotonic() + max(10, int(body.get("expires_in", 300)) - 30)
        return {"Authorization": f"Bearer {self._token}"}


class Api:
    def __init__(self, login: Login, tenant_id: str | None = None, headers: dict[str, str] | None = None):
        self.login, self.tenant_id, self.headers = login, tenant_id, dict(headers or {})

    def _h(self) -> dict[str, str]:
        h = {**self.login.bearer(), "Idempotency-Key": str(uuid.uuid4()), **self.headers}
        if self.tenant_id:
            h["X-Tenant-ID"] = self.tenant_id
        return h

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = httpx.get(f"{API}{path}", headers=self._h(), params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            raise ApiError(f"GET {path}", r)
        return r.json()

    def post(self, path: str, body: Any, what: str, ok: tuple[int, ...] = (200, 201)) -> Any:
        r = httpx.post(f"{API}{path}", headers=self._h(), json=body, timeout=60.0)
        if r.status_code not in ok:
            raise ApiError(what, r)
        return r.json() if r.content else {}

    def put_bytes(self, path: str, data: bytes, what: str) -> Any:
        h = {**self._h(), "Content-Type": "application/octet-stream"}
        r = httpx.put(f"{API}{path}", headers=h, content=data, timeout=60.0)
        if r.status_code != 200:
            raise ApiError(what, r)
        return r.json()

    def rows(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Every row of a list endpoint (plain list or paged envelope)."""
        out: list[dict[str, Any]] = []
        page = 1
        while True:
            body = self.get(path, {**(params or {}), "page": page, "page_size": 200})
            if isinstance(body, list):
                return body
            out += body["items"]
            if len(out) >= body["total"] or not body["items"]:
                return out
            page += 1


# --- tenant lookup and the temporary mandate ----------------------------------------------------------------------
def find_tenant(p: Api, registration: str, name: str) -> dict[str, Any]:
    tenants = p.rows("/platform/tenants")
    matches = [t for t in tenants if registration and norm(t.get("registration_number")) == norm(registration)]
    if not matches and name:
        by_name = [t for t in tenants if norm(name) in (norm(t["display_name"]), norm(t["legal_name"]))]
        clash = [t for t in by_name if t.get("registration_number") and registration]
        if clash:
            raise Refuse(
                f"No tenant has registration number '{registration}', but '{name}' exists with registration "
                f"number '{clash[0]['registration_number']}'. Check which tenant is meant and pass it explicitly."
            )
        matches = by_name
    if not matches:
        raise Refuse(
            f"No tenant with registration number '{registration}' or name '{name}'.",
            "Create it in the platform console first (Platform -> Tenants -> Onboard).",
        )
    if len(matches) > 1:
        listing = ", ".join(f"{t['display_name']} ({t['id']})" for t in matches)
        raise Refuse(f"More than one tenant matches: {listing}")
    return matches[0]


def check_entitled(p: Api, t: dict[str, Any]) -> dict[str, Any]:
    sub = p.get(f"/platform/tenants/{t['id']}/subscription")
    problems = []
    if t["verification_status"] != "VERIFIED":
        problems.append(
            f"company verification is {t['verification_status']}: verify it in Platform -> Tenants -> "
            f"{t['display_name']} -> Verification"
        )
    if sub["status"] != "ACTIVE":
        problems.append(
            f"subscription is {sub['status']}: activate it (Platform -> Tenants -> {t['display_name']} -> "
            "Subscription -> transition to ACTIVE) once the agreement is signed"
        )
    if t["status"] != "ACTIVE":
        problems.append(f"tenant status is {t['status']} (becomes ACTIVE with an active subscription)")
    if t["access_state"] != "FULL":
        problems.append(f"access state is {t['access_state']} ({t.get('access_state_reason') or 'see billing'})")
    if problems:
        raise Refuse(f"Tenant '{t['display_name']}' is not ready for demo data:", *problems)
    return dict(sub)


@dataclass
class Platform:
    kc: KeycloakAdmin
    api: Api
    login: Login
    email: str


@contextlib.contextmanager
def platform_session(kc: KeycloakAdmin, domain: str) -> Iterator[Platform]:
    """Throwaway platform owner + confidential client, both deleted on the way out (even on failure)."""
    client = kc.create_client()
    uid: str | None = None
    try:
        email = f"demo-seeder-{uuid.uuid4().hex[:8]}@{domain}"
        uid, password = kc.create_user(email, "Asseta", "Demo Setup", "/platform/platform-owner")
        login = Login(client, email, password)
        api = Api(login)
        api.get("/me")  # registers the app user (the mandate staff list and the audit trail need it)
        yield Platform(kc, api, login, email)
    finally:
        failed = []
        if uid:
            try:
                kc.delete_user(uid)
            except Exception as e:
                failed.append(f"user {uid}: {e}")
        try:
            kc.delete_client(client.uuid)
        except Exception as e:
            failed.append(f"client {client.client_id}: {e}")
        if failed:
            log("WARNING: cleanup incomplete, delete these in the Keycloak admin console: " + "; ".join(failed))
        else:
            log("temporary platform user and Keycloak client deleted")


OPEN_MANDATE = ("IN_FORCE", "SCHEDULED", "EXPIRED")  # all still status ACTIVE in the database: one per client


@contextlib.contextmanager
def mandate(pf: Platform, tenant: dict[str, Any], consent: str, purpose: str) -> Iterator[Api]:
    open_ones = [m for m in pf.api.get("/platform/mandates") if m["tenant_id"] == tenant["id"]]
    open_ones = [m for m in open_ones if m["status"] in OPEN_MANDATE]
    if open_ones:
        m = open_ones[0]
        raise Refuse(
            f"'{tenant['display_name']}' already has an open managed-service mandate {m['reference']} "
            f"({m['status']}). Only one is allowed and this script never touches someone else's mandate:",
            "end it in Platform -> Managed service (or let the client revoke it), then run again.",
        )
    today = utcnow().date()
    m = pf.api.post(
        "/platform/mandates",
        {
            "tenant_id": tenant["id"],
            "scope": "FULL",
            "starts_on": today.isoformat(),
            "ends_on": (today + timedelta(days=1)).isoformat(),  # safety net; ended explicitly below
            "consent_reference": consent,
            "notes": f"Temporary mandate for {purpose} by scripts/seed-demo-tenant.sh (ended automatically).",
        },
        "grant mandate",
    )
    log(f"mandate {m['reference']} granted ({purpose})")
    try:
        me = pf.api.get("/me")["user_id"]
        pf.api.get("/platform/mandates/staff", {"q": pf.email})
        pf.api.post(
            f"/platform/mandates/{m['id']}/assignments", {"user_id": me, "role_key": "owner"}, "assign staff", (200,)
        )
        pf.login.refresh()  # the next token carries the tenant group
        acting = Api(pf.login, tenant["id"])
        acting.get("/tenant/machines", {"page_size": 1})
        yield acting
    finally:
        try:
            cur = pf.api.get(f"/platform/mandates/{m['id']}")
            if cur["status"] in OPEN_MANDATE:
                pf.api.post(
                    f"/platform/mandates/{m['id']}/end",
                    {"version": cur["version"], "reason": f"{purpose} finished"},
                    "end mandate",
                    (200,),
                )
            log(f"mandate {m['reference']} ended")
        except Exception as e:
            log(f"WARNING: could not end mandate {m['reference']} ({e}); end it in Platform -> Managed service")


# --- simulation ---------------------------------------------------------------------------------------------------
@dataclass
class Rules:
    """The tenant's own thresholds, read at seed time, so the simulated fleet never trips an alert rule."""

    timezone: str = "Africa/Dar_es_Salaam"
    moving_speed_kmh: float = 3.0
    window_start: str | None = None
    window_end: str | None = None
    weekdays: list[int] = field(default_factory=lambda: list(range(7)))
    max_run_minutes: float = 22.0

    def moving_allowed(self, t: datetime) -> bool:
        """Mirror of TrackingPolicy.within_operating_window (movement outside it is UNAUTHORIZED_MOVEMENT)."""
        if not self.window_start or not self.window_end:
            return True
        local = t.astimezone(ZoneInfo(self.timezone))
        if local.weekday() not in self.weekdays:
            return False
        now, start, end = local.time(), dtime.fromisoformat(self.window_start), dtime.fromisoformat(self.window_end)
        return start <= now < end if start <= end else (now >= start or now < end)


@dataclass
class Unit:
    """One simulated tracker and the machine state it reports."""

    code: str
    device: str
    mode: str  # work | idle
    home: tuple[float, float]
    lat: float
    lon: float
    hours_ms: int
    ignition: bool = False
    phase: str = "PARKED"  # PARKED | WORK | BREAK
    phase_until: str = ""
    target: tuple[float, float] | None = None
    dig_until: str = ""
    course: float = 0.0
    transport: str = ""  # osmand | gateway
    traccar_id: int | None = None


def _rng(u: Unit, t: datetime) -> random.Random:
    return random.Random(f"{u.device}:{int(t.timestamp())}")  # noqa: S311 - deterministic simulation, not crypto


def _dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    dy = (b[0] - a[0]) * EARTH_M_PER_DEG
    dx = (b[1] - a[1]) * EARTH_M_PER_DEG * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def _bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    dy = b[0] - a[0]
    dx = (b[1] - a[1]) * math.cos(math.radians(a[0]))
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


WORK_RADIUS_DEG = 0.0008  # ~90 m around the machine's spot; the site geofence is +-0.004 deg (~440 m)


def step(u: Unit, prev: datetime, now: datetime, rules: Rules) -> Fix:
    """Advance one unit from `prev` to `now` and return the fix it reports at `now`."""
    dt = max(1.0, (now - prev).total_seconds())
    was_on = u.ignition
    rng = _rng(u, now)
    speed = 0.0
    if u.mode == "work":
        until = datetime.fromisoformat(u.phase_until) if u.phase_until else now
        if u.phase == "WORK" and now >= until:  # end of a work run: engine off for a short break
            u.phase, u.target, u.dig_until = "BREAK", None, ""
            u.phase_until = (now + timedelta(minutes=rng.uniform(4, 9))).isoformat()
        elif u.phase in ("BREAK", "PARKED") and now >= until:
            u.phase = "WORK"
            u.phase_until = (now + timedelta(minutes=rng.uniform(0.55, 1.0) * rules.max_run_minutes)).isoformat()
        u.ignition = u.phase == "WORK"
        if u.ignition:
            dig_done = not u.dig_until or now >= datetime.fromisoformat(u.dig_until)
            if u.target is None and dig_done:
                ang, r = rng.uniform(0, 2 * math.pi), rng.uniform(0.3, 1.0) * WORK_RADIUS_DEG
                u.target = (u.home[0] + r * math.sin(ang), u.home[1] + r * math.cos(ang))
                u.dig_until = ""
            if u.target is not None:
                fast = max(4.0, rules.moving_speed_kmh * 1.4)
                v = rng.uniform(fast, fast + 2.0) if rules.moving_allowed(now) else rules.moving_speed_kmh * 0.5
                remaining, travel = _dist_m((u.lat, u.lon), u.target), v / 3.6 * dt
                u.course = _bearing((u.lat, u.lon), u.target)
                if travel >= remaining:
                    u.lat, u.lon = u.target
                    speed = remaining / dt * 3.6
                    u.target, u.dig_until = None, (now + timedelta(minutes=rng.uniform(3, 8))).isoformat()
                else:
                    f = travel / remaining
                    u.lat, u.lon = u.lat + (u.target[0] - u.lat) * f, u.lon + (u.target[1] - u.lon) * f
                    speed = v
            else:  # digging / loading in place: engine on, the machine swings but hardly travels
                speed = round(rng.uniform(0.0, 0.4), 1)
    if was_on:
        u.hours_ms += int(dt * 1000)  # engine hours advance only while the engine ran
    jitter = 0.000004 if u.ignition else 0.0  # parked machines report exactly where they stand
    return Fix(
        now,
        round(u.lat + rng.uniform(-jitter, jitter), 7),
        round(u.lon + rng.uniform(-jitter, jitter), 7),
        round(speed, 1),
        round(u.course, 1),
        ignition=u.ignition,
        accuracy_m=round(rng.uniform(3.0, 7.5), 1),
        hours_ms=u.hours_ms,
    )


def park(u: Unit, prev: datetime, now: datetime) -> Fix:
    """Engine off, stationary (end of the history / of a feed)."""
    if u.ignition:
        u.hours_ms += int(max(1.0, (now - prev).total_seconds()) * 1000)
    u.ignition, u.phase, u.target, u.dig_until = False, "PARKED", None, ""
    u.phase_until = now.isoformat()
    return Fix(
        now,
        round(u.lat, 7),
        round(u.lon, 7),
        0.0,
        round(u.course, 1),
        ignition=False,
        accuracy_m=4.0,
        hours_ms=u.hours_ms,
    )


class Sender:
    """Delivers fixes as a real device would (OsmAnd to Traccar), or straight to the gateway endpoint."""

    def __init__(self, gateway_key: str = "", traccar_login: tuple[str, str] | None = None):
        self.gateway_key, self.traccar_login = gateway_key, traccar_login
        self.http = httpx.Client(timeout=15.0)

    def osmand(self, device: str, fix: Fix) -> bool:
        params: dict[str, str | float | int] = {
            "id": device,
            "lat": fix.lat,
            "lon": fix.lon,
            "timestamp": int(fix.time.timestamp()),
            "speed": round(fix.speed_kmh * KMH_TO_KNOTS, 4),
            "bearing": fix.course,
            "accuracy": fix.accuracy_m or 0,
            "valid": "true",
            "ignition": str(bool(fix.ignition)).lower(),
            "sat": 9,
        }
        if fix.hours_ms is not None:
            params["hours"] = fix.hours_ms
        try:
            return self.http.get(OSMAND, params=params).status_code == 200
        except httpx.HTTPError:
            return False

    def gateway(self, device: str, fix: Fix) -> bool:
        r = self.http.post(
            f"{API}/telemetry/traccar",
            json=traccar_payload(device, fix),
            headers={"X-Asseta-Gateway-Key": self.gateway_key},
        )
        if r.status_code != 202:
            raise ApiError(f"gateway ingest for {device}", r)
        body = r.json()
        if body.get("quarantined"):
            raise RuntimeError(f"gateway quarantined a fix for {device}: {body.get('reasons')}")
        return True

    def register_in_traccar(self, u: Unit, label: str) -> None:
        assert self.traccar_login is not None
        r = self.http.post(
            f"{TRACCAR_API}/api/devices",
            json={"name": label, "uniqueId": u.device, "category": "truck"},
            auth=self.traccar_login,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Traccar refused to register {u.device}: HTTP {r.status_code}")
        u.traccar_id = int(r.json()["id"])

    def choose(self, u: Unit, first: Fix, label: str, wanted: str) -> None:
        """Send the first fix and settle the unit's transport (auto: Traccar if it accepts the device)."""
        if wanted in ("auto", "osmand"):
            if self.osmand(u.device, first):
                u.transport = "osmand"
                return
            if self.traccar_login:
                self.register_in_traccar(u, label)
                if self.osmand(u.device, first):
                    u.transport = "osmand"
                    return
            if wanted == "osmand" or not self.gateway_key:
                raise Refuse(
                    f"Traccar ({OSMAND}) refused the simulated device {u.device}: production registers devices",
                    "explicitly (DEC-017). Either set TRACCAR_ADMIN_EMAIL/TRACCAR_ADMIN_PASSWORD so the script",
                    "registers the demo devices in Traccar, or use --transport gateway (needs",
                    "ASSETA_TRACCAR_GATEWAY_KEY, which the wrapper passes from .env.production).",
                )
        u.transport = "gateway"
        self.gateway(u.device, first)

    def send(self, u: Unit, fix: Fix) -> None:
        if not u.transport:  # a seed that failed before this unit's history: settle it now
            self.choose(u, fix, f"{u.code} (demo)", "auto")
            return
        ok = self.osmand(u.device, fix) if u.transport == "osmand" else self.gateway(u.device, fix)
        if not ok:
            raise RuntimeError(f"Traccar did not accept a fix for {u.code}")


# --- state files ----------------------------------------------------------------------------------------------------
def write_private(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Refuse(f"No state file {path}: run `seed` first (or pass the --slug used for it)")
    return dict(json.loads(path.read_text()))


def units_of(state: dict[str, Any]) -> list[Unit]:
    out = []
    for raw in state["units"]:
        home, target = raw["home"], raw.get("target")
        u = Unit(**{**raw, "home": (float(home[0]), float(home[1])), "target": None})
        u.target = (float(target[0]), float(target[1])) if target else None
        out.append(u)
    return out


def rules_of(state: dict[str, Any]) -> Rules:
    return Rules(**state["rules"])


# --- seed -----------------------------------------------------------------------------------------------------------
def ensure(t: Api, list_path: str, key: str, value: str, create_path: str, body: dict[str, Any]) -> tuple[str, bool]:
    """Reuse a row with the same `key` (codes/names the owner may already have set up), else create it."""
    for row in t.rows(list_path, {"include_inactive": "true"}):
        if norm(str(row.get(key))) == norm(value):
            return str(row["id"]), False
    return str(t.post(create_path, body, f"create {create_path} {value}")["id"]), True


def square(lat: float, lon: float, half: float) -> dict[str, Any]:
    ring = [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half], [lon - half, lat + half]]
    return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


def tracker_model(p: Api) -> str:
    needed = {"GNSS", "ACCURACY", "IGNITION", "ENGINE_HOURS"}
    for m in p.get("/platform/tracker-models", {"q": "Simulated"}):
        caps = set(m.get("declared_capabilities") or [])
        simulated = m["manufacturer"] == "Simulated" and m["protocol"] == "osmand" and m["adapter"] == "TRACCAR"
        if simulated and needed <= caps and m.get("approved", True):
            log(f"reusing tracker model {m['manufacturer']} {m['model']}")
            return str(m["id"])
    created = p.post(
        "/platform/tracker-models",
        {
            "manufacturer": "Simulated",
            "model": "OsmAnd demo simulator",
            "adapter": "TRACCAR",
            "protocol": "osmand",
            "declared_capabilities": sorted(needed),
            "notes": "Simulated demo devices only (scripts/seed-demo-tenant.sh); not real hardware.",
        },
        "create tracker model",
    )
    log("created tracker model 'Simulated OsmAnd demo simulator'")
    return str(created["id"])


def read_rules(t: Api) -> Rules:
    tz = str(t.get("/tenant/overview").get("timezone") or "Africa/Dar_es_Salaam")
    tracking = t.get("/tenant/policies/TRACKING/effective")["values"]
    fraud = t.get("/tenant/policies/FRAUD_CONTROLS/effective")["values"]
    threshold = float(fraud.get("engine_activity_min_minutes") or 30)
    return Rules(
        timezone=tz,
        moving_speed_kmh=float(tracking["moving_speed_kmh"]),
        window_start=tracking.get("operating_window_start"),
        window_end=tracking.get("operating_window_end"),
        weekdays=list(tracking.get("operating_weekdays") or range(7)),
        max_run_minutes=max(3.0, min(22.0, threshold - 6)),  # runs stay under the unreported-engine threshold
    )


def preflight_users(kc: KeycloakAdmin, emails: dict[str, str]) -> None:
    taken = [e for e in emails.values() if kc.users_by_email(e)]
    if taken:
        raise Refuse(
            f"Demo user(s) already exist in Keycloak: {', '.join(taken)}. This script never touches existing",
            "accounts. Use another --demo-domain or --slug, or remove those accounts yourself.",
        )


def seed(a: argparse.Namespace) -> int:
    creds_path, state_path = Path(a.out_dir) / f"demo-{a.slug}-credentials.json", state_file(a)
    for path in (creds_path, state_path):
        if path.exists():
            raise Refuse(f"{path} already exists (an earlier seed?). Move it away first; it is never overwritten.")
    region = REGIONS[a.region]
    emails = {role: f"{role}.{a.slug}@{a.demo_domain}" for role in USERS}
    kc = KeycloakAdmin()
    preflight_users(kc, emails)
    gateway_key = env("ASSETA_TRACCAR_GATEWAY_KEY")
    tl = (env("TRACCAR_ADMIN_EMAIL"), env("TRACCAR_ADMIN_PASSWORD"))
    sender = Sender(gateway_key, tl if all(tl) else None)
    with platform_session(kc, a.demo_domain) as pf:
        tenant = find_tenant(pf.api, a.registration_number, a.tenant_name)
        sub = check_entitled(pf.api, tenant)
        log(f"tenant {tenant['display_name']} ({tenant['id']}): verified, subscription ACTIVE, access FULL")
        if sub.get("enrolled_assets"):
            raise Refuse(f"{tenant['display_name']} already has {sub['enrolled_assets']} enrolled machine(s)")
        model = tracker_model(pf.api)
        with mandate(pf, tenant, a.consent_reference, "demo data setup") as t:
            existing = t.get("/tenant/machines", {"page_size": 1, "include_inactive": "true"})["total"]
            if existing:
                raise Refuse(
                    f"{tenant['display_name']} already has {existing} machine(s); demo data is only added to "
                    "a tenant without machines"
                )
            state: dict[str, Any] = {
                "version": 1,
                "tenant_id": tenant["id"],
                "tenant": tenant["display_name"],
                "registration_number": tenant.get("registration_number"),
                "region": a.region,
                "incomplete": True,
                **{k: {} for k in ("created", "machines", "trackers", "staff", "users")},
                **{k: [] for k in ("enrollments", "units")},
            }
            try:
                build_tenant(t, tenant, sub, region, model, emails, kc, a, state)
                state.pop("incomplete")
            finally:  # the passwords go to the credentials file only, never to the state file
                creds = {
                    "web": WEB,
                    "tenant": tenant["display_name"],
                    "tenant_id": tenant["id"],
                    "note": "Demo accounts only. The tenant owner keeps their own account (not stored here).",
                    "accounts": {r: u.pop("login") for r, u in state["users"].items() if "login" in u},
                }
                if creds["accounts"]:
                    write_private(creds_path, creds)
                write_private(state_path, state)  # also on failure: `retire --yes` can then undo what exists
            send_history(state, sender, a)
            write_private(state_path, state)
            verify_live(t, state)
    log(f"DEMO SEED OK tenant='{tenant['display_name']}' machines={len(MACHINES)} credentials={creds_path}")
    log(f"next: scripts/seed-demo-tenant.sh feed --minutes 90   (state: {state_path})")
    return 0


def build_tenant(
    t: Api,
    tenant: dict[str, Any],
    sub: dict[str, Any],
    region: dict[str, Any],
    model: str,
    emails: dict[str, str],
    kc: KeycloakAdmin,
    a: argparse.Namespace,
    st: dict[str, Any],
) -> None:
    """Fills `st` as it goes, so a failure half-way still records what exists (for `retire`) and any password."""
    now = utcnow()
    today = now.date().isoformat()
    created: dict[str, list[str]] = st["created"]

    def mark(kind: str, rid: str, new: bool) -> str:
        if new:
            created.setdefault(kind, []).append(rid)
        return rid

    rules = read_rules(t)
    log(
        f"tenant rules: timezone {rules.timezone}, moving >= {rules.moving_speed_kmh} km/h, window "
        f"{rules.window_start or 'none'}-{rules.window_end or ''}, work runs <= {rules.max_run_minutes:.0f} min"
    )
    cats = {
        n: mark(
            "categories", *ensure(t, "/tenant/machine-categories", "name", n, "/tenant/machine-categories", {"name": n})
        )
        for n in dict.fromkeys(m[2] for m in MACHINES)
    }
    area_code, area_name = region["area"]
    area = mark(
        "areas",
        *ensure(
            t,
            "/tenant/operating-areas",
            "code",
            area_code,
            "/tenant/operating-areas",
            {"code": area_code, "name": area_name},
        ),
    )
    sites: list[dict[str, Any]] = []
    for code, name, (lat, lon) in region["sites"]:
        sid = mark(
            "sites",
            *ensure(
                t,
                "/tenant/job-sites",
                "code",
                code,
                "/tenant/job-sites",
                {
                    "code": code,
                    "name": name,
                    "address": f"{name}, {area_name}",
                    "center": {"type": "Point", "coordinates": [lon, lat]},
                },
            ),
        )
        sites.append({"id": sid, "code": code, "name": name, "center": (lat, lon), "machines": []})

    # Machines + billing enrollment (needed before a tracker can be assigned and telemetry is accepted).
    rate = sub.get("current_rate") or {}
    machines: dict[str, str] = st["machines"]
    enrollments: list[str] = st["enrollments"]
    charges: list[str] = []
    for code, name, cat, make, mdl, year, site, _mode, _hours in MACHINES:
        mid = t.post(
            "/tenant/machines",
            {
                "asset_code": code,
                "name": name,
                "category_id": cats[cat],
                "operating_area_id": area,
                "manufacturer": make,
                "model": mdl,
                "year_of_manufacture": year,
                "meter_decimal_places": 1,
            },
            f"machine {code}",
        )["id"]
        machines[code] = mark("machines", str(mid), True)
        res = t.post("/tenant/billing/enrollments", {"machine_id": mid, "effective_from": today}, f"enroll {code}")
        enrollments.append(str(res["enrollment"]["id"]))
        if res.get("charge"):
            c = res["charge"]
            charges.append(f"{code}: {c['amount']} {c['currency']} ({c['explanation']})")
        if site is not None:
            sites[site]["machines"].append(str(mid))
    log(
        f"BILLING: {len(enrollments)} machines enrolled from {today} on subscription {sub.get('agreement_number')} "
        f"(rate {rate.get('unit_price', '?')} {rate.get('currency', '')} per asset {rate.get('cadence', '')}, "
        f"minimum {rate.get('minimum_billable_assets', '?')} billable assets)."
    )
    for line in charges:
        log(f"BILLING: pro-rata charge {line}")

    for s in sites:  # each site's allowed area binds only the machines working there
        lat, lon = s["center"]
        gid = t.post(
            "/tenant/geofences",
            {
                "name": f"{s['name']} boundary",
                "kind": "ALLOWED_AREA",
                "job_site_id": s["id"],
                "polygon": square(lat, lon, 0.004),
                "machine_ids": s["machines"],
            },
            f"geofence {s['code']}",
        )["id"]
        mark("geofences", str(gid), True)

    # Simulated trackers, assigned from the start of the GPS history.
    history_start = history_window(now, a.history_hours)
    units: list[dict[str, Any]] = st["units"]
    trackers: dict[str, str] = st["trackers"]
    for i, (code, _name, _cat, _make, _mdl, _year, site, mode, hours) in enumerate(MACHINES):
        if site is None:
            continue  # deliberately untracked: the map must show it without a position
        device = "86" + str(uuid.uuid4().int)[:13]  # IMEI-shaped (15 digits), unique
        tid = t.post(
            "/tenant/trackers",
            {"tracker_model_id": model, "external_id": device, "label": f"{code} tracker (simulated)"},
            f"tracker {code}",
        )["id"]
        trackers[code] = mark("trackers", str(tid), True)
        t.post(
            f"/tenant/trackers/{tid}/assign",
            {"machine_id": machines[code], "effective_from": (history_start - timedelta(minutes=2)).isoformat()},
            f"assign tracker {code}",
        )
        clat, clon = sites[site]["center"]
        dlat, dlon = HOME_OFFSETS[i % len(HOME_OFFSETS)]
        home = (round(clat + dlat, 6), round(clon + dlon, 6))
        u = Unit(code, device, mode, home, home[0], home[1], int(hours * 3_600_000))
        units.append(asdict(u))

    # People: a supervisor (field app) and an accountant, both NEW accounts on the demo domain; operators as staff.
    users: dict[str, dict[str, Any]] = st["users"]
    for role, (first, last) in USERS.items():
        res = t.post(
            "/tenant/access/members",
            {"email": emails[role], "first_name": first, "last_name": last, "role_key": role},
            f"invite {role}",
        )
        users[role] = {"user_id": res["user_id"], "email": emails[role], "subject": ""}
        if not res.get("created_account"):  # appeared since the preflight: never touch that account
            users[role]["preexisting"] = True
            raise RuntimeError(f"{emails[role]} was not created by this run; refusing to set its password")
        hits = kc.users_by_email(emails[role])
        if len(hits) != 1:
            raise RuntimeError(f"expected one Keycloak user for {emails[role]}, found {len(hits)}")
        users[role]["subject"] = subject = str(hits[0]["id"])
        password = "Dm-" + secrets.token_urlsafe(18)
        kc.set_password(subject, password)
        users[role]["login"] = {"email": emails[role], "password": password}
    sup = t.post(
        "/tenant/staff",
        {
            "full_name": " ".join(USERS["supervisor"]),
            "kind": "SUPERVISOR",
            "keycloak_subject": users["supervisor"]["subject"],
            "employee_code": "WS-SUP-01",
        },
        "supervisor staff",
    )["id"]
    st["staff"]["supervisor"] = mark("staff", str(sup), True)
    assign_from = (history_start - timedelta(minutes=1)).isoformat()
    tracked = [m for m in MACHINES if m[6] is not None]
    for n, m in enumerate(tracked):
        op = t.post(
            "/tenant/staff",
            {"full_name": OPERATORS[n % len(OPERATORS)], "kind": "OPERATOR", "employee_code": f"WS-OP-{n + 1:02d}"},
            f"operator for {m[0]}",
        )["id"]
        mark("staff", str(op), True)
        t.post(
            f"/tenant/machines/{machines[m[0]]}/assignments",
            {"staff_member_id": op, "role": "OPERATOR", "effective_from": assign_from},
            f"assign operator {m[0]}",
        )
        if m[7] == "work":
            t.post(
                f"/tenant/machines/{machines[m[0]]}/assignments",
                {"staff_member_id": sup, "role": "SUPERVISOR", "effective_from": assign_from},
                f"assign supervisor {m[0]}",
            )

    # Commercial side: customers, contracts per site, jobs (approved for the working machines, one pending, one draft).
    for code, name in EXPENSE_CATEGORIES:
        mark(
            "expense_categories",
            *ensure(
                t,
                "/tenant/expense-categories",
                "code",
                code,
                "/tenant/expense-categories",
                {"code": code, "name": name},
            ),
        )
    customers = {
        code: mark(
            "customers",
            *ensure(
                t,
                "/tenant/customers",
                "code",
                code,
                "/tenant/customers",
                {"code": code, "name": name, "payment_terms_days": 30},
            ),
        )
        for code, name in CUSTOMERS
    }
    site_of = {m[0]: m[6] for m in MACHINES}
    contracts: dict[str, str] = {}
    for n, (code, _name) in enumerate(CUSTOMERS):
        number = f"CT-{now.year}-{code}"
        cid, new = ensure(
            t,
            "/tenant/contracts",
            "contract_number",
            number,
            "/tenant/contracts",
            {
                "customer_id": customers[code],
                "contract_number": number,
                "job_site_id": sites[n % len(sites)]["id"],
                "starts_on": now.isoformat(),
                "reference": f"Demo contract {number}",
            },
        )
        contracts[code] = mark("contracts", cid, new)
    jobs: list[str] = []
    for number, cust, mcode, hourly, final in JOBS:
        site = site_of[mcode]
        body: dict[str, Any] = {
            "contract_id": contracts[cust],
            "job_number": number,
            "machine_id": machines[mcode],
            "planned_start": now.isoformat(),
            "planned_end": (now + timedelta(days=30)).isoformat(),
            "hourly_rate": hourly,
            "minimum_hours": "4",
        }
        if site is not None:
            body["job_site_id"] = sites[site]["id"]
        if final == "APPROVED":
            body["supervisor_id"] = sup
        job = t.post("/tenant/jobs", body, f"job {number}")["id"]
        jobs.append(mark("jobs", str(job), True))
        actions = {"APPROVED": ("SUBMIT", "APPROVE"), "PENDING_APPROVAL": ("SUBMIT",), "DRAFT": ()}[final]
        for action in actions:
            t.post(f"/tenant/jobs/{job}/transitions", {"action": action}, f"{number} {action}", (200,))
    log(
        f"created: {len(MACHINES)} machines, {len(units)} simulated trackers, {len(sites)} sites + geofences, "
        f"{len(CUSTOMERS)} customers, {len(contracts)} contracts, {len(jobs)} jobs, 2 demo users, "
        f"{len(tracked) + 1} staff"
    )
    st.update(
        seeded_at=now.isoformat(),
        history_start=history_start.isoformat(),
        rules=asdict(rules),
        last_time=history_start.isoformat(),
    )


def history_window(now: datetime, hours: float) -> datetime:
    """Start of the GPS history: `hours` back, but never before today's UTC midnight (enrollments start today)."""
    midnight = datetime.combine(now.date(), dtime(0, 5), UTC)
    start = max(now - timedelta(hours=hours), midnight)
    if start > now - timedelta(minutes=30):
        log("NOTE: shortly after midnight UTC the history is short (enrollments only start today)")
    return start.replace(second=0)


def send_history(state: dict[str, Any], sender: Sender, a: argparse.Namespace) -> None:
    """A few hours of history, sent round-robin across the devices with at least `history_pace` seconds between two
    fixes of one device: Traccar forwards concurrently, and a burst would reach the API out of order."""
    rules, units = rules_of(state), units_of(state)
    start, end = datetime.fromisoformat(state["history_start"]), utcnow() - timedelta(seconds=5)
    interval = timedelta(seconds=a.history_interval)
    tracks: list[list[Fix]] = []
    for u in units:
        prev, cur = start, start
        fixes: list[Fix] = [park(u, start, start)]
        u.phase_until = (start + timedelta(minutes=_rng(u, start).uniform(5, 30))).isoformat()  # staggered
        while cur + interval < end:
            cur += interval
            fixes.append(step(u, prev, cur, rules))
            prev = cur
        fixes.append(park(u, prev, end))  # history ends parked: no engine left "running" without a feed
        tracks.append(fixes)
    try:
        for u, fixes in zip(units, tracks, strict=True):
            sender.choose(u, fixes[0], f"{state['tenant']} {u.code} (demo)", a.transport)
        time.sleep(a.history_pace)
        rounds = max(len(f) for f in tracks)
        log(f"sending {sum(map(len, tracks))} history fixes ({rounds} rounds, about {rounds * a.history_pace:.0f} s)")
        for i in range(1, rounds):
            began = time.monotonic()
            for u, fixes in zip(units, tracks, strict=True):
                if i < len(fixes):
                    sender.send(u, fixes[i])
            if any(u.transport == "osmand" for u in units):
                time.sleep(max(0.0, a.history_pace - (time.monotonic() - began)))
    finally:  # every generated fix is <= `end`: the feed continues strictly after it, even after a failure
        state["units"] = [asdict(u) for u in units]
        state["last_time"] = end.isoformat()
    for u, fixes in zip(units, tracks, strict=True):
        log(f"history {u.code}: {len(fixes)} fixes via {u.transport} ({u.mode})")
    log(f"GPS history sent from {start:%H:%M} to {end:%H:%M} UTC")


def verify_live(t: Api, state: dict[str, Any]) -> None:
    """Wait until every simulated tracker's last fix is on the fleet map; report open tracking alerts."""
    want = set(state["trackers"])
    deadline = time.monotonic() + 120
    rows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        rows = t.get("/tenant/fleet/map")
        seen = {r["asset_code"] for r in rows if r["position_time"] and r["asset_code"] in want}
        if seen == want and all(
            datetime.fromisoformat(r["position_time"]) >= datetime.fromisoformat(state["last_time"])
            for r in rows
            if r["asset_code"] in want
        ):
            break
        time.sleep(3)
    for r in rows:
        log(
            f"map {r['asset_code']:6} {r['connectivity']:15} engine={r['observed_engine']:8} "
            f"compliance={r['location_compliance']}"
        )
    alerts = t.rows("/tenant/alerts", {"status": "OPEN"})
    log(f"open tracking alerts: {len(alerts)} {dict(Counter(x['alert_type'] for x in alerts))}")


# --- feed -----------------------------------------------------------------------------------------------------------
STOP = {"now": False}


def _stop(_sig: int, _frame: object) -> None:
    STOP["now"] = True


def feed(a: argparse.Namespace) -> int:
    path = state_file(a)
    state = load_state(path)
    if state.get("retired_at"):
        raise Refuse("the demo data was retired; nothing to feed")
    if state.get("incomplete"):
        raise Refuse("the seed did not finish (see its output); `retire --yes` undoes what it created")
    lock = open(path.with_suffix(".lock"), "w")  # noqa: SIM115 - held for the whole run
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise Refuse("another feed is already running for this tenant (one writer only)") from None
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    rules, units = rules_of(state), units_of(state)
    tl = (env("TRACCAR_ADMIN_EMAIL"), env("TRACCAR_ADMIN_PASSWORD"))
    sender = Sender(env("ASSETA_TRACCAR_GATEWAY_KEY"), tl if all(tl) else None)
    if any(u.transport != "osmand" for u in units) and not sender.gateway_key:
        raise Refuse("the seed used gateway delivery; ASSETA_TRACCAR_GATEWAY_KEY is needed (the wrapper passes it)")
    prev = datetime.fromisoformat(state["last_time"])
    if prev > utcnow():
        raise Refuse(f"the last sent fix ({prev.isoformat()}) is in the future; check the server clock")
    interval = float(a.interval)
    open_runs = [u for u in units if u.ignition]
    if open_runs:  # a feed killed hard left engines on: end those runs right after the last fix
        when = prev + timedelta(seconds=min(interval, max(1.0, (utcnow() - prev).total_seconds() / 2)))
        for u in open_runs:
            sender.send(u, park(u, prev, when))
            log(f"{u.code}: closed an engine run left open by an interrupted feed")
        prev = when
    start = utcnow()
    for u in units:  # working machines start their engines one by one over the first minutes
        if u.mode == "work":
            u.phase = "PARKED"
            u.phase_until = (start + timedelta(seconds=_rng(u, start).uniform(20, 180))).isoformat()
    end = start + timedelta(minutes=a.minutes)
    log(f"feeding {len(units)} trackers every {interval:.0f} s until {end:%H:%M} UTC (Ctrl-C stops cleanly)")
    ticks = failures = 0
    try:
        while not STOP["now"] and utcnow() < end:
            now = utcnow()
            if now <= prev:  # strictly forward in time, whatever the clock does
                time.sleep(0.5)
                continue
            fixes = [(u, step(u, prev, now, rules)) for u in units]
            errors = 0
            for u, fix in fixes:
                try:
                    sender.send(u, fix)
                except (httpx.HTTPError, RuntimeError) as e:  # one lost fix is harmless: time still moves forward
                    errors += 1
                    log(f"WARNING {u.code}: {e}")
            failures = failures + 1 if errors == len(units) else 0
            if failures >= 10:
                raise RuntimeError("10 ticks in a row failed for every tracker; is Traccar/the API up?")
            prev, ticks = now, ticks + 1
            state["units"], state["last_time"] = [asdict(u) for u in units], now.isoformat()
            write_private(path, state)
            if ticks % 10 == 1:
                log(f"{now:%H:%M:%S} tick {ticks}: engines on {sum(u.ignition for u in units)}/{len(units)}")
            deadline = time.monotonic() + interval
            while not STOP["now"] and time.monotonic() < deadline:
                time.sleep(0.5)
    finally:
        final = max(utcnow(), prev + timedelta(seconds=1))
        for u in units:
            if u.ignition:  # never leave an engine "running" once nobody feeds the machine
                try:
                    sender.send(u, park(u, prev, final))
                except (httpx.HTTPError, RuntimeError) as e:
                    log(f"WARNING {u.code}: could not park ({e}); the next feed closes the run")
                    u.ignition = True
                state["last_time"] = final.isoformat()
        state["units"] = [asdict(u) for u in units]
        state.setdefault("feeds", []).append({"started": start.isoformat(), "ended": utcnow().isoformat()})
        write_private(path, state)
        log(f"feed stopped after {ticks} ticks; machines parked with the engine off")
    return 0


# --- field ----------------------------------------------------------------------------------------------------------
# A recent field history played as the demo supervisor through the offline sync protocol the phones use
# (POST /sync/push), so every server rule applies: meter validation, phone-GPS vs tracker comparison, exceptions,
# the expense policy, cash custody and the audit trail. Times are only ever in the past and never before the jobs
# were approved (earlier work would rightly be flagged as work without authorization).
FIELD_STARTS = ("J-2026-103", "J-2026-101", "J-2026-102")  # started in this order on role days 0, 1, 2
FIELD_COMPLETED = "J-2026-103"  # completed on role day 3 (closing reading, customer acknowledgement)
FIELD_READY = "J-2026-104"  # left APPROVED: ready to start live during the demo
FIELD_DAY = (dtime(7, 30), dtime(17, 30))  # local working hours (narrowed by the tenant's operating window)
FIELD_MIN_DAY = timedelta(hours=3)  # shorter working periods (approval late in the day, now early) are skipped
FIELD_PAST_DAYS = 4
FIELD_BATCH = 25
ENGINE_ON = ("WORK", "STANDBY")  # the hour meter runs while working and while idling on standby
TENTH = Decimal("0.1")
STANDBY_NOTES = {
    "J-2026-101": "Waiting for the tipper trucks to return from the tip",
    "J-2026-102": "Waiting for the site engineer to set out the next section",
    "J-2026-103": "Stockpile empty; waiting for the crusher",
}
DOWNTIME_NOTES = {
    "J-2026-101": "Hydraulic hose leak on the boom cylinder; hose replaced on site",
    "J-2026-102": "Fuel filter blocked; filter changed by the operator",
    "J-2026-103": "Front left tyre puncture; repaired on site",
}
FUEL_ISSUE_LITRES = {"J-2026-101": Decimal(180), "J-2026-102": Decimal(160), "J-2026-103": Decimal(140)}
FUEL_UNIT_PRICE = Decimal(3200)
FUEL_PURCHASE = (Decimal(600), Decimal(3150), "Kibamba Filling Station")
# category code, job, during ("DOWNTIME" | "STANDBY"), description, supplier, amount in the tenant currency
FIELD_EXPENSES: list[tuple[str, str, str, str, str | None, Decimal]] = [
    (
        "SPARES",
        "J-2026-101",
        "DOWNTIME",
        "Hydraulic hose and fittings for the boom cylinder",
        "Tabata Hydraulics",
        Decimal(185000),
    ),
    ("TYRES", "J-2026-103", "DOWNTIME", "Puncture repair, front left tyre", "Kigamboni Tyre Centre", Decimal(45000)),
    ("FUEL", "J-2026-102", "STANDBY", "Engine oil 20 L and grease", "Tabata Lubricants", Decimal(95000)),
    ("ALLOWANCE", "J-2026-101", "STANDBY", "Lunch allowance for the operator and banksman", None, Decimal(30000)),
]
FIELD_FLOAT = Decimal(500000)
FIELD_COLLECTION = Decimal(1500000)
FIELD_HANDOVER = Decimal(1200000)
FIELD_SIGNER = "Grace Mushi"  # fictional site engineer of the customer
OCR_ENGINE = "demo-script (generated image, not a camera photo)"


@dataclass
class Segment:
    kind: str  # WORK | STANDBY | DOWNTIME
    start: datetime
    end: datetime
    note: str | None = None


@dataclass
class JobRun:
    number: str
    opening_at: datetime
    opening: Decimal
    segments: list[Segment] = field(default_factory=list)
    closing_at: datetime | None = None

    def meter_at(self, t: datetime) -> Decimal:
        """Hour meter at `t`: the opening reading plus engine time (work and standby) logged before `t`."""
        secs = sum(max(0.0, (min(s.end, t) - s.start).total_seconds()) for s in self.segments if s.kind in ENGINE_ON)
        return (self.opening + Decimal(str(secs)) / Decimal(3600)).quantize(TENTH, rounding=ROUND_DOWN)


@dataclass
class FieldEvent:
    at: datetime
    kind: str  # FLOAT FUEL_PURCHASE OPENING START FUEL_ISSUE ACTIVITY EXPENSE CLOSING ACK COMPLETE COLLECTION HANDOVER
    job: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


def _minute_up(t: datetime) -> datetime:
    return t if t.second == 0 and t.microsecond == 0 else t.replace(second=0, microsecond=0) + timedelta(minutes=1)


def _minute_down(t: datetime) -> datetime:
    return t.replace(second=0, microsecond=0)


def field_window(rules: Rules) -> tuple[dtime, dtime]:
    """Local working hours: FIELD_DAY, narrowed by the tenant's operating window when it has one."""
    lo, hi = FIELD_DAY
    if rules.window_start and rules.window_end:
        ws, we = dtime.fromisoformat(rules.window_start), dtime.fromisoformat(rules.window_end)
        if ws < we:
            lo, hi = max(lo, ws), min(hi, we)
            if hi <= lo:
                lo, hi = ws, we
    return lo, hi


Day = tuple[datetime, datetime]


def field_days(earliest: datetime, latest: datetime, rules: Rules) -> tuple[list[Day], list[Day]]:
    """Usable working periods (UTC, whole minutes) inside [earliest, latest]: up to FIELD_PAST_DAYS past days and
    today, on the tenant's operating weekdays, each at least FIELD_MIN_DAY long."""
    zone = ZoneInfo(rules.timezone)
    lo, hi = field_window(rules)
    earliest, latest = _minute_up(earliest), _minute_down(latest)
    first, last = earliest.astimezone(zone).date(), latest.astimezone(zone).date()
    past: list[Day] = []
    today: list[Day] = []
    d = first
    while d <= last:
        s = max(datetime.combine(d, lo, zone), earliest)
        e = min(datetime.combine(d, hi, zone), latest)
        if d.weekday() in rules.weekdays and e - s >= FIELD_MIN_DAY:
            (today if d == last else past).append((s.astimezone(UTC), e.astimezone(UTC)))
        d += timedelta(days=1)
    return past[-FIELD_PAST_DAYS:], today


def day_segments(number: str, a: datetime, b: datetime, standby: bool, downtime: bool) -> list[Segment]:
    """One day of a job's work log between a and b: work with a lunch gap, a standby block on the first day and
    a short downtime (with its note) on the second (both on the first when the job has a single day)."""
    span = b - a
    if span < timedelta(minutes=30):
        return []
    if standby and downtime:
        pattern = [
            ("WORK", 0, 0.35),
            ("STANDBY", 0.35, 0.45),
            ("WORK", 0.45, 0.7),
            ("DOWNTIME", 0.7, 0.78),
            ("WORK", 0.78, 1.0),
        ]
    elif standby:
        pattern = [("WORK", 0, 0.45), ("STANDBY", 0.45, 0.6), ("WORK", 0.6, 1.0)]
    elif downtime:
        pattern = [("WORK", 0, 0.45), ("WORK", 0.52, 0.75), ("DOWNTIME", 0.75, 0.83), ("WORK", 0.83, 1.0)]
    else:
        pattern = [("WORK", 0, 0.45), ("WORK", 0.52, 1.0)]
    notes = {"STANDBY": STANDBY_NOTES[number], "DOWNTIME": DOWNTIME_NOTES[number]}
    return [
        Segment(kind, _minute_down(a + span * f0), _minute_down(a + span * f1), notes.get(kind))
        for kind, f0, f1 in pattern
    ]


def plan_field(
    past: list[Day], today: list[Day], openings: dict[str, Decimal]
) -> tuple[dict[str, JobRun], list[FieldEvent]]:
    """The whole field history, in time order. Role days map onto the usable past days (4 of them: exactly
    "started 4/3/2 days ago, completed yesterday"); with fewer, roles share days; with none, all of it is today."""
    days = past + today
    if not days:
        raise ValueError("no usable working period")

    def role_day(r: int) -> Day:
        return past[min(r, len(past) - 1)] if past else days[-1]

    index = {d: i for i, d in enumerate(days)}
    runs: dict[str, JobRun] = {}
    events: list[FieldEvent] = [
        FieldEvent(days[0][0] - timedelta(minutes=10), "FLOAT", data={"amount": FIELD_FLOAT}),
        FieldEvent(
            days[0][0] + timedelta(minutes=5),
            "FUEL_PURCHASE",
            data={"litres": FUEL_PURCHASE[0], "unit_price": FUEL_PURCHASE[1], "supplier": FUEL_PURCHASE[2]},
        ),
    ]
    starts: Counter[Day] = Counter()
    for r, number in enumerate(FIELD_STARTS):
        day = role_day(r)
        at = day[0] + timedelta(minutes=15 + 20 * starts[day])
        starts[day] += 1
        run = runs[number] = JobRun(number, at, openings[number])
        end_day = role_day(3) if number == FIELD_COMPLETED else days[-1]
        if number == FIELD_COMPLETED:
            run.closing_at = end_day[1] - timedelta(minutes=45)
        si, ei = index[day], index[end_day]
        for i in range(si, ei + 1):
            a = at + timedelta(minutes=10) if i == si else days[i][0]
            b = run.closing_at - timedelta(minutes=5) if run.closing_at and i == ei else days[i][1]
            downtime = i == si + 1 if ei > si else True
            run.segments += day_segments(number, a, b, standby=i == si, downtime=downtime)
        events += [
            FieldEvent(at, "OPENING", number, {"reading": run.opening}),
            FieldEvent(at + timedelta(minutes=1), "START", number),
            FieldEvent(
                at + timedelta(minutes=5),
                "FUEL_ISSUE",
                number,
                {"litres": FUEL_ISSUE_LITRES[number], "unit_price": FUEL_UNIT_PRICE, "meter": run.opening},
            ),
        ]
        events += [FieldEvent(s.end, "ACTIVITY", number, {"segment": s}) for s in run.segments]
        if run.closing_at:
            c = run.closing_at
            closing = run.meter_at(c)
            events += [
                FieldEvent(c, "CLOSING", number, {"reading": closing}),
                FieldEvent(c + timedelta(minutes=10), "ACK", number, {"hours": closing - run.opening}),
                FieldEvent(c + timedelta(minutes=12), "COMPLETE", number),
                FieldEvent(c + timedelta(minutes=20), "COLLECTION", number, {"amount": FIELD_COLLECTION}),
                FieldEvent(c + timedelta(minutes=35), "HANDOVER", None, {"amount": FIELD_HANDOVER}),
            ]
    for code, number, during, description, supplier, amount in FIELD_EXPENSES:
        run = runs[number]
        seg = next((s for s in run.segments if s.kind == during), None)
        at = _minute_down(seg.start + (seg.end - seg.start) / 2) if seg else run.opening_at + timedelta(minutes=30)
        data = {"category": code, "description": description, "supplier": supplier, "amount": amount}
        events.append(FieldEvent(at, "EXPENSE", number, data))
    events.sort(key=lambda e: e.at)
    return runs, events


def png_image(text: str, key: str) -> bytes:
    """A small generated grayscale PNG of `text` (digits, '.', ',') with a key-derived bit strip underneath, so
    every image is unique (the server flags a meter photo or receipt that was used before). A placeholder, not a
    camera photo."""
    font = {
        "0": "01110100011001110101110011000101110",
        "1": "00100011000010000100001000010001110",
        "2": "01110100010000100010001000100011111",
        "3": "11110000010000101110000010000111110",
        "4": "00010001100101010010111110001000010",
        "5": "11111100001111000001000010000111110",
        "6": "00110010001000011110100011000101110",
        "7": "11111000010001000100010000100001000",
        "8": "01110100011000101110100011000101110",
        "9": "01110100011000101111000010001001100",
        ".": "00000000000000000000000000110001100",
        ",": "00000000000000000000001100010001000",
        " ": "00000000000000000000000000000000000",
    }
    scale, pad = 6, 3
    glyphs = [font.get(ch, font[" "]) for ch in text]
    cols = pad * 2 + len(glyphs) * 6
    width, height = cols * scale, (pad * 2 + 7 + 3) * scale
    bits = "".join(f"{b:08b}" for b in hashlib.sha256(key.encode()).digest())
    rows = []
    for y in range(height):
        cy, row = y // scale, bytearray(b"\xff" * width)
        for x in range(width):
            cx = x // scale
            if pad <= cy < pad + 7:
                gi, gx = divmod(cx - pad, 6)
                if 0 <= gi < len(glyphs) and cx >= pad and gx < 5 and glyphs[gi][(cy - pad) * 5 + gx] == "1":
                    row[x] = 0x10
            elif cy == pad + 8 and bits[(x // 2) % len(bits)] == "1":
                row[x] = 0x40
        rows.append(b"\x00" + bytes(row))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)  # 8-bit grayscale
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat()


def opening_meters(state: dict[str, Any]) -> dict[str, Decimal]:
    """Opening readings at each machine's current meter: the simulated tracker's engine hours (the seed baseline
    when the state has none)."""
    hours = {u["code"]: Decimal(int(u["hours_ms"])) / Decimal(3_600_000) for u in state.get("units", [])}
    baseline = {m[0]: Decimal(str(m[8])) for m in MACHINES}
    machine_of = {j[0]: j[2] for j in JOBS}
    return {
        n: hours.get(machine_of[n], baseline[machine_of[n]]).quantize(TENTH, rounding=ROUND_DOWN) for n in FIELD_STARTS
    }


def homes(state: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Where each tracked machine works (the simulated tracker's home spot on its site)."""
    return {u["code"]: (float(u["home"][0]), float(u["home"][1])) for u in state.get("units", [])}


def describe_plan(runs: dict[str, JobRun], events: list[FieldEvent], tz: str) -> list[str]:
    zone, out = ZoneInfo(tz), []
    for e in events:
        when = e.at.astimezone(zone).strftime("%a %d %b %H:%M")
        d = e.data
        if e.kind == "ACTIVITY":
            s = d["segment"]
            what = f"{s.kind:8} {s.start.astimezone(zone):%H:%M}-{s.end.astimezone(zone):%H:%M}" + (
                f" ({s.note})" if s.note else ""
            )
        elif e.kind in ("OPENING", "CLOSING"):
            what = f"{e.kind.lower()} reading {d['reading']} h"
        elif e.kind == "ACK":
            what = f"customer acknowledgement by {FIELD_SIGNER} ({d['hours']} h)"
        elif e.kind in ("FUEL_ISSUE", "FUEL_PURCHASE"):
            what = f"fuel {e.kind.split('_')[1].lower()} {d['litres']} L at {d['unit_price']}/L"
        elif e.kind == "EXPENSE":
            what = f"expense {d['category']} {d['amount']}: {d['description']}"
        elif e.kind in ("FLOAT", "COLLECTION", "HANDOVER"):
            what = f"cash {e.kind.lower()} {d['amount']}" + (" (issued by the office)" if e.kind == "FLOAT" else "")
        else:
            what = e.kind.lower()
        out.append(f"{when}  {e.job or '':10}  {what}")
    for n, r in runs.items():
        end = f"closing {r.meter_at(r.closing_at)} h" if r.closing_at else "still IN_PROGRESS"
        out.append(f"{n}: opening {r.opening} h, {end}")
    out.append(f"{FIELD_READY}: left APPROVED (ready to start)")
    return out


@dataclass
class DemoSupervisor:
    email: str
    password: str
    user_id: str
    subject: str
    staff_id: str


def demo_supervisor(a: argparse.Namespace, state: dict[str, Any]) -> DemoSupervisor:
    """The supervisor account `seed` created, from its credentials file only; anything else is refused."""
    path = Path(a.out_dir) / f"demo-{a.slug}-credentials.json"
    if not path.exists():
        raise Refuse(
            f"No credentials file {path}. `field` signs in only as the demo supervisor that `seed` created and",
            "whose password `seed` wrote there; it never uses any other account.",
        )
    creds = json.loads(path.read_text())
    acc = (creds.get("accounts") or {}).get("supervisor") or {}
    user = (state.get("users") or {}).get("supervisor") or {}
    expected = f"supervisor.{a.slug}@{a.demo_domain}"
    problems = []
    if creds.get("tenant_id") != state["tenant_id"]:
        problems.append(
            f"{path.name} belongs to tenant {creds.get('tenant_id')}, the state file to {state['tenant_id']}"
        )
    if not acc.get("email") or not acc.get("password"):
        problems.append(f"{path.name} has no demo supervisor account")
    elif not norm(acc["email"]) == norm(user.get("email")) == norm(expected):
        problems.append(f"the supervisor account must be {expected} (as created by `seed`), found {acc['email']}")
    if user.get("preexisting") or not user.get("subject") or not user.get("user_id"):
        problems.append("the state file does not record a supervisor account created by `seed`")
    if not state.get("staff", {}).get("supervisor"):
        problems.append("the state file has no supervisor staff record")
    if problems:
        raise Refuse("Will not sign in for the field history:", *problems)
    return DemoSupervisor(
        acc["email"], acc["password"], str(user["user_id"]), str(user["subject"]), str(state["staff"]["supervisor"])
    )


class FieldDevice:
    """The demo supervisor's 'phone': device session, evidence uploads and offline-operation pushes."""

    def __init__(self, api: Api, device_id: str):
        self.api, self.device_id = api, device_id

    def register(self) -> None:
        self.api.post(
            "/sync/devices",
            {"device_id": self.device_id, "platform": "ANDROID", "app_version": "demo-field-1"},
            "register device",
            (201,),
        )

    def upload(self, data: bytes, purpose: str) -> str:
        """Resumable evidence upload, as the app does it; content the server already has is not sent again."""
        sha = hashlib.sha256(data).hexdigest()
        s = self.api.post(
            "/sync/blobs", {"sha256": sha, "size_bytes": len(data), "purpose": purpose}, "start upload", (201,)
        )
        if s["status"] != "COMPLETE":
            size = int(s["chunk_size"])
            for i in range(int(s["total_chunks"])):
                self.api.put_bytes(f"/sync/blobs/{s['id']}/chunks/{i}", data[i * size : (i + 1) * size], "chunk")
            s = self.api.post(f"/sync/blobs/{s['id']}/complete", {}, "complete upload", (200,))
        return str(s["attachment_id"])

    def push(self, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for i in range(0, len(ops), FIELD_BATCH):
            batch = ops[i : i + FIELD_BATCH]
            body = {
                "device_now": _iso(utcnow()),
                "operations": [
                    {k: o[k] for k in ("id", "op_type", "created_at_device", "depends_on", "payload")} for o in batch
                ],
            }
            res = self.api.post("/sync/push", body, "sync push", (200,))
            for o, r in zip(batch, res["results"], strict=True):
                if r["status"] not in ("ACKED", "DUPLICATE") or r.get("error"):
                    err = r.get("error") or {}
                    raise RuntimeError(
                        f"{o['label']}: {r['status']} {err.get('code', '')} {str(err.get('message', ''))[:300]}"
                    )
                results.append({"label": o["label"], "op_type": o["op_type"], "entity": r["result"].get("entity")})
        return results


def build_field_ops(
    device: FieldDevice,
    boot: dict[str, Any],
    events: list[FieldEvent],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Turns the plan into sync operations (with uploaded evidence where the tenant's policy asks for it)."""
    data = boot["data"]
    jobs = {j["job_number"]: j for j in data["jobs"]}
    customer_of = {c["id"]: c["customer_id"] for c in data["contracts"]}
    categories = {c["code"]: c["id"] for c in data["expense_categories"]}
    snapshots = {(p["policy_type"], p["scope_key"]): p["values"] for p in boot["policy_snapshots"]}
    expense_policy = snapshots[("EXPENSE_CAPTURE", "tenant")]
    receipt_above = Decimal(str(expense_policy["receipt_required_above"]))
    auto_limit = Decimal(str(expense_policy["auto_approve_limit"]))
    machine_of = {j[0]: j[2] for j in JOBS}
    spots = homes(state)
    ops: list[dict[str, Any]] = []
    op_of: dict[tuple[str, str], str] = {}  # (job, kind) -> op id, for dependencies

    def meter_policy(job: dict[str, Any]) -> dict[str, Any]:
        found = (
            snapshots.get(("METER_CAPTURE", f"machine:{job['machine_id']}")) or snapshots[("METER_CAPTURE", "tenant")]
        )
        return dict(found)

    def gps(number: str, at: datetime, key: str) -> dict[str, Any]:
        lat, lon = spots[machine_of[number]]
        rng = random.Random(key)  # noqa: S311 - plausible jitter, not crypto
        return {
            "status": "FIX",
            "latitude": round(lat + rng.uniform(-0.00025, 0.00025), 7),
            "longitude": round(lon + rng.uniform(-0.00025, 0.00025), 7),
            "accuracy_m": round(rng.uniform(4.0, 9.0), 1),
            "captured_at": _iso(at - timedelta(seconds=rng.randint(3, 20))),
            "provider": "fused",
        }

    def add(e: FieldEvent, op_type: str, payload: dict[str, Any], label: str, deps: tuple[str, ...] = ()) -> str:
        oid = str(uuid.uuid4())
        depends = [op_of[(e.job or "", d)] for d in deps if (e.job or "", d) in op_of]
        ops.append(
            {
                "id": oid,
                "op_type": op_type,
                "created_at_device": _iso(e.at),
                "depends_on": depends,
                "payload": payload,
                "label": label,
            }
        )
        op_of[(e.job or "", e.kind)] = oid
        return oid

    for e in events:
        job = jobs.get(e.job or "")
        if e.kind == "FLOAT":
            continue  # issued by the office (see issue_float), not by the supervisor's phone
        if e.kind == "FUEL_PURCHASE":
            payload = {
                "client_id": str(uuid.uuid4()),
                "event_type": "PURCHASE",
                "litres": str(e.data["litres"]),
                "unit_price": str(e.data["unit_price"]),
                "supplier": e.data["supplier"],
                "occurred_at": _iso(e.at),
                "note": "Diesel for the site bowser",
            }
            add(e, "FUEL_EVENT", payload, f"fuel purchase {e.data['litres']} L")
            continue
        if e.kind == "HANDOVER":
            payload = {
                "client_id": str(uuid.uuid4()),
                "amount": str(e.data["amount"]),
                "handed_at": _iso(e.at),
                "reference": "HO-01",
                "note": "Cash handed over to the office",
            }
            add(e, "CASH_HANDOVER", payload, f"cash handover {e.data['amount']}")
            continue
        assert job is not None, e
        number = str(e.job)
        if e.kind in ("OPENING", "CLOSING"):
            pol = meter_policy(job)
            mode = str(pol["opening_mode" if e.kind == "OPENING" else "closing_mode"])
            reading: Decimal = e.data["reading"]
            cid = str(uuid.uuid4())
            payload = {
                "id": cid,
                "job_id": job["id"],
                "kind": e.kind,
                "capture_mode": mode,
                "reading": str(reading),
                "gps": gps(number, e.at, cid),
                "device_id": device.device_id,
                "captured_at": _iso(e.at),
            }
            if mode == "AUTOMATIC" or pol.get("manual_photo_required"):
                payload["photo_attachment_id"] = device.upload(png_image(f"{reading:.1f}", cid), "METER_PHOTO")
            if mode == "AUTOMATIC":  # the digits are known (we drew them); the engine name says so
                payload |= {
                    "ocr_raw_text": f"{reading:.1f}",
                    "ocr_value": str(reading),
                    "ocr_confidence": 0.96,
                    "ocr_engine": OCR_ENGINE,
                }
            add(e, "METER_CAPTURE", payload, f"{number} {e.kind.lower()} reading {reading}", ("START",))
        elif e.kind in ("START", "COMPLETE"):
            deps = ("OPENING",) if e.kind == "START" else ("CLOSING", "ACK")
            add(e, "JOB_TRANSITION", {"job_id": job["id"], "action": e.kind}, f"{number} {e.kind.lower()}", deps)
        elif e.kind == "ACTIVITY":
            s: Segment = e.data["segment"]
            payload = {
                "job_id": job["id"],
                "client_id": str(uuid.uuid4()),
                "activity_type": s.kind,
                "started_at": _iso(s.start),
                "ended_at": _iso(s.end),
                "note": s.note,
                "device_id": device.device_id,
            }
            add(e, "JOB_ACTIVITY", payload, f"{number} {s.kind.lower()} {s.start:%d %b %H:%M}Z", ("START",))
        elif e.kind == "ACK":
            payload = {
                "job_id": job["id"],
                "client_id": str(uuid.uuid4()),
                "method": "NAME_CONFIRMATION",
                "signer_name": FIELD_SIGNER,
                "acknowledged_hours": str(e.data["hours"]),
                "captured_at": _iso(e.at),
            }
            add(e, "JOB_ACKNOWLEDGEMENT", payload, f"{number} acknowledgement", ("CLOSING",))
        elif e.kind == "FUEL_ISSUE":
            payload = {
                "client_id": str(uuid.uuid4()),
                "event_type": "ISSUE",
                "litres": str(e.data["litres"]),
                "unit_price": str(e.data["unit_price"]),
                "machine_id": job["machine_id"],
                "job_id": job["id"],
                "meter_reading": str(e.data["meter"]),
                "occurred_at": _iso(e.at),
                "note": "Issued from the site bowser",
            }
            add(e, "FUEL_EVENT", payload, f"{number} fuel issue {e.data['litres']} L")
        elif e.kind == "EXPENSE":
            amount: Decimal = e.data["amount"]
            if auto_limit > 0 and e.data["category"] == "ALLOWANCE":
                amount = min(amount, auto_limit)  # small enough for the tenant's auto-approval
            elif auto_limit > 0 and e.data["category"] == "SPARES":
                amount = max(amount, auto_limit + 10000)  # always one for the owner/accountant to approve
            cid = str(uuid.uuid4())
            payload = {
                "client_id": cid,
                "category_id": categories[e.data["category"]],
                "supplier": e.data["supplier"],
                "description": e.data["description"],
                "amount": str(amount),
                "incurred_at": _iso(e.at),
                "machine_id": job["machine_id"],
                "job_id": job["id"],
                "paid_from": "CASH_CUSTODY",
                "receipt_attachment_ids": [],
                "gps": gps(number, e.at, cid),
                "device_id": device.device_id,
            }
            if amount > receipt_above:
                payload["receipt_attachment_ids"] = [device.upload(png_image(f"{amount:,.0f}", cid), "EXPENSE_RECEIPT")]
            add(e, "EXPENSE", payload, f"{number} expense {e.data['category']} {amount}")
        elif e.kind == "COLLECTION":
            payload = {
                "client_id": str(uuid.uuid4()),
                "customer_id": customer_of[job["contract_id"]],
                "amount": str(e.data["amount"]),
                "received_at": _iso(e.at),
                "reference": f"{number}-CASH-01",
                "note": f"Part payment in cash for {number}",
            }
            add(e, "CASH_COLLECTION", payload, f"{number} cash collection {e.data['amount']}", ("COMPLETE",))
    return ops


def issue_float(kc: KeycloakAdmin, a: argparse.Namespace, state: dict[str, Any], staff_id: str, at: datetime) -> None:
    """A supervisor cannot give themselves cash: the office issues the float. As in `seed`, that is done under a
    temporary managed-service mandate, by a throwaway platform user (both removed at the end)."""
    with platform_session(kc, a.demo_domain) as pf:
        tenant = find_tenant(pf.api, a.registration_number, a.tenant_name)
        if tenant["id"] != state["tenant_id"]:
            raise Refuse(f"state file belongs to tenant {state['tenant_id']}, not {tenant['id']}")
        with mandate(pf, tenant, a.consent_reference, "issuing the demo supervisor's cash float") as t:
            t.post(
                "/tenant/cash/floats",
                {
                    "staff_member_id": staff_id,
                    "amount": str(FIELD_FLOAT),
                    "occurred_at": _iso(at),
                    "reference": "FLOAT-01",
                    "note": "Site cash float for the week",
                },
                "issue cash float",
                (201,),
            )
    log(f"cash float {FIELD_FLOAT} issued to the demo supervisor (by the office, under the mandate)")


def reset_demo_password(kc: KeycloakAdmin, a: argparse.Namespace, who: DemoSupervisor) -> DemoSupervisor:
    """New generated password for the seed-created demo supervisor only (identity checked by the caller against the
    Keycloak id `seed` recorded), written to the credentials file (mode 600) and never printed."""
    password = "Dm-" + secrets.token_urlsafe(24)
    kc.set_password(who.subject, password)
    kc.clear_lockout(who.subject)
    path = Path(a.out_dir) / f"demo-{a.slug}-credentials.json"
    creds = json.loads(path.read_text())
    creds["accounts"]["supervisor"]["password"] = password
    write_private(path, creds)
    log(f"new password set for {who.email}; it is in {path.name} (not printed)")
    return DemoSupervisor(who.email, password, who.user_id, who.subject, who.staff_id)


def field_history(a: argparse.Namespace) -> int:
    path = state_file(a)
    state = load_state(path)
    if state.get("retired_at"):
        raise Refuse("the demo data was retired; no field history is added to it")
    if state.get("incomplete"):
        raise Refuse("the seed did not finish (see its output); `retire --yes` undoes what it created")
    played = state.get("field") or {}
    if played.get("completed_at"):
        raise Refuse(f"the field history was already played ({played['completed_at']}); it is played only once")
    who = demo_supervisor(a, state)
    rules = rules_of(state)
    if a.dry_run:
        earliest = datetime.fromisoformat(state["seeded_at"]) + timedelta(minutes=30)
        past, today = field_days(earliest, utcnow() - timedelta(minutes=10), rules)
        if not past and not today:
            raise Refuse("no working period of 3 h yet since the jobs were approved; run `field` later")
        runs, events = plan_field(past, today, opening_meters(state))
        log(f"DRY RUN: nothing is sent. Plan (times in {rules.timezone}; job approval approximated by the seed time):")
        for line in describe_plan(runs, events, rules.timezone):
            log("  " + line)
        log(f"would sign in as {who.email} (password from the credentials file, never printed)")
        return 0
    kc = KeycloakAdmin()
    hits = kc.users_by_email(who.email)
    if len(hits) != 1 or str(hits[0]["id"]) != who.subject or not hits[0].get("enabled"):
        raise Refuse(f"{who.email} is not the enabled Keycloak user `seed` created; nothing was changed")
    if a.reset_demo_password:
        who = reset_demo_password(kc, a, who)
    client = kc.create_client()
    try:
        device = FieldDevice(
            Api(Login(client, who.email, who.password), state["tenant_id"], {"X-Device-Id": f"demo-{a.slug}-phone"}),
            f"demo-{a.slug}-phone",
        )
        try:
            me = device.api.get("/me")
        except LoginFailed as e:
            raise Refuse(
                f"Keycloak refused the demo supervisor's sign-in: {e}.",
                "Usually its password was changed after `seed` (e.g. with Change password in the app), so the",
                "credentials file is out of date, or it is locked after failed sign-ins. Nothing was changed.",
                "Re-run with --reset-demo-password to give this demo account (and only it) a new generated",
                "password, saved to the credentials file; then sign in to the apps with that new password.",
            ) from None
        if str(me.get("user_id")) != who.user_id:
            raise Refuse(f"{who.email} signed in as another app user than the one `seed` created; stopping")
        log(f"signed in as the demo supervisor {who.email}")
        device.register()
        boot = device.api.get("/sync/bootstrap")
        if not played.get("ops"):
            plan_ops(device, boot, state, rules)
            write_private(path, state)
        played = state["field"]
        if not played.get("float_issued"):
            issue_float(kc, a, state, who.staff_id, datetime.fromisoformat(played["float_at"]))
            played["float_issued"] = True
            write_private(path, state)
        log(f"pushing {len(played['ops'])} operations as the supervisor's phone (sync protocol)")
        results = device.push(played["ops"])
        played["completed_at"] = utcnow().isoformat()
        write_private(path, state)
        report_field(device.api, results)
    finally:
        try:
            kc.delete_client(client.uuid)
            log("temporary Keycloak client deleted")
        except Exception as e:
            log(f"WARNING: delete Keycloak client {client.client_id} in the admin console ({e})")
    return 0


def plan_ops(device: FieldDevice, boot: dict[str, Any], state: dict[str, Any], rules: Rules) -> None:
    """First run: refuse unless the field is untouched, plan from the real approval and server times, upload the
    evidence and keep the operations in the state file (a re-run after a failure re-sends the same operations,
    which the server answers as duplicates)."""
    data = boot["data"]
    jobs = {j["job_number"]: j for j in data["jobs"]}
    wanted = (*FIELD_STARTS, FIELD_READY)
    problems = [f"{n} is {jobs[n]['status']}" for n in wanted if n in jobs and jobs[n]["status"] != "APPROVED"]
    problems += [f"{n} is not one of the supervisor's jobs" for n in wanted if n not in jobs]
    mine = ("meter_captures", "job_activities", "expenses", "fuel_events", "cash_collections", "cash_handovers")
    problems += [f"{len(data[f'my_{k}'])} {k.replace('_', ' ')}" for k in mine if data.get(f"my_{k}")]
    if problems:
        raise Refuse("Field activity already exists (only played on untouched demo jobs):", *problems)
    approved = max(datetime.fromisoformat(jobs[n]["approved_at"]) for n in wanted)
    server_now = datetime.fromisoformat(boot["server_time"])
    past, today = field_days(approved + timedelta(minutes=15), server_now - timedelta(minutes=10), rules)
    if not past and not today:
        raise Refuse(
            f"No working period of at least 3 h between the job approval ({approved.isoformat()}) and now.",
            "Field records before approval would be flagged as work without authorization; run `field` later.",
        )
    runs, events = plan_field(past, today, opening_meters(state))
    log(f"plan ({rules.timezone}):")
    for line in describe_plan(runs, events, rules.timezone):
        log("  " + line)
    ops = build_field_ops(device, boot, events, state)
    float_at = next(e.at for e in events if e.kind == "FLOAT")
    state["field"] = {
        "planned_at": utcnow().isoformat(),
        "device_id": device.device_id,
        "float_at": float_at.isoformat(),
        "float_issued": False,
        "ops": ops,
    }


def report_field(api: Api, results: list[dict[str, Any]]) -> None:
    for r in results:
        ent = r["entity"] or {}
        if r["op_type"] == "METER_CAPTURE":
            cap = ent.get("capture", {})
            found = [f["type"] for f in ent.get("findings", [])]
            log(f"{r['label']}: {cap.get('state')} findings={found or 'none'} gps={cap.get('tracker_comparison')}")
        elif r["op_type"] == "EXPENSE":
            log(f"{r['label']}: {ent.get('status')}")
    jobs = {j["job_number"]: j for j in api.rows("/tenant/jobs")}
    for n in (*FIELD_STARTS, FIELD_READY):
        if n in jobs:
            s = api.get(f"/tenant/jobs/{jobs[n]['id']}")
            log(
                f"{n}: {s['job']['status']} meter={s['meter_hours']} billable={s['billable_hours']} "
                f"open exceptions={s['open_exceptions']} billing_ready={s['billing_ready']}"
            )
    for c in api.get("/tenant/cash/custody/me"):
        log(f"cash custody: {c}")
    log("DEMO FIELD OK")


# --- status ---------------------------------------------------------------------------------------------------------
def status(a: argparse.Namespace) -> int:
    path = state_file(a)
    kc = KeycloakAdmin()
    with platform_session(kc, a.demo_domain) as pf:
        tenant = find_tenant(pf.api, a.registration_number, a.tenant_name)
        sub = pf.api.get(f"/platform/tenants/{tenant['id']}/subscription")
        print(f"tenant        {tenant['display_name']} ({tenant['id']}) reg={tenant.get('registration_number')}")
        print(
            f"              verification={tenant['verification_status']} status={tenant['status']} "
            f"access={tenant['access_state']}"
        )
        print(
            f"subscription  {sub['status']} enrolled_assets={sub['enrolled_assets']} "
            f"billable_assets={sub['billable_assets']}"
        )
        mandates = [m for m in pf.api.get("/platform/mandates") if m["tenant_id"] == tenant["id"]]
        print(
            f"mandates      {len(mandates)} total, open: "
            f"{[m['reference'] for m in mandates if m['status'] in OPEN_MANDATE] or 'none'}"
        )
        if path.exists():
            st = json.loads(path.read_text())
            feeds = st.get("feeds") or [{}]
            played = (st.get("field") or {}).get("completed_at") or ("partial" if st.get("field") else "no")
            print(
                f"state file    {path}: seeded {st.get('seeded_at')}, incomplete={bool(st.get('incomplete'))}, "
                f"last fix {st.get('last_time')}, "
                f"last feed {feeds[-1].get('started', 'never')}, retired {st.get('retired_at') or 'no'}, "
                f"field history {played}"
            )
        else:
            print(f"state file    {path}: none")
        if a.quick:
            return 0
        with mandate(pf, tenant, a.consent_reference, "a read-only demo status check") as t:
            counts = {
                "machines": len(t.rows("/tenant/machines", {"include_inactive": "true"})),
                "trackers": len(t.rows("/tenant/trackers")),
                "job_sites": len(t.rows("/tenant/job-sites")),
                "geofences": len(t.rows("/tenant/geofences")),
                "customers": len(t.rows("/tenant/customers")),
                "contracts": len(t.rows("/tenant/contracts")),
                "staff": len(t.rows("/tenant/staff")),
                "members": len(t.rows("/tenant/access/members")),
                "expense_categories": len(t.rows("/tenant/expense-categories")),
            }
            print("counts        " + " ".join(f"{k}={v}" for k, v in counts.items()))
            jobs = Counter(j["status"] for j in t.rows("/tenant/jobs"))
            print(f"jobs          {dict(jobs)}")
            fleet = t.get("/tenant/fleet/map")
            print(
                f"fleet map     connectivity={dict(Counter(r['connectivity'] for r in fleet))} "
                f"engine={dict(Counter(r['observed_engine'] for r in fleet))}"
            )
            alerts = t.rows("/tenant/alerts")
            print(
                f"alerts        open={dict(Counter(x['alert_type'] for x in alerts if x['status'] == 'OPEN'))} "
                f"all={dict(Counter(x['alert_type'] for x in alerts))}"
            )
            all_jobs = t.rows("/tenant/jobs")
            exceptions = t.rows("/tenant/exceptions")
            field_counts = {
                "meter_captures": len(t.rows("/tenant/meter-captures")),
                "activities": sum(len(t.get(f"/tenant/jobs/{j['id']}/activities")) for j in all_jobs),
                "fuel_events": len(t.rows("/tenant/fuel-events")),
                "cash_collections": sum(p["method"] == "CASH" for p in t.rows("/tenant/customer-payments")),
            }
            print("field         " + " ".join(f"{k}={v}" for k, v in field_counts.items()))
            print(
                f"              expenses={dict(Counter(x['status'] for x in t.rows('/tenant/expenses')))} "
                f"handovers={dict(Counter(x['status'] for x in t.rows('/tenant/cash/handovers')))}"
            )
            print(
                f"exceptions    open={dict(Counter(x['exception_type'] for x in exceptions if x['status'] == 'OPEN'))} "
                f"all={len(exceptions)}"
            )
    return 0


# --- retire ---------------------------------------------------------------------------------------------------------
def retire(a: argparse.Namespace) -> int:
    if not a.yes:
        raise Refuse("retire changes the tenant (soft: cancels/deactivates, never deletes); pass --yes")
    path = state_file(a)
    state = load_state(path)
    kc = KeycloakAdmin()
    done: list[str] = []
    failed: list[str] = []
    reason = "Demo data retired (scripts/seed-demo-tenant.sh retire)"

    def outcome(label: str, error: Exception | None) -> None:
        if error is None:
            done.append(label)
        else:
            failed.append(
                f"{label}: {error.code or error.status}" if isinstance(error, ApiError) else f"{label}: {error}"
            )

    def do(t: Api, label: str, path: str, body: dict[str, Any]) -> None:
        try:
            t.post(path, body, label, (200,))
            outcome(label, None)
        except (ApiError, httpx.HTTPError) as e:
            outcome(label, e)

    with platform_session(kc, a.demo_domain) as pf:
        tenant = find_tenant(pf.api, a.registration_number, a.tenant_name)
        if tenant["id"] != state["tenant_id"]:
            raise Refuse(f"state file {path} belongs to tenant {state['tenant_id']}, not {tenant['id']}")
        with mandate(pf, tenant, a.consent_reference, "retiring demo data") as t:
            now = utcnow()
            created = state["created"]
            for jid in created.get("jobs", []):
                job = t.get(f"/tenant/jobs/{jid}")["job"]
                if job["status"] in ("DRAFT", "PENDING_APPROVAL", "APPROVED"):
                    body = {"action": "CANCEL", "reason": reason}
                    do(t, f"cancel job {job['job_number']}", f"/tenant/jobs/{jid}/transitions", body)
            for code, trk in state.get("trackers", {}).items():
                body = {"effective_to": now.isoformat(), "reason": reason}
                do(t, f"unassign tracker {code}", f"/tenant/trackers/{trk}/unassign", body)
                do(t, f"retire tracker {code}", f"/tenant/trackers/{trk}/state", {"state": "RETIRED", "reason": reason})
            for eid in state.get("enrollments", []):
                body = {"effective_to": now.date().isoformat(), "reason": "REMOVED_FROM_FLEET"}
                do(t, f"end enrollment {eid}", f"/tenant/billing/enrollments/{eid}/end", body)
            for code, mid in state.get("machines", {}).items():
                do(t, f"deactivate machine {code}", f"/tenant/machines/{mid}/deactivate", {"reason": reason})
            for kind, fmt in (
                ("geofences", "/tenant/geofences/{}/deactivate"),
                ("sites", "/tenant/job-sites/{}/deactivate"),
                ("contracts", "/tenant/contracts/{}/close"),
                ("customers", "/tenant/customers/{}/deactivate"),
                ("staff", "/tenant/staff/{}/deactivate"),
            ):
                for rid in created.get(kind, []):
                    do(t, f"{fmt.rsplit('/', 1)[-1]} {kind} {rid}", fmt.format(rid), {"reason": reason})
            for role, u in state.get("users", {}).items():
                do(t, f"revoke {role} {u['email']}", f"/tenant/access/members/{u['user_id']}/roles/{role}/revoke", {})
                if u.get("preexisting") or not u.get("subject"):
                    continue  # an account this script did not create keeps its login
                try:
                    kc_user = kc.get_user(u["subject"])
                    if kc_user and norm(kc_user.get("email")) == norm(u["email"]):  # only the account seed created
                        kc.update_user(u["subject"], {"enabled": False})
                    outcome(f"disable login {u['email']}", None)
                except RuntimeError as e:
                    outcome(f"disable login {u['email']}", e)
    tl = (env("TRACCAR_ADMIN_EMAIL"), env("TRACCAR_ADMIN_PASSWORD"))
    for raw in state.get("units", []):
        if raw.get("traccar_id") and all(tl):
            try:
                url = f"{TRACCAR_API}/api/devices/{raw['traccar_id']}"
                httpx.delete(url, auth=tl, timeout=TIMEOUT).raise_for_status()
                outcome(f"remove Traccar device {raw['code']}", None)
            except httpx.HTTPError as e:
                outcome(f"remove Traccar device {raw['code']}", e)
    state["retired_at"] = utcnow().isoformat()
    write_private(path, state)
    log(f"retired: {len(done)} steps done")
    for f in failed:
        log(f"not done: {f}")
    if failed:
        log("re-run `retire --yes` later for refused steps (for example machines refused while still enrolled today)")
    return 0 if not failed else 1


# --- CLI ------------------------------------------------------------------------------------------------------------
def state_file(a: argparse.Namespace) -> Path:
    return Path(a.out_dir) / f"demo-{a.slug}-state.json"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = p.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--registration-number", default="2026/10/0001")
    common.add_argument("--tenant-name", default="Wambura & Sons Ltd", help="fallback: exact display or legal name")
    common.add_argument("--slug", default="wambura", help="names the state/credentials files and demo e-mails")
    common.add_argument("--out-dir", default="/out", help="directory for the state and credentials files")
    common.add_argument("--demo-domain", default="demo.asseta.co.tz", help="e-mail domain of the demo accounts")
    common.add_argument(
        "--consent-reference",
        default="Platform owner demo setup",
        help="recorded on the temporary managed-service mandate (the client sees it)",
    )
    s = sub.add_parser("seed", parents=[common])
    s.add_argument("--region", choices=sorted(REGIONS), default="dar-es-salaam")
    s.add_argument("--history-hours", type=float, default=4.0)
    s.add_argument("--history-interval", type=int, default=60, help="seconds between history fixes")
    s.add_argument("--history-pace", type=float, default=0.3, help="min seconds between two sends to one device")
    s.add_argument("--transport", choices=["auto", "osmand", "gateway"], default="auto")
    f = sub.add_parser("feed", parents=[common])
    f.add_argument("--minutes", type=float, default=90.0)
    f.add_argument("--interval", type=int, default=30, help="seconds between fixes (keeps the map LIVE)")
    st = sub.add_parser("status", parents=[common])
    st.add_argument("--quick", action="store_true", help="platform-level facts only (no mandate)")
    fh = sub.add_parser("field", parents=[common])
    fh.add_argument("--dry-run", action="store_true", help="print the planned history; no sign-in, nothing sent")
    fh.add_argument(
        "--reset-demo-password",
        action="store_true",
        help="give the seed-created demo supervisor a new generated password first (saved to the credentials file)",
    )
    r = sub.add_parser("retire", parents=[common])
    r.add_argument("--yes", action="store_true")
    a = p.parse_args(argv)
    if a.command == "feed" and not 5 <= a.interval <= 120:
        p.error("--interval must be 5..120 s")
    commands = {"seed": seed, "feed": feed, "field": field_history, "status": status, "retire": retire}
    return int(commands[a.command](a))


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Refuse as refused:
        print(f"[demo] {refused}", file=sys.stderr, flush=True)
        sys.exit(2)
