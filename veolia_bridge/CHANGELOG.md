# Changelog

## 0.2.0

- Descarcă PDF-ul fiecărei facturi (o singură dată, câte cel mult 6 la o actualizare) și extrage: perioada, tarifele, cantitățile facturate, totalurile și **toate contoarele** de pe factură (propriu, condominiu sau alte tipuri).
- PDF-urile nu se salvează; în `/data/invoices.json` rămân doar cifrele extrase.

## 0.1.0

- Prima versiune: citește contul Veolia VRSI printr-un Chromium headless și îl pune la dispoziția integrării Veolia VRSI.
