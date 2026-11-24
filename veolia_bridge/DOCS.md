# Veolia Bridge

Add-on-ul citește contul tău de pe [clienti-vrsi.veolia.ro](https://clienti-vrsi.veolia.ro) pentru integrarea **Veolia VRSI**.

Portalul Veolia e protejat de AWS WAF, care acceptă doar browsere reale. Add-on-ul pornește un Chromium fără fereastră doar cât citește datele (cam 15–40 de secunde), apoi îl oprește.

## Instalare

1. **Setări → Add-ons → Add-on store → ⋮ → Repositories** și adaugă `https://github.com/romicaraicu/ha-veolia`.
2. Instalează **Veolia Bridge** și pornește-l.
3. Instalează și adaugă integrarea **Veolia VRSI**. Home Assistant o descoperă automat după ce add-on-ul pornește; tu introduci doar emailul și parola contului Veolia.

## Ce trebuie să știi

- Funcționează pe **amd64** și **aarch64** (Raspberry Pi 4/5 pe 64 de biți, mini-PC, HA Green, mașini virtuale).
- În timpul unei actualizări are nevoie de aproximativ **300–500 MB RAM** liber.
- Nu ține parola: o primește de la integrare la fiecare cerere și nu o scrie nicăieri.
- Ascultă doar pe rețeaua internă a Home Assistant (portul 8099, nepublicat în rețeaua ta). Cererile cer un token generat la prima pornire, trimis automat integrării.

## Opțiuni

| Opțiune | Descriere |
|---|---|
| `log_level` | `debug`, `info` (implicit), `warning` sau `error` |

## Probleme

- **`waf_blocked`** – portalul a refuzat browserul automat (de exemplu, cere CAPTCHA). Add-on-ul nu încearcă să ocolească protecția; verifică dacă portalul merge din browserul tău și încearcă din nou mai târziu.
- **`auth`** – email sau parolă greșite; integrarea îți cere parola din nou.
