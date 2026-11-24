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

### Din PDF-ul facturii (de la 0.2.0)

Add-on-ul descarcă fiecare factură o singură dată (câte cel mult 6 la o actualizare, de la cea mai nouă), deci la prima instalare istoricul complet se adună în câteva actualizări.

| Cheie | Nume | Valoare | Atribute |
|---|---|---|---|
| `tarif_apa` | Tarif apă | lei/m³, fără TVA, de pe ultima factură | `factura`, `luna`, `de_la`, `pana_la`, `istoric` |
| `tarif_canalizare` | Tarif canalizare | lei/m³, fără TVA | la fel |
| `pret_mc_facturat` | Preț pe m³ facturat | total factură (cu TVA, apă + canalizare) / m³ de apă facturați | la fel; `istoric` are prețul pe fiecare lună |
| `cost_efectiv_mc` | Cost efectiv pe m³ | total factură / consumul contoarelor tale (include partea din condominiu) | la fel |
| `apa_facturata` | Apă facturată | m³ de apă de pe factură | la fel |
| `diferenta_facturata` | Diferență facturată față de contor | m³ facturați peste consumul contoarelor tale | la fel |

**Contoarele sunt citite din factură**, nu sunt fixate nicăieri: pentru fiecare serie găsită (contorul tău, contorul de condominiu sau oricâte altele) apar două entități, iar un contor nou apare automat când e pe o factură:

| Cheie | Nume | Valoare | Atribute |
|---|---|---|---|
| `contor_<serie>_consum` | Consum contor &lt;serie&gt; (&lt;tip&gt;) | m³ pe ultima factură | `serie`, `tip` (`individual`, `condominiu`…), `index_nou`, `index_vechi`, `stabilit_prin`, `motiv`, `data`, `consum_lunar` |
| `contor_<serie>_index` | Index contor &lt;serie&gt; (&lt;tip&gt;) | indexul nou | la fel, fără `consum_lunar` |

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

| Statistică | Unitate | Ce conține |
|---|---|---|
| `veolia_vrsi:consum_apa_<cod_loc_consum>` | m³ | consumul lunar din portal, cu tot istoricul |
| `veolia_vrsi:contor_<serie>` | m³ | consumul lunar al fiecărui contor de pe facturi |
| `veolia_vrsi:apa_facturata_<cod_loc_consum>` | m³ | apa facturată pe lună |
| `veolia_vrsi:pret_mc_<cod_loc_consum>` | lei/m³ | prețul pe m³ facturat, pe lună (medie) |

Pentru m³ folosește cardul **Statistics graph** cu `stat_types: [change]` și `period: month` sau `period: year`; pentru preț, `stat_types: [mean]`.

## Acțiunea `veolia_vrsi.trimite_index`

```yaml
action: veolia_vrsi.trimite_index
data:
  contor: 22AA000001
  index: 1234
```

Refuză cu un mesaj clar dacă contorul e smart, dacă nu ești în perioada de autocitire sau dacă indexul are mai mult de 6 cifre. Întoarce `{contor, index, mesaj}`.
