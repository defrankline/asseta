"""Throwaway tenant for the hardening drills: create it through the real platform/tenant APIs, then remove it.

    cd backend
    uv run python ../scripts/drills/drill_tenant.py create [--machines 100]
    uv run python ../scripts/drills/drill_tenant.py purge --dry-run   # report what would be removed (rolls back)
    uv run python ../scripts/drills/drill_tenant.py purge --yes       # remove THIS tenant id only

`create` follows compose_smoke.py / field_e2e_setup.py: a throwaway confidential Keycloak client and platform-owner
user onboard + verify + activate a tenant named "Drill 7E <tag>"; as its owner it creates N machines, enrolls each as
a billable asset, registers one simulated OsmAnd tracker per machine (IMEI-shaped id) under a drill tracker model and
assigns it as primary (effective 3 h ago), plus a customer and a contract (for job events). State, incl. the
throwaway passwords, goes only to .drills/tenant.json (0600, gitignored).

`purge` removes exactly the tenant id recorded in that file with backend/scripts/purge_tenants.py's database and
Keycloak routines (never by name prefix), deletes the throwaway Keycloak users + client and withdraws approval of
the drill tracker model. A dry run is always available and changes nothing.
"""

from __future__ import annotations

import argparse
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import httpx
from drill_common import ENV, KC, Session, expect, guard_local, load_state, now_utc, save_state, sql, state_path

ADMIN = f"{KC}/admin/realms/asseta"


def admin_headers() -> dict[str, str]:
    r = httpx.post(
        f"{KC}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ENV["KEYCLOAK_ADMIN_USER"],
            "password": ENV["KEYCLOAK_ADMIN_PASSWORD"],
        },
        timeout=30,
    )
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def kc_client(h: dict[str, str], client_id: str, secret: str) -> str:
    web = httpx.get(f"{ADMIN}/clients", params={"clientId": "asseta-web"}, headers=h, timeout=30).json()[0]
    httpx.post(
        f"{ADMIN}/clients",
        headers=h,
        json={
            "clientId": client_id,
            "secret": secret,
            "publicClient": False,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": False,
            "protocolMappers": [{k: v for k, v in m.items() if k != "id"} for m in web["protocolMappers"]],
        },
        timeout=30,
    ).raise_for_status()
    return str(httpx.get(f"{ADMIN}/clients", params={"clientId": client_id}, headers=h, timeout=30).json()[0]["id"])


def kc_user(h: dict[str, str], email: str, group: str | None) -> tuple[str, str]:
    """Creates (when `group`) or adopts the user; sets a generated password. Returns (id, password)."""
    if group:
        httpx.post(
            f"{ADMIN}/users",
            headers=h,
            json={
                "username": email,
                "email": email,
                "enabled": True,
                "emailVerified": True,
                "firstName": "Drill",
                "lastName": "User",
            },
            timeout=30,
        ).raise_for_status()
    uid = str(
        httpx.get(f"{ADMIN}/users", params={"email": email, "exact": "true"}, headers=h, timeout=30).json()[0]["id"]
    )
    httpx.put(
        f"{ADMIN}/users/{uid}",
        headers=h,
        json={"requiredActions": [], "emailVerified": True, "firstName": "Drill", "lastName": "User"},
        timeout=30,
    ).raise_for_status()
    pw = "Drill-" + secrets.token_urlsafe(24)
    httpx.put(
        f"{ADMIN}/users/{uid}/reset-password",
        headers=h,
        json={"type": "password", "value": pw, "temporary": False},
        timeout=30,
    ).raise_for_status()
    if group:
        gid = httpx.get(f"{ADMIN}/group-by-path/{group.strip('/')}", headers=h, timeout=30).json()["id"]
        httpx.put(f"{ADMIN}/users/{uid}/groups/{gid}", headers=h, timeout=30).raise_for_status()
    return uid, pw


def create(machines: int) -> None:
    if state_path().exists():
        raise SystemExit(f"a drill tenant already exists ({state_path()}); purge it first")
    guard_local()
    tag = uuid.uuid4().hex[:6]
    h = admin_headers()
    state: dict[str, Any] = {
        "tag": tag,
        "client_id": f"drill-{tag}",
        "client_secret": secrets.token_hex(24),
        "users": {},
        "machines": [],
    }
    state["client_uuid"] = kc_client(h, state["client_id"], state["client_secret"])
    save_state(state)  # from here on, purge can clean up even if creation fails half way
    platform_email = f"drill-platform-{tag}@asseta.local"
    uid, pw = kc_user(h, platform_email, "/platform/platform-owner")
    state["users"]["platform"] = {"email": platform_email, "password": pw, "id": uid}
    save_state(state)
    s = Session(state)
    owner_email = f"drill-owner-{tag}@example.com"
    today = now_utc().date().isoformat()
    created = expect(
        s.call(
            "POST",
            "/platform/tenants",
            who="platform",
            json={
                "legal_name": f"Drill 7E {tag} Ltd",
                "display_name": f"Drill 7E {tag}",
                "contact_name": "Drill Owner",
                "contact_email": owner_email,
                "timezone": "Africa/Dar_es_Salaam",
                "currency": "TZS",
                "owner": {"email": owner_email, "first_name": "Drill", "last_name": "Owner"},
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
        ),
        201,
        "onboard tenant",
    )
    state["tenant_id"] = str(created["tenant"]["id"])
    save_state(state)
    tid, sub = state["tenant_id"], str(created["subscription_id"])
    expect(
        s.call(
            "POST",
            f"/platform/tenants/{tid}/verification",
            who="platform",
            json={"status": "VERIFIED", "note": "Gate 7E drill"},
        ),
        200,
        "verify",
    )
    expect(
        s.call(
            "POST",
            f"/platform/subscriptions/{sub}/transitions",
            who="platform",
            json={"to_status": "ACTIVE", "effective_date": today, "reason": "Gate 7E drill"},
        ),
        200,
        "activate",
    )
    uid, pw = kc_user(h, owner_email, None)
    state["users"]["owner"] = {"email": owner_email, "password": pw, "id": uid}
    model = expect(
        s.call(
            "POST",
            "/platform/tracker-models",
            who="platform",
            json={
                "manufacturer": "Simulated",
                "model": f"Drill-OsmAnd-{tag}",
                "adapter": "TRACCAR",
                "protocol": "osmand",
                "declared_capabilities": ["GNSS", "ACCURACY", "IGNITION"],
            },
        ),
        201,
        "tracker model",
    )
    state["tracker_model_id"] = model["id"]
    save_state(state)
    assign_from = (now_utc() - timedelta(hours=3)).isoformat()

    def one(i: int) -> dict[str, str]:
        m = expect(
            s.call("POST", "/tenant/machines", json={"asset_code": f"DRL-{i:03d}", "name": f"Drill machine {i}"}),
            201,
            f"machine {i}",
        )
        expect(
            s.call("POST", "/tenant/billing/enrollments", json={"machine_id": m["id"], "effective_from": today}),
            201,
            f"enroll {i}",
        )
        device = f"86{tag_digits}{i:04d}"
        tr = expect(
            s.call(
                "POST",
                "/tenant/trackers",
                json={"tracker_model_id": model["id"], "external_id": device, "label": f"Drill {i}"},
            ),
            201,
            f"tracker {i}",
        )
        expect(
            s.call(
                "POST",
                f"/tenant/trackers/{tr['id']}/assign",
                json={"machine_id": m["id"], "effective_from": assign_from},
            ),
            201,
            f"assign {i}",
        )
        return {"machine_id": m["id"], "tracker_id": tr["id"], "device": device}

    tag_digits = str(int(tag, 16) % 10**9).zfill(9)  # 15-digit IMEI-shaped ids: 86 + 9 + 4
    s.token("owner")
    with ThreadPoolExecutor(8) as pool:
        state["machines"] = list(pool.map(one, range(1, machines + 1)))
    cust = expect(
        s.call("POST", "/tenant/customers", json={"code": f"DRL-{tag}", "name": "Drill customer"}), 201, "customer"
    )
    contract = expect(
        s.call(
            "POST",
            "/tenant/contracts",
            json={"customer_id": cust["id"], "contract_number": f"DRL-CT-{tag}", "starts_on": today},
        ),
        201,
        "contract",
    )
    state["customer_id"], state["contract_id"] = cust["id"], contract["id"]
    save_state(state)
    print(f"DRILL TENANT OK tenant={tid} machines={len(state['machines'])} state={state_path()}")


def purge(dry_run: bool) -> None:
    guard_local()
    from purge_tenants import purge_database, purge_keycloak

    state = load_state()
    tid = state.get("tenant_id")
    if tid:
        name = sql("SELECT display_name FROM tenant WHERE id = %s", (tid,))
        if name and not str(name[0][0]).startswith("Drill 7E "):
            raise SystemExit(f"refusing: tenant {tid} is not a drill tenant ({name[0][0]!r})")
    ids = [uuid.UUID(tid)] if tid else []
    counts = purge_database(ENV, ids, dry_run) if ids else {}
    if dry_run:
        print(f"DRY RUN (nothing changed) tenant={tid} rows={sum(counts.values())} detail={counts}")
        return
    groups = purge_keycloak(ENV, ids) if ids else 0
    h = admin_headers()
    s = Session(state)
    if state.get("tracker_model_id") and "platform" in state["users"]:
        m = s.call("GET", f"/platform/tracker-models/{state['tracker_model_id']}", who="platform")
        if m.status_code == 200 and m.json().get("approved", True):
            s.call(
                "POST",
                f"/platform/tracker-models/{state['tracker_model_id']}/deactivate",
                who="platform",
                json={"reason": "Gate 7E drill finished", "version": m.json().get("version", 1)},
            )
    removed = 0
    for u in state["users"].values():
        if httpx.delete(f"{ADMIN}/users/{u['id']}", headers=h, timeout=30).status_code in (204, 404):
            removed += 1
    if state.get("client_uuid"):
        httpx.delete(f"{ADMIN}/clients/{state['client_uuid']}", headers=h, timeout=30)
    state_path().unlink()
    print(
        f"PURGE OK tenant={tid} rows={sum(counts.values())} keycloak_groups={groups} users_removed={removed} "
        f"detail={counts}"
    )


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--machines", type=int, default=100)
    pg = sub.add_parser("purge")
    pg.add_argument("--dry-run", action="store_true")
    pg.add_argument("--yes", action="store_true")
    a = p.parse_args()
    if a.cmd == "create":
        create(a.machines)
    elif a.dry_run:
        purge(True)
    elif a.yes:
        purge(False)
    else:
        raise SystemExit("refusing: pass --dry-run or --yes")


if __name__ == "__main__":
    main()
