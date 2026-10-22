"""Tenant people directory: display names for record ids, never e-mail, never across tenants."""

from tests.support.api import Api


def test_people_directory_resolves_members_only_without_email(api: Api) -> None:
    a = api.onboard("Names Co", price="1")
    b = api.onboard("Other Co", price="1")
    owner_a, owner_b = a["owner"], b["owner"]
    id_a = owner_a.get("/api/v1/me").json()["user_id"]
    id_b = owner_b.get("/api/v1/me").json()["user_id"]

    r = owner_a.get("/api/v1/tenant/people", ids=f"{id_a},{id_b}")
    assert r.status_code == 200, r.text
    assert r.json() == [{"user_id": id_a, "display_name": owner_a.get("/api/v1/me").json()["display_name"]}]
    assert "@" not in r.text  # display names only

    assert owner_a.get("/api/v1/tenant/people").status_code == 422  # ids are required
    bad = owner_a.get("/api/v1/tenant/people", ids="-" * 36)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_IDS"
    too_many = owner_a.get("/api/v1/tenant/people", ids=",".join([id_a] * 101))
    assert too_many.status_code == 422
    # Tenant boundary: asking tenant B for A's owner resolves nothing.
    assert owner_b.get("/api/v1/tenant/people", ids=id_a).json() == []


def test_people_search_finds_current_members_of_this_tenant_only(api: Api) -> None:
    a = api.onboard("Search Co", price="1")
    b = api.onboard("Search Other", price="1")
    owner_a, owner_b = a["owner"], b["owner"]
    me_a = owner_a.get("/api/v1/me").json()
    needle = me_a["display_name"][:2]

    found = owner_a.get("/api/v1/tenant/people", q=needle.lower()).json()  # case-insensitive
    assert {"user_id": me_a["user_id"], "display_name": me_a["display_name"]} in found
    id_b = owner_b.get("/api/v1/me").json()["user_id"]
    assert id_b not in {p["user_id"] for p in found}  # never another tenant's members
    assert owner_a.get("/api/v1/tenant/people", q="%").json() == []  # wildcards are literal
    both = owner_a.get("/api/v1/tenant/people", q=needle, ids=me_a["user_id"])
    assert both.status_code == 422 and both.json()["error"]["code"] == "INVALID_PEOPLE_QUERY"
