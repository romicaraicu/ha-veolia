#!/usr/bin/env python3
"""Test real al accesului la portalul Veolia, cu rezumat anonimizat.

Moduri:
  python tools/test_bridge.py --local
      rulează browserul direct pe calculatorul tău (pip install playwright aiohttp
      și `python -m playwright install chromium` înainte)
  python tools/test_bridge.py <url_bridge> <token>
      apelează add-on-ul pornit (ex. http://127.0.0.1:8099)

Emailul se ia din VEOLIA_EMAIL (sau se cere), parola din VEOLIA_PASSWORD
(sau se cere fără afișare). Nu se afișează date personale.
"""

from __future__ import annotations

import asyncio
import getpass
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _credentials() -> tuple[str, str]:
    email = os.environ.get("VEOLIA_EMAIL") or input("Email Veolia: ").strip()
    password = os.environ.get("VEOLIA_PASSWORD") or getpass.getpass("Parola Veolia: ")
    return email, password


def summarize(snap: dict, seconds: float) -> None:
    accounts = snap.get("accounts", {})
    print(f"OK în {seconds:.1f} s")
    print(f"  coduri client: {len(snap.get('client_codes', []))}")
    for i, acc in enumerate(accounts.values(), 1):
        print(f"  cont {i}:")
        print(f"    locuri de consum: {len(acc.get('locations', []))}")
        for j, meter in enumerate(acc.get("meters", {}).values(), 1):
            last = meter.get("last_index") or {}
            print(
                f"    contor {j}: {len(meter.get('index_history', []))} perioade de consum, "
                f"smart={last.get('IsSmart')}, perioadă index "
                f"{last.get('AdatsollMin')} → {last.get('Adatsoll')} (Inperioada={last.get('Inperioada')!r})"
            )
        print(f"    facturi neplătite: {len(acc.get('unpaid_invoices', []))}")
        print(f"    facturi plătite: {len(acc.get('paid_invoices', []))}")
        print(f"    plăți: {len(acc.get('payments', []))}")
        print(f"    total de plată: {acc.get('total_to_pay')}")


async def run_local() -> None:
    from veolia_bridge.app.browser import PlaywrightPortal
    from veolia_bridge.app.errors import PortalError

    email, password = _credentials()
    started = time.monotonic()
    try:
        snap = await PlaywrightPortal().snapshot(email, password)
    except PortalError as err:
        print(f"EROARE {err.code}: {err.message}")
        sys.exit(1)
    summarize(snap, time.monotonic() - started)


async def run_remote(url: str, token: str) -> None:
    import aiohttp

    email, password = _credentials()
    started = time.monotonic()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
        async with session.post(
            f"{url.rstrip('/')}/snapshot",
            json={"email": email, "password": password},
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            data = await resp.json()
    if "error" in data:
        print(f"EROARE {data['error']['code']}: {data['error']['message']}")
        sys.exit(1)
    summarize(data, time.monotonic() - started)


def main() -> None:
    if sys.argv[1:] == ["--local"]:
        asyncio.run(run_local())
    elif len(sys.argv) == 3:
        asyncio.run(run_remote(sys.argv[1], sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
