"""Drill (d): restart the API and every worker under activity; WebSocket clients must reconnect.

    cd backend && uv run python ../scripts/drills/restart_under_load.py

Background activity (drill_activity.py) runs throughout, plus a scripted WebSocket client (protocol asseta.v1,
first-message auth as the drill tenant owner) that reconnects with 1 s backoff like the web console. Each service is
restarted with `docker compose restart` (SIGTERM, graceful); the timeline worker is additionally killed with SIGKILL
(crash mid-stream: offsets are committed only after the replay commits, so redelivery must be harmless).
Measured per service: restart duration, API health recovery, WebSocket reconnect time, live `entity.changed`
messages resuming after the notification worker restart. At the end: exactly-once verification of every
acknowledged effect, outbox empty, consumer lag 0, all services up.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from drill_activity import Activity, verify_effects
from drill_common import (
    API_BASE,
    Evidence,
    Session,
    compose,
    guard_local,
    lags,
    load_state,
    outbox_pending,
    readiness,
    ready_summary,
    wait_until,
)
from websockets.sync.client import connect

WS_URL = API_BASE.replace("http://", "ws://") + "/api/v1/ws"
SERVICES = [
    "api",
    "outbox-relay",
    "timeline-worker",
    "notification-worker",
    "intelligence-worker",
    "connectivity-worker",
    "notification-scheduler",
    "billing-scheduler",
]


class WsClient(threading.Thread):
    def __init__(self, session: Session, tenant_id: str):
        super().__init__(daemon=True)
        self.session, self.tenant_id = session, tenant_id
        self.stop_flag = threading.Event()
        self.connected = threading.Event()
        self.auth_ok: list[float] = []
        self.disconnects: list[float] = []
        self.messages: list[tuple[float, str]] = []

    def run(self) -> None:
        while not self.stop_flag.is_set():
            try:
                with connect(WS_URL, subprotocols=["asseta.v1"], open_timeout=5) as ws:  # type: ignore[list-item]
                    ws.send(
                        json.dumps({"type": "auth", "token": self.session.token("owner"), "tenant_id": self.tenant_id})
                    )
                    while not self.stop_flag.is_set():
                        try:
                            raw = ws.recv(timeout=1)
                        except TimeoutError:
                            continue
                        msg: dict[str, Any] = json.loads(raw)
                        kind = str(msg.get("type"))
                        if kind == "auth_ok":
                            self.auth_ok.append(time.time())
                            self.connected.set()
                        elif kind == "ping":
                            ws.send(json.dumps({"type": "pong"}))
                        else:
                            self.messages.append((time.time(), kind))
            except Exception:  # noqa: BLE001 - server gone: reconnect like the console does
                pass
            if self.connected.is_set():
                self.disconnects.append(time.time())
                self.connected.clear()
            time.sleep(1)

    def reconnect_after(self, t: float) -> float | None:
        later = [x for x in self.auth_ok if x > t]
        return later[0] - t if later else None

    def messages_after(self, t: float) -> int:
        return sum(1 for ts, kind in self.messages if ts > t and kind == "entity.changed")


def main() -> None:
    guard_local()
    state = load_state()
    tid = state["tenant_id"]
    ev = Evidence("restart-under-load", "API and worker restarts under activity, WebSocket reconnect")
    ev.say(f"Throwaway tenant `{tid}`; activity = 1 position / 0.5 s + job create+submit / 2 s; 1 WebSocket client.")
    ev.say("")
    act = Activity(state)
    ws = WsClient(Session(state), tid)
    act.start()
    ws.start()
    ws.connected.wait(30)
    ev.check("WebSocket client authenticated (auth_ok)", ws.connected.is_set(), "")
    time.sleep(10)
    rows = []
    for svc in SERVICES + ["timeline-worker (SIGKILL)"]:
        name = svc.split(" ")[0]
        t0, t0_wall = time.monotonic(), time.time()
        if "SIGKILL" in svc:
            compose("kill", "-s", "SIGKILL", name, capture=True)
            compose("start", name, capture=True)
        else:
            compose("restart", name, capture=True)
        restart_s = time.monotonic() - t0
        health = wait_until(lambda: readiness().get("status") == "ok", 120, 0.5) if name == "api" else None
        time.sleep(15)  # let activity flow through the restarted component
        ps = compose("ps", name, "--format", "{{.Status}}", capture=True).stdout.strip()
        reconnect = ws.reconnect_after(t0_wall) if name == "api" else None
        live_msgs = ws.messages_after(t0_wall + restart_s)
        rows.append(
            [
                svc,
                f"{restart_s:.1f}",
                "-" if health is None else f"{health:.1f}",
                "-" if name != "api" else (f"{reconnect:.1f}" if reconnect else "NO"),
                live_msgs,
                ps,
            ]
        )
        ev.check(f"{svc}: running after restart", ps.startswith("Up"), ps)
        if name == "api":
            ev.check("api: healthy again", health is not None, f"{health}")
            ev.check("WebSocket client reconnected after api restart", reconnect is not None, f"{reconnect}")
        if name == "notification-worker":
            ev.check(
                "live entity.changed messages resume after notification-worker restart",
                live_msgs > 0,
                f"{live_msgs} in 15 s",
            )
    ev.table(
        [
            "service",
            "restart (s)",
            "API ready after (s)",
            "WS reconnect (s)",
            "entity.changed msgs in next 15 s",
            "status",
        ],
        rows,
    )
    act.stop()
    t_settle = wait_until(lambda: all((v or 0) == 0 for v in lags().values()) and outbox_pending(tid) == 0, 900, 3.0)
    ws.stop_flag.set()
    ws.join(timeout=10)
    api_fail = [f for f in act.failures]
    ev.say(f"* Activity: {act.summary()}")
    ev.say(
        f"* Activity call failures (expected only while the API process restarts): {len(api_fail)}; "
        f"WebSocket disconnects {len(ws.disconnects)}, auth_ok {len(ws.auth_ok)}, "
        f"entity.changed received {sum(1 for _, k in ws.messages if k == 'entity.changed')}"
    )
    ev.check("outbox drained and consumer lag 0 after all restarts", t_settle is not None, f"{t_settle} s; {lags()}")
    eff = verify_effects(state, act)
    ev.say(f"* Effects: {eff}")
    ev.check(
        "no acknowledged position lost / duplicated",
        eff["positions_lost"] == 0 and eff["positions_duplicated"] == 0,
        f"lost {eff['positions_lost']}, dup {eff['positions_duplicated']}",
    )
    ev.check(
        "no lost outbox events: every submitted job produced its event and notification",
        eff["job_events"] == eff["jobs_submitted"] and eff["job_events_without_notification"] == 0,
        f"{eff['job_events']}/{eff['jobs_submitted']} events, {eff['job_events_without_notification']} "
        "without notification",
    )
    ev.check("no duplicate notifications", eff["duplicate_notifications"] == 0, str(eff["duplicate_notifications"]))
    ev.check("final readiness ok", readiness().get("status") == "ok", ready_summary(readiness()))
    up = compose("ps", "--format", "{{.Service}} {{.Status}}", capture=True).stdout.splitlines()
    ev.check("all compose services up", all(" Up" in line for line in up), "; ".join(up))
    ev.write(
        not_simulated=[
            "Multiple API replicas behind a load balancer (zero-downtime rolling restart); one API container here, so "
            "requests during its restart fail and the client/Traccar retries.",
            "Host reboot / Docker daemon restart; OOM kills other than the explicit SIGKILL of the timeline worker.",
            "Mobile clients: their outbox retry is covered by the sync tests; only a WebSocket client is scripted.",
        ],
        commands=["cd backend", "uv run python ../scripts/drills/restart_under_load.py"],
    )


if __name__ == "__main__":
    main()
