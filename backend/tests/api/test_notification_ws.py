"""DEC-022 WebSocket gateway (auth required, token never in the URL, wrong tenant / ended mandate refused, receives
notifications published through the broker, re-auth) plus RLS on notification and wallet tables."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from starlette.websockets import WebSocketDisconnect

from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.main import create_app
from asseta.modules.identity.tokens import OidcTokenVerifier
from asseta.modules.notification.processing import process_event
from asseta.modules.notification.realtime import InMemoryBroker, entity_channel, user_channel
from asseta.modules.notification.rules import DomainEvent
from tests.conftest import MutableClock
from tests.support.api import Api
from tests.support.idp import InMemoryIdp, InMemoryObjectStore
from tests.support.notify import member, user_id
from tests.support.tokens import AUDIENCE, ISSUER, StaticKeyProvider, TokenFactory

WS = "/api/v1/ws"


@pytest.fixture
def broker() -> InMemoryBroker:
    return InMemoryBroker()


@pytest.fixture
def client(tokens: TokenFactory, idp: InMemoryIdp, clock: MutableClock, broker: InMemoryBroker) -> Iterator[TestClient]:
    """Same app as the shared fixture, with an in-process broker standing in for Redis pub/sub."""
    verifier = OidcTokenVerifier(StaticKeyProvider(tokens.public_key), ISSUER, AUDIENCE)
    app = create_app(token_verifier=verifier, idp_admin=idp, object_store=InMemoryObjectStore(), realtime=broker)
    app.state.clock = clock
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def closed_with(ws: Any) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    return int(exc.value.code)


def test_auth_required_and_bad_tokens_refused(api: Api) -> None:
    t = api.onboard("Ws Co", price="1")
    with api.client.websocket_connect(WS) as ws:
        ws.send_json({"type": "ping"})
        msg = ws.receive_json()
        assert msg == {
            "type": "auth_error",
            "payload": {"code": "AUTH_REQUIRED", "message": "First message must be auth"},
        }
        assert closed_with(ws) == 4401
    forged = api.tokens.mint("x", [], key=TokenFactory().private_key)
    with api.client.websocket_connect(WS) as ws:
        ws.send_json({"type": "auth", "token": forged, "tenant_id": t["tenant"]["id"]})
        assert ws.receive_json()["payload"]["code"] == "NOT_AUTHENTICATED"
        assert closed_with(ws) == 4401


def test_wrong_tenant_and_platform_context_refused(api: Api) -> None:
    a = api.onboard("Ws A", price="1")
    b = api.onboard("Ws B", price="1")
    owner = a["owner"]
    token = api.tokens.mint(owner.subject, owner.groups, email=owner.email)
    with api.client.websocket_connect(WS) as ws:
        ws.send_json({"type": "auth", "token": token, "tenant_id": b["tenant"]["id"]})
        assert ws.receive_json()["payload"]["code"] == "TENANT_ACCESS_DENIED"
        assert closed_with(ws) == 4403
    with api.client.websocket_connect(WS) as ws:  # a tenant user is not platform staff
        ws.send_json({"type": "auth", "token": token, "tenant_id": None})
        assert ws.receive_json()["payload"]["code"] == "PLATFORM_REQUIRED"
        assert closed_with(ws) == 4403
    # Platform staff without a mandate are refused in a client tenant, like REST.
    sneaky = api.tokens.mint(
        "platform-owner-subject", ["/platform/platform-owner", f"/tenants/{a['tenant']['id']}/owner"]
    )
    with api.client.websocket_connect(WS) as ws:
        ws.send_json({"type": "auth", "token": sneaky, "tenant_id": a["tenant"]["id"]})
        assert ws.receive_json()["payload"]["code"] == "MANDATE_REQUIRED"


def test_receives_notifications_via_broker_heartbeat_and_reauth(api: Api, broker: InMemoryBroker) -> None:
    t = api.onboard("Ws Live", price="1")
    tid = t["tenant"]["id"]
    acct = member(api, tid, "accountant", "ws-acct")
    token = api.tokens.mint(acct.subject, acct.groups, email=acct.email)
    # Token in Sec-WebSocket-Protocol (never in the URL); context chosen by the first message.
    with api.client.websocket_connect(WS, subprotocols=["asseta.v1", f"bearer.{token}"]) as ws:
        ws.send_json({"type": "subscribe", "scope": {"kind": "tenant", "tenantId": tid}})
        ok = ws.receive_json()
        assert ok["type"] == "auth_ok" and ok["payload"]["tenant_id"] == tid and ok["payload"]["unread_count"] == 0
        uid = user_id(acct.subject)
        assert broker.subscribers(user_channel(uid, tid)) == 1 and broker.subscribers(entity_channel(tid)) == 1
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        # A real event through the pipeline, published (after commit) to the user's channel.
        payload = {
            "payment_id": str(uuid.uuid4()),
            "customer_id": str(uuid.uuid4()),
            "amount": "5000",
            "currency": "TZS",
            "method": "CASH",
        }
        event = DomainEvent(uuid.uuid4(), "CustomerPaymentRecorded", uuid.UUID(tid), payload)
        process_event(event, get_sessionmaker(), api.clock, broker)
        pushed = ws.receive_json()
        assert pushed["type"] == "notification" and pushed["payload"]["type"] == "CUSTOMER_PAYMENT_TO_VERIFY"
        assert ws.receive_json() == {"type": "unread_count", "payload": {"count": 1}}
        assert ws.receive_json()["type"] == "entity.changed"
        # Token refresh on the open socket keeps the subscription; another user's token is refused.
        ws.send_json({"type": "auth", "token": api.tokens.mint(acct.subject, acct.groups, email=acct.email)})
        assert ws.receive_json()["type"] == "auth_ok"
        intruder = api.tokens.mint(t["owner"].subject, t["owner"].groups)
        ws.send_json({"type": "auth", "token": intruder})
        assert ws.receive_json()["payload"]["code"] == "SUBJECT_CHANGED"
        assert closed_with(ws) == 4401
    assert broker.subscribers(user_channel(uid, tid)) == 0  # cleaned up on close


def test_rls_confines_notifications_and_wallet(api: Api) -> None:
    t = api.onboard("Rls Co", price="1")
    tid = t["tenant"]["id"]
    a = member(api, tid, "accountant", "rls-a")
    b = member(api, tid, "accountant", "rls-b")
    payload = {
        "payment_id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "amount": "1",
        "currency": "TZS",
        "method": "CASH",
    }
    process_event(
        DomainEvent(uuid.uuid4(), "CustomerPaymentRecorded", uuid.UUID(tid), payload), get_sessionmaker(), api.clock
    )
    engine = create_engine(get_settings().database_url)  # the application role, RLS genuinely applies
    with engine.begin() as conn:
        conn.execute(
            text(
                "SELECT set_config('app.scope', 'tenant', true), set_config('app.tenant_id', :t, true),"
                " set_config('app.actor_id', :u, true)"
            ),
            {"t": tid, "u": str(user_id(a.subject))},
        )
        mine = conn.execute(text("SELECT DISTINCT recipient_user_id FROM notification")).scalars().all()
        assert mine == [user_id(a.subject)]
        assert user_id(b.subject) not in mine
        with pytest.raises(Exception, match="row-level security"):
            conn.execute(
                text(
                    "INSERT INTO sms_wallet_entry (id, tenant_id, entry_type, credits, balance_after, reference_type,"
                    " reference_id, created_at) VALUES (gen_random_uuid(), :t, 'BUNDLE_CREDIT', 1000, 1000, 'x',"
                    " gen_random_uuid(), now())"
                ),
                {"t": tid},
            )
    with engine.begin() as conn:  # platform scope sees no tenant inbox rows
        conn.execute(
            text("SELECT set_config('app.scope', 'platform', true), set_config('app.actor_id', :u, true)"),
            {"u": str(user_id(a.subject))},
        )
        assert conn.execute(text("SELECT count(*) FROM notification")).scalar_one() == 0
    engine.dispose()


NEW_TENANT_TABLES = [
    "notification",
    "notification_preference",
    "sms_delivery",
    "sms_wallet_entry",
    "platform_line_allocation",
    "platform_line_fulfilment",
    "platform_product",
    "notification_profile",
]


@pytest.mark.parametrize("table", NEW_TENANT_TABLES)
def test_force_rls_on_new_tables(table: str) -> None:
    engine = create_engine(get_settings().migration_database_url)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :t"), {"t": table}
        ).one()
    engine.dispose()
    assert tuple(row) == (True, True)
