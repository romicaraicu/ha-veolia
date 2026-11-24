"""Teste pentru serverul HTTP al bridge-ului."""

from __future__ import annotations

import asyncio
import logging

import pytest

from veolia_bridge.app.errors import PortalError
from veolia_bridge.app.server import create_app

TOKEN = "tok"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
CREDS = {"email": "user@example.com", "password": "S3cret!"}


class FakePortal:
    def __init__(self, delay: float = 0.0, error: PortalError | None = None) -> None:
        self.delay = delay
        self.error = error
        self.active = 0
        self.max_active = 0
        self.submitted: list[tuple] = []

    async def _run(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            if self.error:
                raise self.error
        finally:
            self.active -= 1

    async def snapshot(self, email: str, password: str) -> dict:
        await self._run()
        return {"client_codes": ["1"], "accounts": {}}

    async def submit_index(self, email, password, client_code, meter, index) -> dict:
        await self._run()
        self.submitted.append((client_code, meter, index))
        return {"mesaj": "Indexul a fost salvat cu succes!"}


@pytest.fixture
def make_client(aiohttp_client):
    async def _make(portal: FakePortal, op_timeout: float = 150.0):
        return await aiohttp_client(create_app(portal, TOKEN, "0.1.0", op_timeout))

    return _make


async def test_health_no_token(make_client) -> None:
    client = await make_client(FakePortal())
    resp = await client.get("/health")
    assert resp.status == 200
    assert await resp.json() == {"status": "ok", "version": "0.1.0", "busy": False}


async def test_snapshot_requires_token(make_client) -> None:
    client = await make_client(FakePortal())
    resp = await client.post("/snapshot", json=CREDS)
    assert resp.status == 401
    assert (await resp.json())["error"]["code"] == "unauthorized"
    resp = await client.post("/snapshot", json=CREDS, headers={"Authorization": "Bearer nu"})
    assert resp.status == 401


async def test_snapshot_ok(make_client) -> None:
    client = await make_client(FakePortal())
    resp = await client.post("/snapshot", json=CREDS, headers=AUTH)
    assert resp.status == 200
    assert (await resp.json())["client_codes"] == ["1"]


async def test_submit_index_ok(make_client) -> None:
    portal = FakePortal()
    client = await make_client(portal)
    body = {**CREDS, "clientCode": "10000001", "meter": "22AA000001", "index": 1234}
    resp = await client.post("/submit-index", json=body, headers=AUTH)
    assert resp.status == 200
    assert portal.submitted == [("10000001", "22AA000001", 1234)]


@pytest.mark.parametrize(
    ("code", "status"),
    [("auth", 403), ("waf_blocked", 503), ("not_allowed", 400), ("portal", 502), ("timeout", 504)],
)
async def test_error_mapping(make_client, code: str, status: int) -> None:
    client = await make_client(FakePortal(error=PortalError(code, "mesaj")))
    resp = await client.post("/snapshot", json=CREDS, headers=AUTH)
    assert resp.status == status
    assert await resp.json() == {"error": {"code": code, "message": "mesaj"}}


@pytest.mark.parametrize(
    "body",
    ["nu e json", '{"email": "a@b.ro"}', '{"email": "a@b.ro", "password": 5}'],
)
async def test_bad_body_is_400(make_client, body: str) -> None:
    client = await make_client(FakePortal())
    resp = await client.post("/snapshot", data=body, headers=AUTH)
    assert resp.status == 400
    assert (await resp.json())["error"]["code"] == "bad_request"


async def test_submit_index_bad_index_is_400(make_client) -> None:
    client = await make_client(FakePortal())
    body = {**CREDS, "clientCode": "1", "meter": "M", "index": "abc"}
    resp = await client.post("/submit-index", json=body, headers=AUTH)
    assert resp.status == 400


async def test_requests_are_serialized(make_client) -> None:
    portal = FakePortal(delay=0.2)
    client = await make_client(portal)
    r1, r2 = await asyncio.gather(
        client.post("/snapshot", json=CREDS, headers=AUTH),
        client.post("/snapshot", json=CREDS, headers=AUTH),
    )
    assert (r1.status, r2.status) == (200, 200)
    assert portal.max_active == 1


async def test_timeout(make_client) -> None:
    client = await make_client(FakePortal(delay=1.0), op_timeout=0.1)
    resp = await client.post("/snapshot", json=CREDS, headers=AUTH)
    assert resp.status == 504
    assert (await resp.json())["error"]["code"] == "timeout"


async def test_password_not_logged(make_client, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    client = await make_client(FakePortal(error=PortalError("auth", "Date greșite")))
    await client.post("/snapshot", json=CREDS, headers=AUTH)
    client2 = await make_client(FakePortal())
    await client2.post("/snapshot", json=CREDS, headers=AUTH)
    assert "S3cret!" not in caplog.text


async def test_concurrent_snapshots_share_one_portal_run(make_client) -> None:
    portal = FakePortal(delay=0.2)
    portal.calls = 0
    original = portal.snapshot

    async def counting(email, password):
        portal.calls += 1
        return await original(email, password)

    portal.snapshot = counting
    client = await make_client(portal)
    r1, r2 = await asyncio.gather(
        client.post("/snapshot", json=CREDS, headers=AUTH),
        client.post("/snapshot", json=CREDS, headers=AUTH),
    )
    assert (r1.status, r2.status) == (200, 200)
    assert portal.calls == 1


async def test_lock_wait_counts_toward_timeout(make_client) -> None:
    portal = FakePortal(delay=0.3)
    client = await make_client(portal, op_timeout=0.5)
    body = {**CREDS, "clientCode": "1", "meter": "M", "index": 1}
    r1, r2 = await asyncio.gather(
        client.post("/submit-index", json=body, headers=AUTH),
        client.post("/submit-index", json=body, headers=AUTH),
    )
    statuses = sorted([r1.status, r2.status])
    assert statuses == [200, 504]
