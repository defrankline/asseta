"""Text search (`q`) on list endpoints: case-insensitive substring, LIKE wildcards in the user text taken
literally, blank q ignored, and combined (AND) with each endpoint's existing filters and paging."""

from typing import Any

from tests.support.api import PLATFORM_SUBJECT, Actor, Api

OWNER_PATH = "/platform/platform-owner"


def owner(api: Api, name: str = "Search Co") -> Actor:
    o: Actor = api.onboard(name, price="1")["owner"]
    return o


def created(r: Any) -> dict[str, Any]:
    assert r.status_code == 201, r.text
    return dict(r.json())


def test_contracts_q_matches_number_or_reference_and_combines_with_customer_and_paging(api: Api) -> None:
    o = owner(api)
    c1 = created(o.post("/api/v1/tenant/customers", {"code": "C1", "name": "Road Builders"}))["id"]
    c2 = created(o.post("/api/v1/tenant/customers", {"code": "C2", "name": "Dam Makers"}))["id"]
    start = api.clock.now.isoformat()
    for cust, number, ref in ((c1, "CT-001", "Bridge works"), (c2, "CT-002", "Bridge repairs"), (c1, "CT-003", "Road")):
        created(
            o.post(
                "/api/v1/tenant/contracts",
                {"customer_id": cust, "contract_number": number, "starts_on": start, "reference": ref},
            )
        )
    body = o.get("/api/v1/tenant/contracts", q="bRIDGE").json()
    assert body["total"] == 2 and {c["contract_number"] for c in body["items"]} == {"CT-001", "CT-002"}
    body = o.get("/api/v1/tenant/contracts", q="bridge", customer_id=c1).json()
    assert body["total"] == 1 and [c["contract_number"] for c in body["items"]] == ["CT-001"]
    body = o.get("/api/v1/tenant/contracts", q="ct-00", page_size=1).json()
    assert body["total"] == 3 and len(body["items"]) == 1
    assert o.get("/api/v1/tenant/contracts", q="   ").json()["total"] == 3  # blank q = no filter


def test_machine_categories_q_on_name(api: Api) -> None:
    o = owner(api)
    for name in ("Excavators", "Wheel Loaders", "Mini Excavators"):
        created(o.post("/api/v1/tenant/machine-categories", {"name": name}))
    rows = o.get("/api/v1/tenant/machine-categories", q="eXCAV").json()
    assert [c["name"] for c in rows] == ["Excavators", "Mini Excavators"]
    assert len(o.get("/api/v1/tenant/machine-categories").json()) == 3


def test_operating_areas_q_on_code_or_name(api: Api) -> None:
    o = owner(api)
    created(o.post("/api/v1/tenant/operating-areas", {"code": "DSM", "name": "Dar es Salaam"}))
    created(o.post("/api/v1/tenant/operating-areas", {"code": "ARU", "name": "Arusha"}))
    assert [a["code"] for a in o.get("/api/v1/tenant/operating-areas", q="salAAM").json()] == ["DSM"]
    assert [a["code"] for a in o.get("/api/v1/tenant/operating-areas", q="aru").json()] == ["ARU"]


def test_like_wildcards_in_q_are_literal(api: Api) -> None:
    o = owner(api)
    for name in ("100% Electric", "1000 Electric"):
        created(o.post("/api/v1/tenant/machine-categories", {"name": name}))
    assert [c["name"] for c in o.get("/api/v1/tenant/machine-categories", q="0%").json()] == ["100% Electric"]
    assert [c["name"] for c in o.get("/api/v1/tenant/machine-categories", q="%").json()] == ["100% Electric"]
    created(o.post("/api/v1/tenant/operating-areas", {"code": "A_1", "name": "Zone one"}))
    created(o.post("/api/v1/tenant/operating-areas", {"code": "AB1", "name": "Zone two"}))
    created(o.post("/api/v1/tenant/operating-areas", {"code": "BS1", "name": "Back\\slash"}))
    assert [a["code"] for a in o.get("/api/v1/tenant/operating-areas", q="a_1").json()] == ["A_1"]
    assert [a["code"] for a in o.get("/api/v1/tenant/operating-areas", q="k\\s").json()] == ["BS1"]
    # Existing searches use the same escaping (listMachines).
    created(o.post("/api/v1/tenant/machines", {"asset_code": "EX_1", "name": "CAT 320"}))
    created(o.post("/api/v1/tenant/machines", {"asset_code": "EXX1", "name": "CAT 336"}))
    assert [m["asset_code"] for m in o.get("/api/v1/tenant/machines", q="x_1").json()["items"]] == ["EX_1"]


def test_tracker_models_q_on_manufacturer_or_model(api: Api) -> None:
    for manufacturer, model in (("Teltonika", "FMB920"), ("Queclink", "GV300"), ("Teltonika", "FMC130")):
        created(
            api.platform.post(
                "/api/v1/platform/tracker-models",
                {
                    "manufacturer": manufacturer,
                    "model": model,
                    "adapter": "TRACCAR",
                    "protocol": "teltonika",
                    "declared_capabilities": ["GNSS"],
                },
            )
        )
    o = owner(api)
    rows = o.get("/api/v1/tenant/tracker-models", q="TELTON").json()
    assert [(r["manufacturer"], r["model"]) for r in rows] == [("Teltonika", "FMB920"), ("Teltonika", "FMC130")]
    assert [r["model"] for r in o.get("/api/v1/tenant/tracker-models", q="gv3").json()] == ["GV300"]


def test_job_sites_q_on_code_or_name(api: Api) -> None:
    o = owner(api)
    for code, name in (("KIG", "Kigamboni Bridge"), ("MOR", "Morogoro Quarry")):
        body = {"code": code, "name": name, "center": {"type": "Point", "coordinates": [39.28, -6.82]}}
        created(o.post("/api/v1/tenant/job-sites", body))
    assert [s["code"] for s in o.get("/api/v1/tenant/job-sites", q="qUARRY").json()] == ["MOR"]
    assert [s["code"] for s in o.get("/api/v1/tenant/job-sites", q="kig").json()] == ["KIG"]
    assert len(o.get("/api/v1/tenant/job-sites").json()) == 2


def test_platform_staff_q_on_display_name_or_email(api: Api) -> None:
    for subject, email in ((PLATFORM_SUBJECT, "platform@asseta.local"), ("s-asha", "asha@asseta.local")):
        api.idp.users[subject] = email
        api.idp.memberships.setdefault(subject, set()).add(OWNER_PATH)
    owner(api)  # ensures the platform role groups exist in the IdP
    rows = api.platform.get("/api/v1/platform/mandates/staff", q="ASHA").json()
    assert [s["email"] for s in rows] == ["asha@asseta.local"]
    everyone = api.platform.get("/api/v1/platform/mandates/staff", q=" ").json()
    assert {s["email"] for s in everyone} == {"asha@asseta.local", "platform@asseta.local"}


def test_mandate_roles_q_on_role_key(api: Api) -> None:
    api.idp.users[PLATFORM_SUBJECT] = "platform@asseta.local"
    api.idp.memberships.setdefault(PLATFORM_SUBJECT, set()).add(OWNER_PATH)
    tid = api.onboard("Roles Co", price="1")["tenant"]["id"]
    m = created(
        api.platform.post(
            "/api/v1/platform/mandates",
            {
                "tenant_id": tid,
                "scope": "FULL",
                "starts_on": api.clock.now.date().isoformat(),
                "consent_reference": "MSA-1",
            },
        )
    )
    roles = api.platform.get(f"/api/v1/platform/mandates/{m['id']}/roles", q="oPER").json()
    assert [r["key"] for r in roles] == ["operator"]
    assert len(api.platform.get(f"/api/v1/platform/mandates/{m['id']}/roles").json()) > 1
