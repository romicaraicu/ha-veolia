"""Interpretarea snapshot-ului primit de la add-on-ul Veolia Bridge.

Modulul nu depinde de Home Assistant, ca să poată fi testat independent.
Forma snapshot-ului e descrisă în docs/superpowers/specs/2026-11-24-veolia-design.md (5.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from .const import AMOUNT_EPSILON, PAID_LIMIT

_MONTHS_RO = (
    "ian.", "feb.", "mar.", "apr.", "mai", "iun.",
    "iul.", "aug.", "sep.", "oct.", "nov.", "dec.",
)


def parse_date(value: Any) -> date | None:
    """`YYYY-MM-DD` → date; `0000-00-00`, gol sau invalid → None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value or value.startswith("0000"):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    """Număr sau șir numeric → float; altfel None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _fmt_day(d: date, with_year: bool) -> str:
    text = f"{d.day} {_MONTHS_RO[d.month - 1]}"
    return f"{text} {d.year}" if with_year else text


def _months_ago(today: date, months: int) -> date:
    year, month = divmod(today.year * 12 + today.month - 1 - months, 12)
    return date(year, month + 1, min(today.day, 28))


@dataclass
class Invoice:
    number: str
    issued: date | None
    due: date | None
    total: float
    balance: float
    paid: bool
    paid_on: date | None

    def is_overdue(self, today: date) -> bool:
        return (
            not self.paid
            and self.balance > AMOUNT_EPSILON
            and self.due is not None
            and self.due < today
        )

    def as_attr(self) -> dict[str, Any]:
        return {
            "numar": self.number,
            "emisa": iso(self.issued),
            "scadenta": iso(self.due),
            "total": self.total,
            "rest_plata": self.balance,
            "platita_la": iso(self.paid_on),
        }


def _invoice(raw: dict[str, Any], paid: bool) -> Invoice:
    balance = to_float(raw.get("SoldTotal"))
    if balance is None:
        balance = to_float(raw.get("Sold")) or 0.0
    return Invoice(
        number=str(raw.get("InvoiceNumber") or ""),
        issued=parse_date(raw.get("DateIn")),
        due=parse_date(raw.get("DueDate")),
        total=to_float(raw.get("Total")) or 0.0,
        balance=0.0 if paid else balance,
        paid=paid,
        paid_on=parse_date(raw.get("LastPayDate")) or parse_date(raw.get("PayUTransactionDate")),
    )


@dataclass
class Period:
    start: date | None
    end: date
    consumption: float
    index: float | None
    kind: str

    @property
    def month(self) -> str:
        return f"{self.end.year:04d}-{self.end.month:02d}"

    def as_attr(self) -> dict[str, Any]:
        return {
            "de_la": iso(self.start),
            "pana_la": iso(self.end),
            "luna": self.month,
            "m3": self.consumption,
            "index": self.index,
            "tip": self.kind,
        }


@dataclass
class Payment:
    paid_on: date | None
    amount: float
    kind: str

    def as_attr(self) -> dict[str, Any]:
        return {"data": iso(self.paid_on), "suma": self.amount, "tip": self.kind}


@dataclass
class InvoiceMeter:
    serial: str
    kind: str
    index_new: float | None
    index_old: float | None
    consumption: float | None
    method: str
    reason: str | None
    date: date | None

    def as_attr(self) -> dict[str, Any]:
        return {
            "serie": self.serial,
            "tip": self.kind,
            "index_nou": self.index_new,
            "index_vechi": self.index_old,
            "consum": self.consumption,
            "stabilit_prin": self.method,
            "motiv": self.reason,
            "data": iso(self.date),
        }


@dataclass
class InvoiceDetail:
    """Cifrele extrase din PDF-ul unei facturi."""

    number: str
    issued: date | None
    period_start: date | None
    period_end: date | None
    meters: list[InvoiceMeter]
    services: dict[str, dict[str, Any]]
    total: float | None

    @property
    def month(self) -> str | None:
        end = self.period_end or self.issued
        return f"{end.year:04d}-{end.month:02d}" if end else None

    def tariff(self, service: str) -> float | None:
        return to_float((self.services.get(service) or {}).get("tariff"))

    @property
    def water_billed(self) -> float | None:
        return to_float((self.services.get("apa") or {}).get("quantity"))

    @property
    def price_per_m3(self) -> float | None:
        """Total factură (cu TVA, apă + canalizare) / m³ de apă facturați."""
        if not self.total or not self.water_billed:
            return None
        return round(self.total / self.water_billed, 2)

    @property
    def own_consumption(self) -> float | None:
        values = [m.consumption for m in self.meters if m.kind == "individual" and m.consumption is not None]
        return round(sum(values), 3) if values else None

    @property
    def effective_cost_per_m3(self) -> float | None:
        """Total factură / consumul contoarelor proprii (include partea din condominiu)."""
        if not self.total or not self.own_consumption:
            return None
        return round(self.total / self.own_consumption, 2)

    @property
    def billed_difference(self) -> float | None:
        if self.water_billed is None or self.own_consumption is None:
            return None
        return round(self.water_billed - self.own_consumption, 3)

    def as_attr(self) -> dict[str, Any]:
        return {
            "factura": self.number,
            "luna": self.month,
            "de_la": iso(self.period_start),
            "pana_la": iso(self.period_end),
            "apa_facturata": self.water_billed,
            "consum_contoare_proprii": self.own_consumption,
            "pret_mc": self.price_per_m3,
            "cost_efectiv_mc": self.effective_cost_per_m3,
            "total": self.total,
        }


def _invoice_detail(raw: dict[str, Any]) -> InvoiceDetail | None:
    if not isinstance(raw, dict) or raw.get("parse_error"):
        return None
    meters = [
        InvoiceMeter(
            serial=str(m.get("serial") or ""),
            kind=str(m.get("kind") or "individual"),
            index_new=to_float(m.get("index_new")),
            index_old=to_float(m.get("index_old")),
            consumption=to_float(m.get("consumption")),
            method=str(m.get("method") or ""),
            reason=m.get("reason"),
            date=parse_date(m.get("date")),
        )
        for m in raw.get("meters") or []
        if isinstance(m, dict) and m.get("serial")
    ]
    services = raw.get("services") if isinstance(raw.get("services"), dict) else {}
    return InvoiceDetail(
        number=str(raw.get("invoice_number") or ""),
        issued=parse_date(raw.get("issued")),
        period_start=parse_date(raw.get("period_start")),
        period_end=parse_date(raw.get("period_end")),
        meters=meters,
        services=services,
        total=to_float(raw.get("total")),
    )


@dataclass
class LocationData:
    client_code: str
    code: str
    installation: str
    address: str
    meters: list[str]
    contract: dict[str, Any] | None = None
    reading: dict[str, Any] | None = None
    periods: list[Period] = field(default_factory=list)
    unpaid: list[Invoice] = field(default_factory=list)
    paid: list[Invoice] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    total_to_pay: float | None = None
    last_invoice: Invoice | None = None
    invoice_details: list[InvoiceDetail] = field(default_factory=list)

    # ---------------------------------------------------------- consum
    @property
    def meter(self) -> str | None:
        return self.meters[0] if self.meters else None

    @property
    def last_period(self) -> Period | None:
        return self.periods[0] if self.periods else None

    def monthly_consumption(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for p in sorted(self.periods, key=lambda p: p.end):
            totals[p.month] = round(totals.get(p.month, 0.0) + p.consumption, 3)
        return totals

    def yearly_consumption(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for p in self.periods:
            year = str(p.end.year)
            totals[year] = round(totals.get(year, 0.0) + p.consumption, 3)
        return dict(sorted(totals.items(), reverse=True))

    def current_year_consumption(self, today: date) -> float:
        return self.yearly_consumption().get(str(today.year), 0.0)

    # ---------------------------------------------------------- index
    @property
    def last_index(self) -> float | None:
        return to_float((self.reading or {}).get("LastIndex"))

    @property
    def last_index_date(self) -> date | None:
        return parse_date((self.reading or {}).get("LastIndexDate"))

    @property
    def is_smart(self) -> bool:
        return bool((self.reading or {}).get("IsSmart"))

    @property
    def reading_start(self) -> date | None:
        return parse_date((self.reading or {}).get("AdatsollMin"))

    @property
    def reading_end(self) -> date | None:
        return parse_date((self.reading or {}).get("Adatsoll"))

    @property
    def reading_label(self) -> str | None:
        start, end = self.reading_start, self.reading_end
        if not start or not end:
            return None
        if (start.year, start.month) == (end.year, end.month):
            return f"{start.day}–{_fmt_day(end, True)}"
        if start.year == end.year:
            return f"{_fmt_day(start, False)}–{_fmt_day(end, True)}"
        return f"{_fmt_day(start, True)}–{_fmt_day(end, True)}"

    @property
    def reading_open(self) -> bool:
        if not self.reading or self.is_smart:
            return False
        return self.reading.get("Inperioada") == "X"

    # ---------------------------------------------------------- detalii factură (PDF)
    @property
    def latest_invoice_detail(self) -> InvoiceDetail | None:
        return self.invoice_details[0] if self.invoice_details else None

    def meter_readings(self) -> dict[str, InvoiceMeter]:
        """Ultima citire a fiecărui contor apărut pe facturi (serie → citire)."""
        readings: dict[str, InvoiceMeter] = {}
        for detail in reversed(self.invoice_details):
            for meter in detail.meters:
                readings[meter.serial] = meter
        return dict(sorted(readings.items(), key=lambda kv: (kv[1].kind != "individual", kv[0])))

    def meter_monthly(self, serial: str) -> dict[str, float]:
        totals: dict[str, float] = {}
        for detail in reversed(self.invoice_details):
            for meter in detail.meters:
                if meter.serial == serial and meter.consumption is not None and detail.month:
                    totals[detail.month] = round(totals.get(detail.month, 0.0) + meter.consumption, 3)
        return dict(sorted(totals.items()))

    def billed_monthly(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for detail in reversed(self.invoice_details):
            if detail.water_billed is not None and detail.month:
                totals[detail.month] = round(totals.get(detail.month, 0.0) + detail.water_billed, 3)
        return dict(sorted(totals.items()))

    def price_monthly(self) -> dict[str, float]:
        prices: dict[str, float] = {}
        for detail in reversed(self.invoice_details):
            if detail.price_per_m3 is not None and detail.month:
                prices[detail.month] = detail.price_per_m3
        return dict(sorted(prices.items()))

    # ---------------------------------------------------------- facturi
    def next_due_date(self, today: date) -> date | None:
        dues = [i.due for i in self.unpaid if i.due and i.balance > AMOUNT_EPSILON]
        return min(dues) if dues else None

    def overdue_amount(self, today: date) -> float:
        return round(sum(i.balance for i in self.unpaid if i.is_overdue(today)), 2)

    def paid_recent(self, today: date) -> list[Invoice]:
        limit = _months_ago(today, 12)
        recent = [i for i in self.paid if (i.issued or date.min) >= limit]
        recent.sort(key=lambda i: i.issued or date.min, reverse=True)
        return recent[:PAID_LIMIT]

    def paid_yearly_totals(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for i in self.paid:
            if i.issued:
                year = str(i.issued.year)
                totals[year] = round(totals.get(year, 0.0) + i.total, 2)
        return dict(sorted(totals.items(), reverse=True))

    @property
    def last_payment(self) -> Payment | None:
        return self.payments[0] if self.payments else None


def _period(raw: dict[str, Any]) -> Period | None:
    end = parse_date(raw.get("EndDate"))
    consumption = to_float(raw.get("Consumption"))
    if end is None or consumption is None:
        return None
    return Period(
        start=parse_date(raw.get("StartDate")),
        end=end,
        consumption=consumption,
        index=to_float(raw.get("Index")),
        kind=str(raw.get("Type") or ""),
    )


def _payment(raw: dict[str, Any]) -> Payment:
    return Payment(
        paid_on=parse_date(raw.get("PaymentDate")),
        amount=to_float(raw.get("PaidAmount")) or 0.0,
        kind=str(raw.get("PaymentType") or ""),
    )


def build_locations(snapshot: dict[str, Any]) -> dict[str, LocationData]:
    """Construiește câte un LocationData pentru fiecare loc de consum."""
    result: dict[str, LocationData] = {}
    for client_code, account in (snapshot.get("accounts") or {}).items():
        account = account or {}
        contracts = account.get("contracts") or []
        meters_raw = account.get("meters") or {}
        unpaid = [_invoice(i, False) for i in account.get("unpaid_invoices") or []]
        paid = [_invoice(i, True) for i in account.get("paid_invoices") or []]
        payments = [_payment(p) for p in account.get("payments") or []]
        payments.sort(key=lambda p: p.paid_on or date.min, reverse=True)
        last_invoice_raw = account.get("last_invoice")
        last_invoice = None
        if last_invoice_raw:
            number = last_invoice_raw.get("InvoiceNumber")
            last_invoice = _invoice(
                last_invoice_raw, not any(i.number == number for i in unpaid)
            )

        details = [
            d for d in map(_invoice_detail, (account.get("invoice_details") or {}).values()) if d
        ]
        details.sort(key=lambda d: d.period_end or d.issued or date.min, reverse=True)
        account_locations = [
            loc for loc in account.get("locations") or [] if loc.get("ConsumptionPointCode")
        ]

        for loc in account_locations:
            code = str(loc.get("ConsumptionPointCode") or "")
            if not code:
                continue
            meters = [str(m) for m in loc.get("ConsumptionMeters") or [] if m]
            meter_data = meters_raw.get(meters[0], {}) if meters else {}
            # istoricul tuturor contoarelor locului (ex. după înlocuirea contorului),
            # fără dubluri pe (contor, sfârșit perioadă)
            seen: set[tuple[str, date]] = set()
            periods = []
            for meter in meters:
                for raw in (meters_raw.get(meter) or {}).get("index_history") or []:
                    period = _period(raw)
                    if period and (meter, period.end) not in seen:
                        seen.add((meter, period.end))
                        periods.append(period)
            periods.sort(key=lambda p: p.end, reverse=True)
            contract = next(
                (c for c in contracts if str(c.get("ConsumptionPointCode")) == code),
                None,
            )
            result[code] = LocationData(
                client_code=str(client_code),
                code=code,
                installation=str(loc.get("ConsumptionInstallation") or ""),
                address=str(loc.get("ConsumptionClientAddress") or code),
                meters=meters,
                contract=contract,
                reading=meter_data.get("last_index") or None,
                periods=periods,
                unpaid=unpaid,
                paid=paid,
                payments=payments,
                total_to_pay=to_float(account.get("total_to_pay")),
                last_invoice=last_invoice,
                invoice_details=[
                    d
                    for d in details
                    # o factură aparține locului cu contorul ei; un cod client cu un singur
                    # loc primește toate facturile
                    if len(account_locations) == 1 or any(m.serial in meters for m in d.meters)
                ],
            )
    return result
