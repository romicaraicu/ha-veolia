# Instalare și configurare

## Cerințe

- **Home Assistant OS** sau **Supervised**: ai nevoie de meniul **Setări → Add-ons**.
- Procesor **amd64** sau **aarch64**: mini-PC, mașină virtuală, Raspberry Pi 4/5 cu sistem pe 64 de biți, HA Green/Yellow.
- Aproximativ **500 MB RAM** liber cât timp se citesc datele (15–40 de secunde, de câteva ori pe zi).
- Un cont pe [clienti-vrsi.veolia.ro](https://clienti-vrsi.veolia.ro) cu care te poți loga din browser.

## 1. Add-on-ul Veolia Bridge

1. **Setări → Add-ons → Add-on store**.
2. **⋮** (dreapta sus) → **Repositories** → adaugă `https://github.com/romicaraicu/ha-veolia` → **Add** → închide.
3. Caută **Veolia Bridge** → **Install**. Prima instalare durează câteva minute: imaginea conține Chromium.
4. **Start**. În tab-ul **Log** trebuie să vezi:

   ```
   Veolia Bridge 0.1.0 - Listening on 0.0.0.0:8099
   Discovery sent (...:8099)
   ```

Add-on-ul nu are porturi deschise în rețeaua ta și nu are nevoie de configurare.

## 2. Integrarea Veolia VRSI

**Varianta Marketplace** (Home Assistant 2026.11+): **Setări → Marketplace → Add from link** → `romicaraicu/ha-veolia` → **Install**.

**Varianta HACS**: **HACS → ⋮ → Custom repositories** → `https://github.com/romicaraicu/ha-veolia`, tip **Integration** → instalează **Veolia VRSI**.

**Manual**: copiază folderul `custom_components/veolia_vrsi` în `config/custom_components/`.

Repornește Home Assistant.

## 3. Adaugă contul

1. **Setări → Dispozitive și servicii**. La **Descoperite** apare **Veolia VRSI** (anunțat de add-on) → **Configurează**.
2. Introdu emailul și parola de pe clienti-vrsi.veolia.ro. Verificarea durează cât o actualizare (15–40 s).
3. Dacă ai mai multe locuri de consum, alege-le pe cele dorite.

Fiecare loc de consum devine un dispozitiv *Veolia &lt;adresă&gt;*, cu entitățile din [entitati.md](entitati.md).

> Nu apare la *Descoperite*? Verifică în log-ul add-on-ului că rulează. Poți adăuga integrarea și manual (**Adaugă integrare → Veolia VRSI**): ai nevoie de adresă și token, pe care add-on-ul le scrie în log când descoperirea automată nu reușește.

## 4. Dashboard (opțional)

Codul locului de consum e numărul de serie al dispozitivului (**Setări → Dispozitive și servicii → Veolia VRSI → dispozitiv**).

```bash
python3 tools/genereaza_dashboard.py <cod_loc_consum>
```

Apoi **Setări → Panouri de bord → Adaugă panou → Pornește de la zero** → deschide-l → ✏️ → ⋮ → **Editor de configurație brută** → lipește conținutul fișierului `dashboard/veolia_<cod>.yaml`.

Graficele pe luni și pe ani folosesc cardul standard **Statistics graph** cu statistica `veolia_vrsi:consum_apa_<cod>`, care conține tot istoricul din portal. Preferi ApexCharts? Vezi `dashboard/card_grafic_consum_apexcharts.yaml`.

## Opțiuni

**Setări → Dispozitive și servicii → Veolia VRSI → Configurează**: intervalul de actualizare (2–24 de ore, implicit 6) și locurile de consum urmărite.

## Dezinstalare

1. Șterge intrarea Veolia VRSI din **Dispozitive și servicii**.
2. Dezinstalează integrarea (Marketplace / HACS / ștergi folderul) și repornește.
3. Oprește și dezinstalează add-on-ul **Veolia Bridge**.
