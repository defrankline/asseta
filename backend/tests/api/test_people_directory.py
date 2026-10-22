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
