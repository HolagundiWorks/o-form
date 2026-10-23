# Remaining Blender references — classification

**Audit date:** 2026-10-23  
**Method:** Targeted inventory of documentation, packaging, GitHub metadata, and product modules. Not a blind repository-wide string replace. Millions of technical identifiers in `source/` correctly retain Blender names.

## Class A — Product-facing (updated this pass)

| Location | Notes |
| --- | --- |
| `README.md` | O-Form product README |
| `docs/**` | New O-Form documentation tree |
| `CONTRIBUTING.md` | O-Form contribution entry |
| `.github/README.md` | Was Blender mirror README; now O-Form |
| `.github/pull_request_template.md` | Was projects.blender.org; now O-Form |
| `.github/FUNDING.yml` | Removed (was fund.blender.org) |
| `release/text/readme.html` | O-Form end-user readme (prior pass) |
| `scripts/.../oform/brand.py`, `ui.py` | Product strings / About |

## Class B — Legal (preserved)

| Location | Why it stays |
| --- | --- |
| `COPYING` | Canonical GPL pointer / Blender Foundation notice |
| `AUTHORS` | Blender copyright author list (comment note added only) |
| `doc/license/*` | License texts |
| `release/license/*` | Third-party notices |
| `release/text/copyright.txt` | Blender copyright + O-Form product lines |
| SPDX `Blender Authors` headers | Required attribution |

## Class C — Technical (must remain accurate)

| Location | Why it stays |
| --- | --- |
| `bpy`, `bl_app_templates_system`, DNA, RNA | API / module names |
| `blender.exe` target name | Build system; `oform.exe` is a copy |
| `.blend` extension | File format |
| `BLENDER_VERSION` 5.2.3 LTS | Library / format compatibility |
| `doc/python_api/**`, `doc/doxygen/**` | Inherited generators documenting Blender APIs |
| `doc/manpage/blender.1.py` | Man page for `blender` binary name |
| `make`, `build_files/**` Blender paths | Build tooling |
| `lib/windows_x64` layout | Prebuilt dependency tree |
| CMake `WITH_*` and Blender options | Build graph |

## Class D — Historical

| Location | Why it stays |
| --- | --- |
| Git history / Blender release commits | Provenance |
| `release/lts/README.md` and similar | Inherited packaging notes |
| Changelogs under Blender paths | Historical |

## Class E — External links

| Former / remaining | Action |
| --- | --- |
| developer.blender.org / projects.blender.org in `.github` | Removed from product GitHub templates |
| blender.org in legal / provenance docs | Kept where attributing origin |
| Blender manual / community links in nested READMEs | Left in inherited trees; not product entry points |

## Class T — Third-party / vendored

`extern/**`, `lib/**` READMEs and licenses — unchanged.

## Outstanding product-facing Blender chrome

| Item | Class | Status |
| --- | --- | --- |
| Executable / title-bar icon art | A | Still Blender assets in binary |
| C About dialog large Blender logo icon | A | Still `ICON_BLENDER_LOGO_LARGE` in splash C++ |
| Win AppId friendly name in CMake | C/A | Still “Blender x.y” for Windows app id strings |

These are tracked as outstanding; changing them requires asset and CMake review beyond documentation.
