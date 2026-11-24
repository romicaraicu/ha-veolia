# Depanare

## Unde mă uit

- **Log-ul add-on-ului**: **Setări → Add-ons → Veolia Bridge → Log**. Pentru detalii, pune opțiunea `log_level: debug` și repornește add-on-ul.
- **Log-ul integrării**: adaugă în `configuration.yaml`

  ```yaml
  logger:
    logs:
      custom_components.veolia_vrsi: debug
  ```

- **Diagnostic**: **Setări → Dispozitive și servicii → Veolia VRSI → ⋮ → Descarcă diagnosticul**. Emailul, parola, token-ul, adresele, numele și numerele de factură sunt mascate.

## Mesaje de eroare

| Mesaj | Ce înseamnă | Ce faci |
|---|---|---|
| *Email sau parolă incorecte* / cerere de reautentificare | portalul a respins datele | verifică login-ul pe clienti-vrsi.veolia.ro și pune parola nouă |
| *Nu mă pot conecta la add-on-ul Veolia Bridge…* | add-on-ul e oprit sau repornește | pornește add-on-ul; entitățile revin la următoarea actualizare |
| *Token-ul add-on-ului… nu este corect* | add-on-ul a fost reinstalat și are alt token | repornește add-on-ul: descoperirea actualizează automat token-ul |
| *Portalul Veolia blochează actualizarea automată* (în **Reparații**) | AWS WAF a refuzat browserul automat sau cere CAPTCHA | verifică dacă portalul merge din browserul tău; încearcă mai târziu cu **Actualizare date**. Integrarea nu ocolește protecția |
| *Contorul este citit de la distanță…* | ai apelat `trimite_index` pentru un contor smart | nimic de făcut: Veolia citește singură contorul |
| *Indexul poate fi transmis doar în perioada de autocitire* | ești în afara perioadei | vezi `Perioadă transmitere index` |

## Testează accesul fără Home Assistant

Din folderul proiectului, pe calculatorul tău:

```bash
python3 -m venv .venv
.venv/bin/pip install playwright aiohttp
.venv/bin/python -m playwright install chromium
.venv/bin/python tools/test_bridge.py --local
```

Scriptul cere emailul și parola (nu le afișează) și tipărește doar un rezumat: câte locuri, perioade, facturi și plăți a găsit.

Ai add-on-ul pornit și vrei să-l testezi direct?

```bash
.venv/bin/python tools/test_bridge.py http://<adresa>:8099 <token>
```
