"""High-level test client: acts as platform owner or tenant users with real signed tokens."""

import uuid
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from tests.support.idp import InMemoryIdp
from tests.support.tokens import TokenFactory

PLATFORM_SUBJECT = "platform-owner-subject"


class Actor:
    def __init__(
        self, api: "Api", subject: str, groups: list[str], tenant_id: str | None = None, email: str = "user@example.com"
    ):
        self.api, self.subject, self.groups, self.tenant_id, self.email = api, subject, groups, tenant_id, email

    def headers(self, idem: bool, tenant: str | None) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api.tokens.mint(self.subject, self.groups, email=self.email)}",
            "X-Correlation-ID": str(uuid.uuid4()),
        }
        if tenant or self.tenant_id:
            h["X-Tenant-ID"] = tenant or self.tenant_id or ""
        if idem:
            h["Idempotency-Key"] = str(uuid.uuid4())
        return h

    def get(self, path: str, tenant: str | None = None, **params: Any) -> Response:
        r: Response = self.api.client.get(path, headers=self.headers(False, tenant), params=params)
        return r

    def post(self, path: str, body: Any = None, tenant: str | None = None, key: str | None = None) -> Response:
        h = self.headers(True, tenant)
        if key:
            h["Idempotency-Key"] = key
        r: Response = self.api.client.post(path, json=body, headers=h)
        return r

    def patch(self, path: str, body: Any) -> Response:
        r: Response = self.api.client.patch(path, json=body, headers=self.headers(True, None))
        return r


class Api:
    def __init__(self, client: TestClient, tokens: TokenFactory, idp: InMemoryIdp, clock: Any):
        self.client, self.tokens, self.idp, self.clock = client, tokens, idp, clock
        self.platform = Actor(self, PLATFORM_SUBJECT, ["/platform/platform-owner"], email="platform@asseta.local")

    def tenant_user(self, email: str, tenant_id: str) -> Actor:
        subject = self.idp.subject_for(email)
        return Actor(self, subject, sorted(self.idp.memberships[subject]), tenant_id, email=email)

    def onboard(
        self,
        name: str,
        *,
        price: str,
        cadence: str = "MONTHLY",
        currency: str = "TZS",
        minimum: int = 1,
        discount: str = "0",
        tax: str = "0",
        start: date | None = None,
        terms_days: int = 14,
        add: str = "PRORATE_DAILY",
        remove: str = "PRORATE_CREDIT",
    ) -> dict[str, Any]:
        email = f"owner@{name.lower().replace(' ', '')}.example.com"
        body = {
            "legal_name": f"{name} Ltd",
            "display_name": name,
            "contact_name": "Owner",
            "contact_email": email,
            "timezone": "Africa/Dar_es_Salaam",
            "currency": currency,
            "owner": {"email": email, "first_name": "Ow", "last_name": "Ner"},
            "subscription": {
                "start_date": (start or self.clock.now.date()).isoformat(),
                "payment_terms_days": terms_days,
                "rate": {
                    "currency": currency,
                    "cadence": cadence,
                    "unit_price": price,
                    "minimum_billable_assets": minimum,
                    "discount_percent": discount,
                    "tax_name": "VAT",
                    "tax_rate_percent": tax,
                    "mid_cycle_add": add,
                    "mid_cycle_remove": remove,
                },
            },
        }
        r = self.platform.post("/api/v1/platform/tenants", body)
        assert r.status_code == 201, r.text
        out: dict[str, Any] = r.json()
        out["owner"] = self.tenant_user(email, out["tenant"]["id"])
        return out

    def activate(self, onboarded: dict[str, Any]) -> None:
        tid, sid = onboarded["tenant"]["id"], onboarded["subscription_id"]
        r = self.platform.post(
            f"/api/v1/platform/tenants/{tid}/verification", {"status": "VERIFIED", "note": "BRELA certificate checked"}
        )
        assert r.status_code == 200, r.text
        r = self.platform.post(
            f"/api/v1/platform/subscriptions/{sid}/transitions",
            {"to_status": "ACTIVE", "effective_date": self.clock.now.date().isoformat(), "reason": "Agreement signed"},
        )
        assert r.status_code == 200, r.text

    def add_machines(self, owner: Actor, n: int, enroll_on: date | None = None, prefix: str = "EXC") -> list[str]:
        ids = []
        for i in range(n):
            r = owner.post("/api/v1/tenant/machines", {"asset_code": f"{prefix}-{i:03d}", "name": f"Machine {i}"})
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
            if enroll_on is not None:
                e = owner.post(
                    "/api/v1/tenant/billing/enrollments",
                    {"machine_id": ids[-1], "effective_from": enroll_on.isoformat()},
                )
                assert e.status_code == 201, e.text
        return ids

    def generate(self, sid: str, as_of: date) -> dict[str, Any]:
        r = self.platform.post(f"/api/v1/platform/subscriptions/{sid}/invoices/generate", {"as_of": as_of.isoformat()})
        assert r.status_code == 200, r.text
        result: dict[str, Any] = r.json()
        return result
