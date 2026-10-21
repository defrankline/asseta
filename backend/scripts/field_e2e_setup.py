"""Live field-sync fixture for the native apps' real sync clients (Gate 4 E2E, scripts/field-e2e.sh).

Usage (from backend/):
  uv run python scripts/field_e2e_setup.py ../.env <outfile>            # create fixture, write outfile (mode 600)
  uv run python scripts/field_e2e_setup.py --cleanup ../.env <outfile>  # delete the Keycloak throwaways, then outfile

Against a running `docker compose` stack: creates a throwaway confidential Keycloak client and platform user (the
compose_smoke.py pattern), onboards + verifies + activates a tenant through the API, and as the tenant owner creates a
machine category, machine, customer, contract, an APPROVED job on that machine, a MANUAL-with-photo opening capture
policy and a SUPERVISOR staff member linked to a throwaway Keycloak supervisor (invited through the tenant access API,
so it lands in `/tenants/<id>/supervisor`) and assigned to the machine. Finally writes the supervisor's access token
and the fixture ids as JSON to <outfile>. Secrets are only ever written to that file, never printed.
"""

import json
import os
import secrets
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

TIMEOUT = 30.0


def read_env(path: str) -> dict[str, str]:
    return dict(
        line.split("=", 1) for line in Path(path).read_text().splitlines() if "=" in line and not line.startswith("#")
    )


class Stack:
    def __init__(self, env: dict[str, str]):
        self.env = env
        self.kc = env.get("ASSETA_PUBLIC_KEYCLOAK_URL", "http://localhost:8080")
        self.api_base = f"http://localhost:{env.get('ASSETA_API_PORT', '8000')}"
        self.api = f"{self.api_base}/api/v1"
        self.admin = f"{self.kc}/admin/realms/asseta"
        self.token_url = f"{self.kc}/realms/asseta/protocol/openid-connect/token"

    def admin_headers(self) -> dict[str, str]:
        r = httpx.post(
            f"{self.kc}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.env["KEYCLOAK_ADMIN_USER"],
                "password": self.env["KEYCLOAK_ADMIN_PASSWORD"],
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}


def check(r: httpx.Response, status: int, what: str) -> dict[str, Any]:
    """Raises with the server's error code (never the request, which may carry a token)."""
    if r.status_code != status:
        try:
            err = r.json().get("error", {})
            code = f"{err.get('code', '')} {err.get('message', '')}"
        except ValueError:
            code = ""
        raise RuntimeError(f"{what}: HTTP {r.status_code} {code}".strip())
    body: dict[str, Any] = r.json() if r.content else {}
    return body


class Keycloak:
    """Throwaway client + users, recorded so --cleanup can remove them."""

    def __init__(self, stack: Stack):
        self.s = stack
        self.h = stack.admin_headers()
        self.client_id = f"field-e2e-{uuid.uuid4().hex[:6]}"
        self.client_secret = secrets.token_hex(24)
        self.client_uuid: str | None = None
        self.user_ids: list[str] = []
        self.passwords: dict[str, str] = {}

    def create_client(self) -> None:
        web = httpx.get(
            f"{self.s.admin}/clients", params={"clientId": "asseta-web"}, headers=self.h, timeout=TIMEOUT
        ).json()[0]
        httpx.post(
            f"{self.s.admin}/clients",
            headers=self.h,
            json={
                "clientId": self.client_id,
                "secret": self.client_secret,
                "publicClient": False,
                "directAccessGrantsEnabled": True,
                "standardFlowEnabled": False,
                "protocolMappers": [{k: v for k, v in m.items() if k != "id"} for m in web["protocolMappers"]],
            },
            timeout=TIMEOUT,
        ).raise_for_status()
        found = httpx.get(
            f"{self.s.admin}/clients", params={"clientId": self.client_id}, headers=self.h, timeout=TIMEOUT
        ).json()
        self.client_uuid = str(found[0]["id"])

    def user(self, email: str, group: str | None) -> str:
        """Creates (when `group`) or adopts the user with `email`, sets a generated password; returns its id."""
        if group:
            httpx.post(
                f"{self.s.admin}/users",
                headers=self.h,
                json={
                    "username": email,
                    "email": email,
                    "enabled": True,
                    "emailVerified": True,
                    "firstName": "Field",
                    "lastName": "E2E",
                },
                timeout=TIMEOUT,
            ).raise_for_status()
        uid = str(
            httpx.get(
                f"{self.s.admin}/users", params={"email": email, "exact": "true"}, headers=self.h, timeout=TIMEOUT
            ).json()[0]["id"]
        )
        self.user_ids.append(uid)
        httpx.put(
            f"{self.s.admin}/users/{uid}",
            headers=self.h,
            json={"requiredActions": [], "emailVerified": True, "firstName": "Field", "lastName": "E2E"},
            timeout=TIMEOUT,
        ).raise_for_status()
        pw = "Fe2e-" + secrets.token_urlsafe(24)
        httpx.put(
            f"{self.s.admin}/users/{uid}/reset-password",
            headers=self.h,
            json={"type": "password", "value": pw, "temporary": False},
            timeout=TIMEOUT,
        ).raise_for_status()
        if group:
            gid = httpx.get(f"{self.s.admin}/group-by-path/{group.strip('/')}", headers=self.h, timeout=TIMEOUT).json()[
                "id"
            ]
            httpx.put(f"{self.s.admin}/users/{uid}/groups/{gid}", headers=self.h, timeout=TIMEOUT).raise_for_status()
        self.passwords[email] = pw
        return uid

    def login(self, email: str) -> dict[str, Any]:
        r = httpx.post(
            self.s.token_url,
            data={
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": email,
                "password": self.passwords[email],
                "scope": "openid",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        out: dict[str, Any] = r.json()
        return out

    def bearer(self, email: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.login(email)['access_token']}"}

    def cleanup_info(self) -> dict[str, Any]:
        return {"client_uuid": self.client_uuid, "user_ids": list(self.user_ids)}


def cleanup(stack: Stack, info: dict[str, Any]) -> int:
    h = stack.admin_headers()
    removed = 0
    for uid in info.get("user_ids", []):
        if httpx.delete(f"{stack.admin}/users/{uid}", headers=h, timeout=TIMEOUT).status_code in (204, 404):
            removed += 1
    if info.get("client_uuid"):
        httpx.delete(f"{stack.admin}/clients/{info['client_uuid']}", headers=h, timeout=TIMEOUT)
    return removed


class Owner:
    """Tenant-owner API calls (fresh idempotency key per mutation)."""

    def __init__(self, stack: Stack, kc: Keycloak, email: str, tenant_id: str):
        self.s, self.kc, self.email, self.tenant_id = stack, kc, email, tenant_id

    def _h(self) -> dict[str, str]:
        return {**self.kc.bearer(self.email), "X-Tenant-ID": self.tenant_id, "Idempotency-Key": str(uuid.uuid4())}

    def post(self, path: str, body: Any, what: str, status: int = 201) -> dict[str, Any]:
        return check(httpx.post(f"{self.s.api}{path}", headers=self._h(), json=body, timeout=TIMEOUT), status, what)


def onboard(stack: Stack, kc: Keycloak, tag: str) -> tuple[str, str]:
    """Platform owner onboards, verifies and activates a tenant. Returns (tenant_id, owner_email)."""
    platform_email = f"field-e2e-platform-{tag}@asseta.local"
    kc.user(platform_email, "/platform/platform-owner")
    owner_email = f"field-e2e-owner-{tag}@example.com"
    today = datetime.now(UTC).date().isoformat()

    def ph() -> dict[str, str]:
        return {**kc.bearer(platform_email), "Idempotency-Key": str(uuid.uuid4())}

    created = check(
        httpx.post(
            f"{stack.api}/platform/tenants",
            headers=ph(),
            json={
                "legal_name": f"Field E2E {tag} Ltd",
                "display_name": f"Field E2E {tag}",
                "contact_name": "Field Owner",
                "contact_email": owner_email,
                "timezone": "Africa/Dar_es_Salaam",
                "currency": "TZS",
                "owner": {"email": owner_email, "first_name": "Field", "last_name": "Owner"},
                "subscription": {
                    "start_date": today,
                    "rate": {
                        "currency": "TZS",
                        "cadence": "MONTHLY",
                        "unit_price": "1000",
                        "minimum_billable_assets": 1,
                    },
                },
            },
            timeout=TIMEOUT,
        ),
        201,
        "onboard tenant",
    )
    tenant_id, sub_id = str(created["tenant"]["id"]), str(created["subscription_id"])
    check(
        httpx.post(
            f"{stack.api}/platform/tenants/{tenant_id}/verification",
            headers=ph(),
            json={"status": "VERIFIED", "note": "Field E2E fixture"},
            timeout=TIMEOUT,
        ),
        200,
        "verify tenant",
    )
    check(
        httpx.post(
            f"{stack.api}/platform/subscriptions/{sub_id}/transitions",
            headers=ph(),
            json={"to_status": "ACTIVE", "effective_date": today, "reason": "Field E2E fixture"},
            timeout=TIMEOUT,
        ),
        200,
        "activate subscription",
    )
    kc.user(owner_email, None)  # created by onboarding; adopt it with a generated password
    return tenant_id, owner_email


def build_fixture(stack: Stack, kc: Keycloak) -> dict[str, Any]:
    tag = uuid.uuid4().hex[:6]
    tenant_id, owner_email = onboard(stack, kc, tag)
    o = Owner(stack, kc, owner_email, tenant_id)
    now = datetime.now(UTC) - timedelta(minutes=5)
    today = now.date().isoformat()
    category = o.post("/tenant/machine-categories", {"name": "Excavators"}, "create category")["id"]
    machine = o.post(
        "/tenant/machines",
        {
            "asset_code": f"FE2E-{tag}",
            "name": "Field E2E excavator",
            "category_id": category,
            "meter_decimal_places": 1,
        },
        "create machine",
    )["id"]
    o.post("/tenant/billing/enrollments", {"machine_id": machine, "effective_from": today}, "enroll machine")
    customer = o.post("/tenant/customers", {"code": f"C-{tag}", "name": "Road Builders Ltd"}, "create customer")["id"]
    contract = o.post(
        "/tenant/contracts",
        {"customer_id": customer, "contract_number": f"CT-{tag}", "starts_on": today},
        "create contract",
    )["id"]
    job = o.post(
        "/tenant/jobs",
        {
            "contract_id": contract,
            "job_number": f"J-{tag}",
            "machine_id": machine,
            "planned_start": now.isoformat(),
            "hourly_rate": "85000",
        },
        "create job",
    )["id"]
    for action in ("SUBMIT", "APPROVE"):
        o.post(f"/tenant/jobs/{job}/transitions", {"action": action}, f"job {action}", status=200)
    # Opening readings are MANUAL with a mandatory photo (no camera/OCR in a headless test); the clients still read
    # the mode from the synced policy snapshot rather than assuming it.
    o.post(
        "/tenant/policies/METER_CAPTURE/versions",
        {
            "scope": "TENANT",
            "values": {"opening_mode": "MANUAL", "closing_mode": "MANUAL", "manual_photo_required": True},
            "reason": "Field E2E capture rules",
        },
        "set capture policy",
    )
    sup_email = f"field-e2e-sup-{tag}@example.com"
    o.post(
        "/tenant/access/members",
        {"email": sup_email, "first_name": "Field", "last_name": "Supervisor", "role_key": "supervisor"},
        "invite supervisor",
    )
    sup_subject = kc.user(sup_email, None)  # created by the invite (in the tenant supervisor group)
    staff = o.post(
        "/tenant/staff",
        {"full_name": "Field E2E Supervisor", "kind": "SUPERVISOR", "keycloak_subject": sup_subject},
        "create staff",
    )["id"]
    o.post(
        f"/tenant/machines/{machine}/assignments",
        {"staff_member_id": staff, "role": "SUPERVISOR", "effective_from": now.isoformat()},
        "assign supervisor",
    )
    finance = finance_fixture(o, tag, staff)  # Gate 5 field finance (additive; extra keys only)
    return {
        "api_base": stack.api_base,
        "tenant_id": tenant_id,
        "job_id": job,
        "machine_id": machine,
        "supervisor_email": sup_email,
        "customer_id": customer,
        **finance,
    }


def finance_fixture(o: Owner, tag: str, staff: str) -> dict[str, Any]:
    """An active expense category and a cash float for the supervisor (so collections, handovers and custody
    expenses have a balance to move). The tenant keeps the default EXPENSE_CAPTURE policy (receipt and GPS fix
    required, every expense needs approval). Each run uses a fresh tenant, so this is idempotent per fixture."""
    category = o.post("/tenant/expense-categories", {"code": f"FE2E{tag}"[:32], "name": "Field E2E parts"}, "expense cat")
    float_amount = "500000"
    o.post(
        "/tenant/cash/floats",
        {"staff_member_id": staff, "amount": float_amount, "reference": f"FLOAT-{tag}", "note": "Field E2E float"},
        "issue cash float",
    )
    return {"expense_category_id": category["id"], "staff_member_id": staff, "cash_float": float_amount}


def supervisor_token(kc: Keycloak, email: str) -> dict[str, Any]:
    tok = kc.login(email)
    expires = datetime.now(UTC) + timedelta(seconds=int(tok["expires_in"]))
    return {"access_token": tok["access_token"], "token_expires_at": expires.isoformat(timespec="milliseconds")}


def write_private(path: str, data: dict[str, Any]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--cleanup":
        stack, out = Stack(read_env(argv[1])), argv[2]
        if not Path(out).exists():
            print("FIELD E2E CLEANUP: nothing to clean")
            return 0
        info = json.loads(Path(out).read_text()).get("keycloak_cleanup", {})
        removed = cleanup(stack, info)
        Path(out).unlink()
        print(f"FIELD E2E CLEANUP OK users_removed={removed} client_removed={bool(info.get('client_uuid'))}")
        return 0
    stack, out = Stack(read_env(argv[0])), argv[1]
    kc = Keycloak(stack)
    done = False
    try:
        kc.create_client()
        fixture = build_fixture(stack, kc)
        token = supervisor_token(kc, fixture.pop("supervisor_email"))
        write_private(out, {**fixture, **token, "keycloak_cleanup": kc.cleanup_info()})
        done = True
        print(f"FIELD E2E SETUP OK tenant={fixture['tenant_id']} job={fixture['job_id']} at={time.strftime('%X')}")
        return 0
    finally:
        if not done:
            cleanup(stack, kc.cleanup_info())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
