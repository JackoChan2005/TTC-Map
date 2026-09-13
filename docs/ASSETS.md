# Assets and publication status

The repository has no project-wide open-source license selected by its owners.
No new reuse rights are asserted here. Contributors must confirm the intended
license and individual contribution attribution before adding a project license.

## Hardware libraries

Integrated PCB/schematic designs remain in `hardware/`. Their placed footprints
and embedded schematic symbols remain part of those designs. The separately
downloaded model files have been removed from the tracked working tree because
the included SnapMagic Design License distinguishes integrated designs from
standalone model redistribution. License notices are retained under
`hardware/My-Custom-Footprints.pretty/`.

For library editing, obtain the relevant symbols/footprints/models from the
original provider under its terms. Required part families include ESP32-DEVKIT-V1,
SN74HC595, BSS84, C0603C104K5RACTU, CL05A104KA5NNNC and JMK105BJ105KV-F.
Set KiCad's `TTC_MODEL_DIR` path variable to your local library directory, keeping
the subfolder structure shown in `hardware/sym-lib-table`. The footprint table
uses that directory as a `.pretty` library. Board viewing does not require replacing
placed footprints; missing optional models affect external library/3D operations.
Standard KiCad libraries must be installed separately.

On the original development machine, removed files were preserved under ignored
`data/private-assets/hardware/My-Custom-Footprints.pretty`. They are not licensed
for redistribution by this document. Prior Git history still contains them;
permission or a separately approved history/publication strategy remains necessary.

## UI images

The two original design-reference JPGs are preserved only in ignored local storage
pending author/provenance confirmation. The written root design document remains.
The README image is an actual TTC-Map browser capture from September 12, 2026;
its counts and source labels record that session, not current observations.

The screenshot contains OpenStreetMap imagery and visible contributor attribution.
The map uses the public OSM tile service with normal browser caching and visible
[OpenStreetMap attribution](https://www.openstreetmap.org/copyright). Transit
station/schedule data comes from Toronto Open Data, with NTAS observations where
available. Do not remove those attributions or claim that TTC endorses the project.
No downloaded font package is bundled; the UI uses available system fonts.

## Local credentials

Legacy `TTC/`, `node-api/`, `.pio`, dependency folders, environment overrides and
secrets headers are ignored. They were not deleted or published by this cleanup.
The earlier audit found a Wi-Fi literal in a local capture tree and compiled
firmware, not in the branch commits inspected. A normal branch push and a full
folder/.git archive have different exposure boundaries.

The owner must confirm whether those local files were ever shared. If exposure
occurred or is uncertain, rotate the Wi-Fi credential first and then clean shared
copies and local capture metadata. This cleanup neither rotates router credentials
nor rewrites protected tool capture refs or published Git history.
