"""Accesul la portal printr-un Chromium headless (Playwright).

Browserul încarcă pagina de login exact ca un utilizator: scripturile site-ului
(inclusiv verificarea AWS WAF) rulează normal. Nu se încearcă rezolvarea unui
CAPTCHA: dacă pagina nu se încarcă, operația se oprește cu `waf_blocked`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
import json
import logging
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout

from .errors import PortalError, classify_call_failure, classify_login_failure
from .invoice_pdf import pdf_to_text
from .invoices import InvoiceCache, add_invoice_details
from .snapshot import Call, build_save_index_body, build_snapshot

_LOGGER = logging.getLogger(__name__)

PORTAL_URL = "https://clienti-vrsi.veolia.ro"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_POST_JS = """
async ([endpoint, body]) => {
  const csrf = document.getElementById('csrf_token')?.value || '';
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'Csrf-Token': csrf},
    body: body === null ? undefined : JSON.stringify(body),
  });
  return {
    status: response.status,
    waf: response.headers.get('x-amzn-waf-action'),
    text: await response.text(),
  };
}
"""


class PlaywrightPortal:
    """Implementarea `Portal` folosită în add-on."""

    def __init__(
        self,
        base_url: str = PORTAL_URL,
        waf_timeout: float = 45.0,
        invoice_cache: InvoiceCache | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._waf_timeout_ms = waf_timeout * 1000
        self._invoice_cache = invoice_cache

    async def snapshot(self, email: str, password: str) -> dict:
        async with self._session(email, password) as call:
            snapshot = await build_snapshot(call, date.today())
            if self._invoice_cache is not None:
                await add_invoice_details(call, snapshot, self._invoice_cache, pdf_to_text)
            return snapshot

    async def submit_index(
        self, email: str, password: str, client_code: str, meter: str, index: int
    ) -> dict:
        async with self._session(email, password) as call:
            last = await call("get-last-index", {"clientCode": client_code, "meterSernr": meter})
            details = (last or {}).get("MeterReadingDetails")
            if not details:
                raise PortalError("not_allowed", f"Portalul nu are date pentru contorul {meter}.")
            body = build_save_index_body(client_code, details, index)
            content = await call("save-index", body)
            return {"mesaj": "Indexul a fost salvat cu succes!", "raspuns": content}

    # ------------------------------------------------------------ intern
    async def _wait_ready(self, page: Page) -> None:
        try:
            await page.wait_for_selector(
                "#csrf_token", state="attached", timeout=self._waf_timeout_ms
            )
        except PlaywrightTimeout:
            html = (await page.content()).lower()
            if "captcha" in html:
                raise PortalError(
                    "waf_blocked", "Portalul cere CAPTCHA; actualizarea automată nu este posibilă."
                ) from None
            raise PortalError(
                "waf_blocked", "Portalul nu s-a încărcat (protecția AWS WAF nu a permis accesul)."
            ) from None

    async def _post(self, page: Page, endpoint: str, body: dict | None) -> dict[str, Any]:
        result = await page.evaluate(_POST_JS, [endpoint, body])
        if result.get("waf"):
            raise PortalError("waf_blocked", f"AWS WAF a blocat cererea {endpoint}.")
        try:
            data = json.loads(result.get("text") or "")
        except ValueError:
            raise PortalError(
                "portal", f"{endpoint}: răspuns neașteptat (HTTP {result.get('status')})."
            ) from None
        if not isinstance(data, dict):
            raise PortalError("portal", f"{endpoint}: răspuns neașteptat.")
        return data

    @asynccontextmanager
    async def _session(self, email: str, password: str) -> AsyncIterator[Call]:
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                try:
                    context = await browser.new_context(
                        user_agent=USER_AGENT, locale="ro-RO", timezone_id="Europe/Bucharest"
                    )
                    page = await context.new_page()
                    await page.goto(f"{self._base}/login", wait_until="domcontentloaded")
                    await self._wait_ready(page)

                    login = await self._post(
                        page, "login-submit", {"email": email, "password": password}
                    )
                    if login.get("success") is not True:
                        raise classify_login_failure(login)
                    _LOGGER.debug("Autentificare reușită")

                    await page.goto(f"{self._base}/sumar", wait_until="domcontentloaded")
                    await self._wait_ready(page)
                    if "/login" in page.url:
                        raise PortalError("auth", "Portalul a respins sesiunea după autentificare.")

                    async def call(endpoint: str, body: dict | None) -> Any:
                        data = await self._post(page, endpoint, body)
                        if data.get("success") is not True:
                            raise classify_call_failure(endpoint, data)
                        return data.get("content")

                    yield call
                finally:
                    await browser.close()
        except PlaywrightTimeout as err:
            raise PortalError("timeout", f"Portalul nu a răspuns la timp: {err.message}") from None
        except PlaywrightError as err:
            raise PortalError("portal", f"Eroare browser: {err.message}") from None
