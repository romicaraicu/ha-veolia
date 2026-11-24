"""Extragerea datelor din factura PDF Veolia.

Se păstrează doar cifrele din blocul „DETALII FACTURĂ” (perioadă, contoare,
servicii, totaluri, date de citire). Numele, adresele, IBAN-ul, codul de client
și numărul de contract nu ajung în rezultat.
"""

from __future__ import annotations

from io import BytesIO
import re
import unicodedata

_DATE = r"(\d{2})\.(\d{2})\.(\d{4})"
_NUMBER = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$")

_INVOICE_NO = re.compile(r"FACTUR\S*\s+Nr\.\s*(\S+)")
_ISSUED = re.compile(r"Data emitere:\s*" + _DATE)
_DUE = re.compile(r"Data scaden\S*:\s*" + _DATE)
_PERIOD = re.compile(r"Perioada de facturare:\s*" + _DATE + r"\s*-\s*" + _DATE)
_NEXT_READING = re.compile(r"Data urm\S+ citiri:\s*" + _DATE)
_WINDOW = re.compile(r"Interval transmitere autocitiri:\s*" + _DATE + r"\s*-\s*" + _DATE)

_METER_HEADER = re.compile(r"^Serie contor(.*?)\s+Index nou\b")
_METER_ROW = re.compile(
    r"^(\S+)\s+([\d.,]+)\s+([\d.,]+)\s+(-?[\d.,]+)\s+(\S+)(?:\s+(.+?))?\s+" + _DATE + r"\s*$"
)
_SERVICE_ROW = re.compile(
    r"^(.+?\(mc\))\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)%\s+([\d.,]+)\s+([\d.,]+)\s*$"
)
_TOTALS = re.compile(r"^Contravaloare servicii\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$")


def ro_number(text: str) -> float | None:
    """`3.355` → 3355, `14,89` → 14.89, `1.020,50` → 1020.5."""
    text = text.strip()
    if not _NUMBER.match(text):
        return None
    return float(text.replace(".", "").replace(",", "."))


def _iso(match: re.Match, start: int = 1) -> str:
    day, month, year = match.group(start), match.group(start + 1), match.group(start + 2)
    return f"{year}-{month}-{day}"


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")


def _meter_kind(header_rest: str) -> str:
    slug = _slug(header_rest)
    return slug or "individual"


def _service_key(label: str) -> str:
    slug = _slug(label)
    if "potabil" in slug:
        return "apa"
    if "meteoric" in slug:
        return "apa_meteorica"
    if "canalizare" in slug:
        return "canalizare"
    return re.sub(r"^servicii_|_mc$", "", slug)


def parse_invoice_text(text: str) -> dict:
    """Textul facturii → dicționarul descris în planul v0.2 (fără date personale)."""
    result: dict = {
        "invoice_number": None,
        "issued": None,
        "due": None,
        "period_start": None,
        "period_end": None,
        "meters": [],
        "services": {},
        "total_without_vat": None,
        "vat": None,
        "total": None,
        "next_reading": None,
        "reading_window": None,
    }
    if m := _INVOICE_NO.search(text):
        result["invoice_number"] = m.group(1)
    if m := _ISSUED.search(text):
        result["issued"] = _iso(m)
    if m := _DUE.search(text):
        result["due"] = _iso(m)
    if m := _PERIOD.search(text):
        result["period_start"], result["period_end"] = _iso(m, 1), _iso(m, 4)
    if m := _NEXT_READING.search(text):
        result["next_reading"] = _iso(m)
    if m := _WINDOW.search(text):
        result["reading_window"] = [_iso(m, 1), _iso(m, 4)]

    kind: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if header := _METER_HEADER.match(line):
            kind = _meter_kind(header.group(1))
            continue
        if kind and (row := _METER_ROW.match(line)):
            result["meters"].append(
                {
                    "serial": row.group(1),
                    "kind": kind,
                    "index_new": ro_number(row.group(2)),
                    "index_old": ro_number(row.group(3)),
                    "consumption": ro_number(row.group(4)),
                    "method": row.group(5),
                    "reason": row.group(6),
                    "date": _iso(row, 7),
                }
            )
            continue
        kind = None
        if service := _SERVICE_ROW.match(line):
            result["services"][_service_key(service.group(1))] = {
                "label": service.group(1),
                "quantity": ro_number(service.group(2)),
                "tariff": ro_number(service.group(3)),
                "value": ro_number(service.group(4)),
                "vat_rate": ro_number(service.group(5)),
                "vat": ro_number(service.group(6)),
                "total": ro_number(service.group(7)),
            }
        elif totals := _TOTALS.match(line):
            result["total_without_vat"] = ro_number(totals.group(1))
            result["vat"] = ro_number(totals.group(2))
            result["total"] = ro_number(totals.group(3))
    return result


def pdf_to_text(data: bytes) -> str:
    """Textul tuturor paginilor din PDF."""
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
