"""Teste pentru token-ul persistent și descoperirea prin Supervisor."""

from __future__ import annotations

import stat

import aiohttp
from aiohttp import web

from veolia_bridge.app.supervisor import announce, load_or_create_token


def test_token_persisted(tmp_path) -> None:
    path = tmp_path / "token"
    first = load_or_create_token(path)
    assert len(first) >= 32
    assert load_or_create_token(path) == first
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


async def test_announce_without_supervisor_is_noop(monkeypatch) -> None:
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    async with aiohttp.ClientSession() as session:
        assert await announce(session, "tok", 8099) is False


async def test_announce_posts_discovery(aiohttp_server, monkeypatch) -> None:
    received: dict = {}

    async def info(request: web.Request) -> web.Response:
        received["info_auth"] = request.headers.get("Authorization")
        return web.json_response({"result": "ok", "data": {"hostname": "abc123-veolia-bridge"}})

    async def discovery(request: web.Request) -> web.Response:
        received["discovery"] = await request.json()
        return web.json_response({"result": "ok", "data": {"uuid": "u1"}})

    app = web.Application()
    app.router.add_get("/addons/self/info", info)
    app.router.add_post("/discovery", discovery)
    server = await aiohttp_server(app)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "sup")

    async with aiohttp.ClientSession() as session:
        ok = await announce(session, "tok", 8099, base_url=str(server.make_url("")).rstrip("/"))

    assert ok is True
    assert received["info_auth"] == "Bearer sup"
    assert received["discovery"] == {
        "service": "veolia_vrsi",
        "config": {"host": "abc123-veolia-bridge", "port": 8099, "token": "tok"},
    }


async def test_announce_failure_does_not_raise(aiohttp_server, monkeypatch) -> None:
    async def info(request: web.Request) -> web.Response:
        return web.json_response({"result": "error"}, status=500)

    app = web.Application()
    app.router.add_get("/addons/self/info", info)
    server = await aiohttp_server(app)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "sup")
    async with aiohttp.ClientSession() as session:
        ok = await announce(session, "tok", 8099, base_url=str(server.make_url("")).rstrip("/"))
    assert ok is False
