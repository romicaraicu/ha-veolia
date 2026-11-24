# Veolia VRSI pentru Home Assistant — design

Data: 2026-11-24 · Stare: propus, așteaptă aprobare

## 1. Ce vrem și de ce

Utilizatorul are contract de apă cu Veolia România Soluții Integrate (portalul
`https://clienti-vrsi.veolia.ro`) și vrea să vadă în Home Assistant aceleași
lucruri pe care le are deja pentru curent prin `ha-premierenergy`:

- consumul pe luni și pe ani, cu **grafic lunar și anual**;
- facturile de plată și facturile plătite (plus plățile);
- locul de consum;
- perioada de transmitere a indexului.

Instalarea și folosirea trebuie să semene cu `ha-premierenergy`: se adaugă
integrarea, se pun **email + parolă o singură dată**, apar entități obișnuite,
un buton de actualizare și un dashboard gata făcut.

### Obiective
- Entități per loc de consum, cu istoric și utilizabile în automatizări.
- Grafic lunar și anual al consumului de apă.
- Experiență de instalare cât mai apropiată de Premier Energy.

### Non-obiective (în prima versiune)
- Plata facturilor din HA (`invoices-payment`, `total-invoices-payment`).
- Descărcarea PDF-urilor de factură (`download-invoice`) — posibil mai târziu.
- Mesaje, preferințe de comunicare, modificarea datelor contului.
- Instalări fără Supervisor (HA Container / Core).

### Anti-obiective (eșec chiar dacă „merge”)
- **Nu** rezolvăm și nu ocolim provocarea AWS WAF sau un eventual CAPTCHA prin
  altceva decât un browser real care rulează scripturile site-ului. Dacă Veolia
  cere CAPTCHA, integrarea raportează clar problema și se oprește; nu încearcă
  să-l rezolve.
- **Nu** stocăm parola în clar în altă parte decât în config entry-ul HA (la fel
  ca Premier Energy). Add-on-ul nu persistă credențiale.
- **Nu** apelăm endpoint-uri care modifică ceva în cont, cu excepția
  `save-index`, și doar la cererea explicită a utilizatorului (acțiune HA).
- **Nu** interogăm portalul agresiv (implicit de 4 ori pe zi).

## 2. Constrângeri

- **AWS WAF cu provocare JavaScript** în fața întregului site. Verificat
  2026-11-24: orice cerere fără cookie-ul `aws-waf-token` primește `202` cu
  `x-amzn-waf-action: challenge` (și `403` fără User-Agent de browser),
  **inclusiv** endpoint-urile JSON `POST`. Un client `aiohttp` nu poate obține
  datele.
- Home Assistant al utilizatorului: **Home Assistant OS**, Core 2026.11.3,
  Supervisor 2026.11.0 → add-on-urile sunt disponibile.
- Utilizatorul creează singur repository-ul GitHub și face push manual.
- Documentația și textele din UI în **română** (ca `ha-premierenergy`), cu
  traducere `en.json`.

## 3. Variante luate în calcul

| Variantă | Pe scurt | Compromis |
|---|---|---|
| **A. Add-on „bridge” cu browser + integrare separată** ✅ | Add-on-ul rulează Chromium headless și expune datele pe rețeaua internă HA; integrarea custom face entitățile | Două lucruri de instalat; reutilizează aproape tot din Premier Energy; browserul e izolat |
| B. Totul în add-on, publicare prin MQTT | Add-on-ul publică entități prin MQTT discovery | O singură instalare, dar cere Mosquitto, fără config flow/reauth, acțiunea de index și butonul sunt stângace |
| C. Ca A, dar browserul doar obține cookie-urile | Integrarea face cererile cu cookie-urile primite | Mai ieftin, dar netestat dacă WAF acceptă tokenul din alt client (alt fingerprint TLS); rămâne optimizare posibilă peste A |

**Ales: A** (de utilizator, 2026-11-24). Motiv: cea mai apropiată de
Premier Energy, entități „adevărate”, partea fragilă (browserul) izolată într-o
singură bucată mică care se poate repara independent.

## 4. API-ul portalului (mapat 2026-11-24)

Site Drupal. Toate cererile sunt `POST` relative la `https://clienti-vrsi.veolia.ro/`,
cu `Content-Type: application/json` și header `Csrf-Token: <valoare>`, unde
valoarea vine din `<input type="hidden" id="csrf_token">` din orice pagină HTML.
Sesiunea e un cookie HttpOnly. Răspunsul are mereu forma
`{success: bool, code: int, error: str|null, content: ...}`; sesiune expirată →
`{success:false, code:401, error:"Neautorizat!"}` (HTTP 200).

| Endpoint | Body | `content` (câmpuri relevante) |
|---|---|---|
| `login-submit` | `{email, password}` | `{redirectUrl}` la succes; `error` cu mesaj la eșec |
| `get-client-codes` | — | `["<cod client>", ...]`; rădăcina are și `selectedClientCode` |
| `get-consumption-locations` | `{clientCode}` | `ConsumptionPointInfo[]`: `ConsumptionClientAddress`, `ConsumptionInstallation`, `ConsumptionPointCode`, `ConsumptionMeters[]` |
| `get-contracts` | `{clientCode}` | `ContractInfo[]`: `ContractNumber`, `ContractNumberWithAnb`, `ContractStartDate`, `Type`, `Installation`, `ConsumptionPointCode`, `AddressConsumptionPoint`, `MeterSeries[]` |
| `get-last-index` | `{clientCode, meterSernr}` | `MeterReadingDetails`: `LastIndex`, `LastIndexDate`, **`AdatsollMin`** (început perioadă index), **`Adatsoll`** (sfârșit), `Inperioada` (flag 1 caracter), `IsSmart`, `Sernr`, `ConsumptionPointAddress` |
| `get-index-history` | `{clientCode, meterSernr, consumptionPointCode}` | `IndexHistory[]`: `StartDate`, `EndDate`, `Index` (string numeric), `Consumption` (număr), `Type`; `GraphicDataset {Dates[], Values[]}`. Utilizatorul are 44 de intrări (din ian. 2023) |
| `get-last-invoice-and-total-payments` | `{clientCode}` | `LastInvoiceDetails` (factură) și `TotalPaymentsSum` (total de plată) |
| `get-unpaid-invoices` | `{clientCode}` | `UnpaidInvoices[]` (factură) |
| `get-invoices` | `{clientCode, year}` | `PaidInvoices[]` (factură) pentru anul cerut |
| `get-payments` | `{clientCode}` | `Payments[]`: `PaymentDate`, `PaidAmount`, `PaymentType`, `DocumentNumber`, `Sold` |
| `save-index` | `{clientCode, adatsoll, anlage, zwnummer, index, matnr, sernr, equnr}` — toate în afară de `index` vin din `MeterReadingDetails` (`Adatsoll`, `Anlage`, `Zwnummer`, `Matnr`, `Sernr`, `Equnr`) | trimiterea indexului; portalul permite doar dacă `IsSmart == false` **și** `Inperioada == "X"`; index max. 6 cifre, fără litere |

Obiectul „factură”: `InvoiceNumber`, `DateIn` (emitere), `DueDate`, `Total`
(string), `Sold` (string), `SoldTotal` (număr), `Status`, `SapStatus`, `Type`,
`LastPayDate`, `PayUTransactionDate`, `Downloadable`. Datele „goale” vin ca
`0000-00-00` și trebuie tratate ca lipsă.

Valori observate pe contul utilizatorului (2026-11-24):
- Facturi plătite: `SapStatus = "Achitata"`, `Status` `"00"`/`"03"`, `Type = "u"`.
  Factură neplătită: `SapStatus = ""`, `Status = "00"`. Starea „plătită” se
  decide după lista din care vine factura (`PaidInvoices` vs `UnpaidInvoices`),
  nu după `Status`.
- `get-invoices` are date pentru 2023, 2024, 2025, 2026 (2022 gol) — istoric
  complet de la începutul contractului (2023-02-27).
- `IndexHistory` și `Payments` vin în ordine **descrescătoare** (cel mai nou primul).
  `IndexHistory[].Type` observat: doar `"citire"`. `Consumption` e în **m³**
  (valori lunare 7–15).
- `Inperioada = "X"` înseamnă „în perioada de autocitire”; gol în afara ei.
- `IsSmart = true` pe contorul utilizatorului → portalul **nu** permite
  trimiterea indexului pentru el (se citește de la distanță).
- `PaymentType` observat: `"Incasare PayU"`, `"Incasari PAGO"`.

Endpoint-urile **nu se apelează niciodată**: `invoices-payment`,
`total-invoices-payment`, `set-default-client-code`, `save-user-data`,
`new-password`, `new-client-code`, `logout` (sesiunea expiră singură; închiderea
contextului de browser e suficientă).

## 5. Arhitectura

```
Home Assistant OS
 ├─ integrarea custom_components/veolia_vrsi
 │     config flow (email+parolă) → coordinator (la 6 h) → senzori, buton, acțiune
 │                   │  HTTP pe rețeaua internă hassio + token
 │                   ▼
 └─ add-on veolia_bridge (Chromium headless, Playwright)
       pornește browserul → login → fetch() din pagină → închide browserul
                         │
                         ▼
               clienti-vrsi.veolia.ro (AWS WAF)
```

### 5.1 Repository (un singur repo `ha-veolia`)

```
ha-veolia/
  repository.yaml              # face repo-ul sursă de add-on-uri
  veolia_bridge/               # add-on-ul
    config.yaml  build.yaml  Dockerfile  run.sh  app/  DOCS.md  CHANGELOG.md
  custom_components/veolia_vrsi/   # integrarea (instalabilă prin HACS/Marketplace)
  hacs.json
  dashboard/                   # dashboard + carduri grafic
  docs/                        # instalare, entități, depanare, întrebări
  tests/                       # pytest pentru parser și config flow
  tools/                       # test_bridge.py, genereaza_dashboard.py
  README.md  LICENSE.md
```

Un singur link de GitHub e adăugat de două ori: o dată în **Setări → Add-ons →
Add-on store → Repositories** (pentru bridge), o dată în Marketplace/HACS
(pentru integrare).

### 5.2 Add-on-ul `veolia_bridge`

- **Imagine**: Python 3 + Playwright + Chromium, arhitecturi `amd64` și
  `aarch64` (Playwright nu suportă armv7/i386).
- **Rețea**: server HTTP mic (aiohttp) pe portul 8099, **fără port mapat pe host**;
  accesibil doar din rețeaua internă Supervisor.
- **Descoperire**: add-on-ul se anunță prin Supervisor discovery
  (`discovery: [veolia_vrsi]` în `config.yaml`), trimițând `host`, `port` și un
  **token** generat la prima pornire și salvat în `/data`. Integrarea primește
  descoperirea (`async_step_hassio`) și reține host/port/token. Fallback: câmp
  URL manual în config flow.
- **Autentificare**: toate cererile cer `Authorization: Bearer <token>`.
- **Endpoint-uri**:
  - `GET /health` → versiune, stare browser.
  - `POST /snapshot` `{email, password}` → un singur JSON cu tot contul (vezi
    5.3). Durată tipică estimată 15–40 s.
  - `POST /submit-index` `{email, password, clientCode, meter, consumptionPoint, index}`
    → rezultatul `save-index`.
- **Ciclul browserului**: pornit la cerere, oprit după răspuns (nu ține
  memorie între actualizări). O singură operație simultan (lacăt); a doua cerere
  așteaptă. Opțional, cookie-urile (`storage_state`) pot fi păstrate **doar în
  memorie** câteva minute ca să evite două login-uri consecutive (ex. snapshot
  urmat de submit-index).
- **Flux**: `goto /login` (browserul trece singur de provocarea WAF) → așteaptă
  input-ul `#csrf_token` → `login-submit` prin `page.evaluate(fetch)` → navighează
  la `sumar` → citește CSRF nou → apelează endpoint-urile de citire tot prin
  `page.evaluate(fetch)` (același origin, aceleași cookie-uri).
- **Erori** (cod + mesaj în română, mapate în integrare):
  `auth` (credențiale greșite), `waf_blocked` (provocare nerezolvată / CAPTCHA
  detectat), `portal` (răspuns neașteptat / `success:false`), `timeout`.
- **Loguri**: fără parolă, fără date personale la nivel INFO.

### 5.3 Snapshot-ul (contractul add-on → integrare)

```json
{
  "fetched_at": "ISO-8601",
  "client_codes": ["..."],
  "accounts": {
    "<clientCode>": {
      "locations": [ConsumptionPointInfo...],
      "contracts": [ContractInfo...],
      "meters": {
        "<meterSernr>": {
          "consumption_point": "<ConsumptionPointCode>",
          "installation": "<ConsumptionInstallation>",
          "last_index": MeterReadingDetails,
          "index_history": [IndexHistory...]
        }
      },
      "last_invoice": LastInvoiceDetails,
      "total_to_pay": TotalPaymentsSum,
      "unpaid_invoices": [...],
      "paid_invoices": [...],          // toți anii de la începutul contractului
      "payments": [...]
    }
  }
}
```

Add-on-ul returnează datele portalului **neprelucrate** (doar grupate);
interpretarea e în `parser.py` din integrare, ca să poată fi testată fără browser.

### 5.4 Integrarea `veolia_vrsi`

Structură identică cu `premierenergy`: `api.py` (client către bridge),
`parser.py`, `coordinator.py`, `config_flow.py`, `sensor.py`,
`binary_sensor.py`, `button.py`, `entity.py`, `diagnostics.py`, `services.yaml`,
`strings.json`, `translations/{ro,en}.json`, `manifest.json`
(`iot_class: cloud_polling`, `dependencies: ["hassio"]`).

**Config flow**: (descoperire bridge sau URL) → email + parolă → validare prin
`/snapshot` → alegerea locurilor de consum (dacă sunt mai multe) → gata.
Opțiuni: interval actualizare (implicit **6 h**, interval 2–24 h) și locurile de
consum. Reauth la eroare `auth`. La `waf_blocked`, issue în Repairs cu
explicație.

**Dispozitiv** = un loc de consum (identificat prin `ConsumptionPointCode`).

**Entități** (nume în română, unități RON / m³):

| Entitate | Tip | Valoare | Atribute principale |
|---|---|---|---|
| Loc de consum | sensor | adresa | cod client, cod loc consum, instalație, contoare, contract, tip, data început |
| Consum ultima lună | sensor m³ (`water`) | consumul ultimei perioade | perioada, tip citire, `istoric` (24 luni), `consum_anual` |
| Consum an curent | sensor m³ | suma pe anul curent | totaluri pe fiecare an |
| Ultimul index | sensor m³ | `LastIndex` | data, contor, smart |
| Total de plată | sensor RON | `TotalPaymentsSum` | rest facturi, restanță, următoarea scadență |
| Facturi neplătite | sensor (număr) | count | listă facturi |
| Facturi plătite | sensor (număr) | count pe ultimele 12 luni | ultimele 12 facturi, totaluri plătite pe fiecare an |
| Ultima factură | sensor RON | `Total` | număr, emitere, scadență, sold |
| Următoarea scadență | sensor `date` | cea mai apropiată `DueDate` neplătită | — |
| Ultima plată | sensor RON | ultima plată | data, tip |
| Perioadă transmitere index | sensor text | „21–25 nov. 2026” | început, sfârșit |
| Început / sfârșit perioadă index | sensor `date` | `AdatsollMin` / `Adatsoll` | — |
| Transmitere index permisă | binary_sensor | `Inperioada == "X"` și contorul nu e smart | `contor_smart`, început, sfârșit |
| Factură restantă | binary_sensor | există factură neplătită cu scadența depășită | — |
| Actualizare date | button | forțează snapshot | — |

**Acțiune** `veolia_vrsi.trimite_index` (`contor`, `index`): aplică aceleași
reguli ca portalul — refuză cu mesaj clar dacă contorul e smart, dacă
`Inperioada != "X"` sau dacă indexul are mai mult de 6 cifre. Pentru contorul
smart al utilizatorului acțiunea va refuza mereu; o păstrăm pentru conturile cu
contor clasic. Senzorul „Transmitere index permisă” e `off` pentru contoare smart,
cu atributul `contor_smart: true`.

**Statistici pentru grafic**: la fiecare actualizare, istoricul lunar se
importă ca statistici externe (`async_add_external_statistics`,
`veolia_vrsi:consum_apa_<loc>`, m³, cu `sum` cumulat). Perioadele de citire
nu coincid cu lunile calendaristice (ex. 29 sep – 28 oct), așa că fiecare
perioadă se atribuie **lunii în care se termină** (`EndDate`) și se scrie la
ora 00:00 a primei zile din acea lună (ora locală). Dacă două perioade cad în
aceeași lună, se adună. Senzorii de consum nu au `state_class`, ca să nu
dubleze statisticile importate. Astfel cardul standard **Statistics graph** arată consumul pe
**lună** și pe **an** fără add-on-uri de frontend, cu tot istoricul de la 2023.

**Dashboard** (`dashboard/`): generat cu `tools/genereaza_dashboard.py`, ca la
Premier Energy, cu:
- carduri de sumar (total de plată, scadență, perioadă index);
- grafic lunar (Statistics graph, `period: month`) și anual (`period: year`);
- variantă ApexCharts din atributul `istoric` (opțional).

## 6. Teste și verificare

- `tests/`: parser pe fixture-uri JSON **anonimizate** (cod client, adrese,
  numere factură înlocuite), config flow cu bridge mock-uit, statistici.
- `tools/test_bridge.py`: rulează `/snapshot` contra unui bridge real (local cu
  Docker sau în HA) și afișează un rezumat fără date personale.
- Verificare finală: add-on instalat pe HA-ul utilizatorului, integrarea
  configurată, entitățile și graficele verificate de utilizator.

## 7. Riscuri

- **WAF înăsprit / CAPTCHA pentru headless** → bridge-ul nu mai obține date.
  Atenuare: mesaj clar + issue în Repairs; nu se încearcă ocolirea.
- **Memorie**: Chromium ~300–500 MB în timpul unui snapshot pe un Raspberry Pi
  cu puțin RAM poate fi problematic.
- **Imaginea add-on-ului e mare** (~600 MB–1 GB cu Chromium); prima instalare
  durează.
- **Schimbări în portal** (nume endpoint-uri / câmpuri) → se repară parser-ul
  sau bridge-ul.

## 8. Decizii luate de mine (verifică-le)

- Domeniul integrării `veolia_vrsi` (nu `veolia`, folosit deja de integrarea
  comunității pentru Veolia Franța).
- Add-on-ul se numește `veolia_bridge`, port intern 8099, descoperire Supervisor + token.
- Interval implicit 6 h (≈ 4 actualizări pe zi).
- Facturi plătite: se citesc toți anii de la începutul contractului (4 cereri
  `get-invoices` azi, câte una pe an).
- Credențialele trăiesc doar în config entry-ul integrării; sunt trimise
  bridge-ului la fiecare cerere.
- Graficul principal prin statistici externe + Statistics graph; ApexCharts
  rămâne opțional.
- PDF-urile de factură și plata din HA nu intră în v1.

## 9. Lăsat constructorului

- Detaliile Dockerfile (imagine de bază Playwright vs. instalare peste baza HA).
- Timeout-uri exacte, reîncercări, cât timp se păstrează cookie-urile în memorie.
- Fixture-urile anonimizate pentru teste: construite după structurile din
  secțiunea 4 (au fost observate pe contul real, dar nu au fost salvate).
