# HCDB + CMO: modern platforms for Harpoon Classic / HUCE

Tools that convert platforms from the **Command: Modern Operations (CMO)** database into the
**Harpoon Classic / Harpoon Ultimate Commanders Edition** platform database (`commondb.res`),
on top of HarpGamer's **HCDB-250724**.

| | Count |
|---|---|
| New platforms | **1,247** (436 ships, 62 subs, 749 aircraft) |
| New weapons / sensors | 429 weapons, 276 radars and sonars |
| Countries with new platforms | 134 (44 added to the country list) |
| Existing rows changed | 98 (country names, regenerated US-batch loadouts) |

The full list is in [`docs/HCDB_CMO_additions_catalog.xlsx`](docs/HCDB_CMO_additions_catalog.xlsx).

## What was added

1. **United States, 2015+**: 89 ships, subs and aircraft (Ford, Constellation, Burke Flt III, Virginia Blk V, F-35, B-21, MQ-25 …).
2. **China, Russia, North and South Korea, Japan, NATO members, 2015+**: 285 platforms.
3. **India, Israel, Iran, Australia, Taiwan, plus transports, tankers, ELINT and utility types for the US, China, Russia and NATO**: 224 platforms.
4. **Every other country in CMO with 2015+ equipment**: 512 platforms.
5. **Older ships and subs (in service 1980+) for countries Harpoon Classic never had**: 137, including Argentina's 1982 fleet (Belgrano, 25 de Mayo, Type 42, TR-1700), Brazil, Chile, Peru, Mexico, Cuba and others.

## How the conversion works

- Each new platform is **cloned from the closest existing HCDB entry**, which supplies its picture, flags and basic handling. Its mounts, magazines, sensors, loadouts, displacement, damage points and speed are then **rebuilt from CMO**.
- Weapons and sensors are matched to existing HCDB items where possible. When there is no match, a new item is cloned from the nearest analog, with range, speed and Ph scaled by the CMO ratio.
- Damage points follow the HCDB formula. Name and array limits are enforced: 4 weapons per multi-weapon group, 8 weapons per loadout, and classname length limits.
- **Aircraft loadouts** are chosen for mission variety first, then by greedy coverage of every carriable weapon, up to 10 per aircraft. Identical loadouts are shared, because the loadout annex is the tightest limit: 4,096 IDs.
- All new IDs use free slots in each annex. No existing platform, weapon or sensor row is changed except the ones listed on the "Modified existing" sheet.
- New country names are written into empty slots in the `CountryName` battleset string.
- The database is built with HCDB's own `db_utils` (`db_make load`, `res_add_headers`, `res_implode`) under Wine, with one fix-up: byte 118 of each ship record is set to 115. The result is checked by exploding it again and comparing all CSVs byte for byte.

## Rebuilding

You need your own copies of:

- HUCE
- HCDB-250724 with its `db_utils`
- a CMO DB3000 CSV export

The scripts expect this layout:

```
~/w/cmo/            CMO CSV export (1_Lookup_Tables, 2_Core_Entities, 3_Junction_Tables, DB3K_*.csv)
~/w/hc/res/         HCDB-250724 CSVs (from start_edit.bat)
~/kit/              HCDB kit: db_utils/*.exe + commondb/res/
```

Copy `config/*.json` into `~/w`, then from `~/w`:

```bash
python3 tools/extract.py && python3 tools/build.py && python3 tools/merge.py   # US batch -> ~/w/out/res
mkdir -p base2 && cp hc/res/* base2/ && cp out/res/* base2/                   # base2 = HCDB + US batch
python3 tools/extract5.py              # platforms5.json, used5.json from config/selection2-5.json
python3 tools/automatch5.py            # auto_maps5.json (or use the one in config/)
python3 tools/build5.py                # built5.json  (LO_CAP=10 by default)
python3 tools/make_base4.py
python3 tools/merge5.py && python3 tools/validate5.py
rm -rf ~/nb && cp -r ~/kit ~/nb && cp ~/w/out5/res/*.csv ~/nb/commondb/res/ && tools/kit_build.sh ~/nb
```

`kit_build.sh` needs 32-bit Wine (`wine32`, `WINEPREFIX=~/.wine32`). The `sel*.py` scripts show how the
selections in `config/` were made; you only need them to change what gets imported.

## Data and rights

- **No game or CMO data is in this repository**: no `.res`, no CSVs, no CMO export. The `.gitignore` keeps them out.
- CMO's database is © WarfareSims / Matrix Games. HCDB is the HarpGamer community database. Values produced by these tools are derived from CMO, so treat any built database as for personal use unless the rights holders agree otherwise.

## Status

Tested in HUCE: the Scenario Editor loads the database and new ships, subs and aircraft can be placed and played. Analog choices and weapon mappings are automatic, and some will be imperfect. Corrections are welcome.
