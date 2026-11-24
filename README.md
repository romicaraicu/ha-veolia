<div align="center">

# 💧 Veolia VRSI pentru Home Assistant

**Consumul de apă, facturile și perioada de index de la Veolia România Soluții Integrate, direct în Home Assistant.**

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.10%2B-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/romicaraicu/ha-veolia?color=00A3E0)](https://github.com/romicaraicu/ha-veolia/releases)
[![Licență MIT](https://img.shields.io/badge/licen%C8%9B%C4%83-MIT-1F446E)](LICENSE.md)

</div>

Dacă ai contract de apă cu Veolia România Soluții Integrate și folosești Home Assistant, proiectul ăsta îți scutește drumul prin portalul [clienti-vrsi.veolia.ro](https://clienti-vrsi.veolia.ro). Pui emailul și parola o singură dată. De atunci, consumul lunar, facturile și perioada de transmitere a indexului apar ca entități obișnuite, cu grafice pe luni și pe ani.

> [!NOTE]
> Proiect personal, neoficial, fără legătură cu Veolia. Citește aceleași date pe care le vezi și tu în portal.

---

## Ce afli din Home Assistant

| Întrebarea ta | Unde găsești răspunsul |
|---|---|
| **Cât apă am consumat luna trecută?** | `Consum ultima lună` (m³), cu istoric pe 24 de perioade |
| **Cât am consumat pe fiecare lună și an?** | graficele *Statistics graph* din dashboard, cu tot istoricul din portal |
| **Am ceva de plată?** | `Total de plată` (lei) și `Facturi neplătite`, cu lista completă |
| **Am vreo factură întârziată?** | senzorul binar `Factură restantă` și `Următoarea scadență` |
| **Ce am plătit deja?** | `Facturi plătite` (ultimele 12 luni, plus totaluri pe ani) și `Ultima plată` |
| **Când pot transmite indexul?** | `Perioadă transmitere index` + senzorul `Transmitere index permisă` |
| **Ce date are locul de consum?** | `Loc de consum`: adresă, cod client, contract, contor |

Pe lângă senzori ai:
- un buton **Actualizare date**;
- acțiunea **`veolia_vrsi.trimite_index`**, pentru contoarele care nu sunt citite de la distanță;
- un **dashboard** gata făcut, doar cu carduri standard.

---

## De ce două componente

Portalul Veolia e protejat de **AWS WAF**, care acceptă doar browsere reale. De aceea proiectul are două bucăți, ambele în acest repository:

| Componentă | Ce face |
|---|---|
| **Add-on-ul Veolia Bridge** | pornește un Chromium fără fereastră, intră în portal cu contul tău și citește datele, apoi oprește browserul |
| **Integrarea Veolia VRSI** | cere datele de la add-on și creează senzorii, butonul, statisticile și acțiunea de index |

Add-on-ul nu ocolește protecția portalului: browserul încarcă pagina ca un utilizator obișnuit. Dacă Veolia ar cere vreodată CAPTCHA, actualizarea se oprește și primești o notificare în **Setări → Reparații**.

---

## Pornire rapidă

Ai nevoie de **Home Assistant OS** sau **Supervised** (meniul *Add-ons*), pe **amd64** sau **aarch64**, și de aproximativ **500 MB RAM** liber cât timp se citesc datele.

**1. Instalează add-on-ul**

**Setări → Add-ons → Add-on store → ⋮ → Repositories** → adaugă `https://github.com/romicaraicu/ha-veolia` → instalează **Veolia Bridge** → **Start**.

**2. Instalează integrarea**

**Setări → Marketplace → Add from link** → `romicaraicu/ha-veolia` → **Install** (pe versiuni mai vechi: HACS → *Custom repositories* → tip *Integration*). Repornește Home Assistant.

**3. Adaugă contul**

**Setări → Dispozitive și servicii** → la *Descoperite* apare **Veolia VRSI** → **Configurează** → email + parolă.

**4. (Opțional) Pune dashboard-ul**

```bash
python3 tools/genereaza_dashboard.py <cod_loc_consum>
```

Apoi lipește fișierul generat în *Editorul de configurație brută* al unui panou nou.

Pașii detaliați sunt în **[docs/instalare.md](docs/instalare.md)**.

---

## Documentație

| Ghid | Ce conține |
|---|---|
| 📦 [Instalare și configurare](docs/instalare.md) | add-on, integrare, primul cont, dashboard, dezinstalare |
| 📋 [Referință entități](docs/entitati.md) | fiecare senzor, cu atributele lui |
| 🛠️ [Depanare](docs/depanare.md) | log-uri, diagnostic, mesaje de eroare și ce înseamnă |

---

## Bune de știut

- Consumul e **lunar**, așa cum îl citește și îl facturează Veolia. Perioadele de citire nu coincid cu lunile calendaristice (de exemplu 29 sep – 28 oct); în grafice, fiecare perioadă apare la luna în care se termină.
- **Contoarele smart** sunt citite de la distanță. Pentru ele portalul nu permite transmiterea indexului, iar `Transmitere index permisă` rămâne `off`.
- Datele se reîmprospătează la 6 ore (configurabil între 2 și 24).
- Parola stă doar în configurația integrării, ca la orice altă integrare Home Assistant. Add-on-ul o primește la fiecare cerere și nu o salvează.

## Ai găsit o problemă?

Deschide un [issue](https://github.com/romicaraicu/ha-veolia/issues). Înainte, șterge din log-uri și din capturi adresa, codul de client și numerele de contract și de factură.

## Licență

[MIT](LICENSE.md)
