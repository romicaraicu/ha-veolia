# Referință entități

Entity ID-urile au forma `<platformă>.veolia_vrsi_<cod_loc_consum>_<cheie>`, de exemplu `sensor.veolia_vrsi_4000000001_total_de_plata`.

## Senzori

| Cheie | Nume | Valoare | Atribute |
|---|---|---|---|
| `loc_consum` | Loc de consum | adresa | `cod_client`, `cod_loc_consum`, `instalatie`, `contoare`, `contract`, `tip_contract`, `inceput_contract` |
| `consum_ultima_luna` | Consum ultima lună | m³ din ultima perioadă de citire | `de_la`, `pana_la`, `luna`, `m3`, `index`, `tip`, `consum_anual` (pe ani), `istoric` (ultimele 24 de perioade) |
| `consum_an_curent` | Consum an curent | m³ în anul curent | — |
| `ultimul_index` | Ultimul index | m³ | `data`, `contor`, `contor_smart` |
| `total_de_plata` | Total de plată | lei | `restant`, `urmatoarea_scadenta`, `facturi_neplatite` |
| `facturi_neplatite` | Facturi neplătite | număr | `total_rest_plata`, `restant`, `facturi` (listă) |
| `facturi_platite` | Facturi plătite | număr, în ultimele 12 luni | `facturi` (max. 12), `total_pe_an` |
| `ultima_factura` | Ultima factură | lei | `numar`, `emisa`, `scadenta`, `total`, `rest_plata`, `platita_la` |
| `urmatoarea_scadenta` | Următoarea scadență | dată | — |
| `ultima_plata` | Ultima plată | lei | `data`, `suma`, `tip` |
| `perioada_index` | Perioadă transmitere index | text, ex. `21–25 nov. 2026` | `inceput`, `sfarsit`, `contor_smart` |
| `perioada_index_inceput` | Început perioadă index | dată | — |
| `perioada_index_sfarsit` | Sfârșit perioadă index | dată | — |

O factură din listă are forma:

```yaml
numar: VRS000000003
emisa: "2026-11-03"
scadenta: "2026-11-18"
total: 258.54
rest_plata: 258.54
platita_la: null
```

## Senzori binari

| Cheie | Nume | `on` când |
|---|---|---|
| `perioada_index_activa` | Transmitere index permisă | portalul e în perioada de autocitire **și** contorul nu e smart |
| `factura_restanta` | Factură restantă | există o factură neplătită cu scadența depășită |

## Buton

| Cheie | Nume | Ce face |
|---|---|---|
| `actualizare` | Actualizare date | cere imediat datele de la portal (prin add-on) |

## Statistici

`veolia_vrsi:consum_apa_<cod_loc_consum>` (m³): câte o valoare pe lună, cu tot istoricul din portal. Se folosește în cardul **Statistics graph** cu `stat_types: [change]` și `period: month` sau `period: year`.

## Acțiunea `veolia_vrsi.trimite_index`

```yaml
action: veolia_vrsi.trimite_index
data:
  contor: 22AA000001
  index: 1234
```

Refuză cu un mesaj clar dacă contorul e smart, dacă nu ești în perioada de autocitire sau dacă indexul are mai mult de 6 cifre. Întoarce `{contor, index, mesaj}`.
