# O-Form documentation audit inventory

**Audit date:** 2026-10-23  
**Repository:** [HolagundiWorks/o-form](https://github.com/HolagundiWorks/o-form)  
**Branch audited:** `main`  
**Upstream Blender snapshot (verified):** 5.2.3 LTS  
- `source/blender/blenkernel/BKE_blender_version.h`: `BLENDER_VERSION 502`, patch `3`, cycle `release`, suffix `LTS`  
- Git ancestry includes commit `e13b728c688` (“Release: Bump to 5.2.3 release”)  
- No Blender remote is configured (independent repository)

**Branding principle (product):** Open Source. Built for Architects. Driven by Community.

This inventory classifies documentation and documentation-related branding. Legal preservation takes priority over rebranding.

## Classification key

| Class | Meaning |
| --- | --- |
| A | Product-facing — prefer O-Form / OSAS identity |
| B | Legal — preserve copyrights, licenses, notices |
| C | Technical — keep Blender/API/build identifiers accurate |
| D | Historical — leave changelogs / provenance |
| E | External link — update only when an O-Form destination exists |
| T | Third-party / vendored — do not rebrand |
| G | Generated tooling — leave unless generators are retargeted |

## Root and packaging

| Path | Purpose | Class | Required change | Sensitivity | Verification |
| --- | --- | --- | --- | --- | --- |
| `README.md` | Product landing | A | Keep polished O-Form README; link into `docs/` | Low | Human review; link check |
| `COPYING` | Points to GPL text; Blender Foundation notice | B | **Leave** | High | Diff against baseline |
| `AUTHORS` | Blender author list for copyright | B | Optional short O-Form note; **do not replace names** | High | Diff |
| `release/text/readme.html` | Shipped end-user readme | A | O-Form (already updated) | Medium | Install tree copy |
| `release/text/copyright.txt` | Packaged copyright | B+A | O-Form lead-in + Blender copyright retained | High | Diff |
| `doc/license/*` | Canonical license texts | B | **Leave** | High | File presence |
| `release/license/license.md` | Third-party overview | B | **Leave** (Blender-era inventory) | High | Diff |
| `release/license/licenses.json` | Machine-readable licenses | B | **Leave** | High | Diff |

## GitHub metadata

| Path | Purpose | Class | Required change | Sensitivity | Verification |
| --- | --- | --- | --- | --- | --- |
| `.github/README.md` | Still Blender mirror README | A | Replace with O-Form pointer to root README | Medium | Content review |
| `.github/pull_request_template.md` | Points to projects.blender.org | A | O-Form PR guidance | Medium | Content review |
| `.github/FUNDING.yml` | Blender Foundation funding URL | A/E | Remove Blender fund redirect (no invented HCW URL) | Medium | YAML parse |
| Issue forms / SECURITY / CODE_OF_CONDUCT | Absent | — | Not fabricated this pass | — | Glob |

## Application branding (in scope)

| Path | Purpose | Class | Required change | Sensitivity | Verification |
| --- | --- | --- | --- | --- | --- |
| `scripts/.../oform/brand.py` | Colors, product strings | A | Align principle / suite strings | Low | Launch / About |
| `scripts/.../oform/ui.py` | Menus, About, splash, status | A | Use brand constants | Low | Launch |
| `source/.../wm_window.cc` | Window title “O-Form” | A | Already set; leave unless wrong | Medium | Build |
| `source/.../wm_splash_screen.cc` | About label O-Form | A | Already set | Medium | Build |
| `source/.../wm_files.cc` | Default app template `oform` | C | Leave | Medium | Runtime |
| `build_files/cmake/config/oform.cmake` | Lite build | C | Leave | Medium | Build |
| Title-bar exe icon / C About logo | Still Blender assets in binary | A | **Outstanding** (art/binary work) | Medium | Visual |

## Inherited documentation (leave or index only)

| Path | Purpose | Class | Action |
| --- | --- | --- | --- |
| `doc/python_api/**` | Sphinx bpy API docs | C/G | Leave; index as inherited |
| `doc/doxygen/**` | Doxygen config | C/G | Leave |
| `doc/blender_file_format/**` | `.blend` format notes | C/D | Leave |
| `doc/manpage/blender.1.py` | man page generator | C | Leave (executable still blender) |
| `build_files/*/README.md` | Build-system notes | C | Leave |
| `tools/readme.rst` | Tools tree | C | Leave |
| `release/{darwin,lts,pypi,snap,msix}/README*` | Platform packaging for Blender | C/E | Leave; Windows-first product |
| `tests/**/readme*` | Test fixtures | C | Leave |
| `extern/**`, `lib/**` READMEs | Vendored | T | Leave |
| `scripts/addons_core/*/README*` | Stock add-ons | C/T | Leave |

## New O-Form documentation (this audit)

| Path | Purpose |
| --- | --- |
| `docs/README.md` | Documentation index |
| `docs/user/overview.md` | User-facing modelling overview |
| `docs/developer/architecture.md` | Layout and extension points |
| `docs/build/windows.md` | Windows build guide |
| `docs/licensing/attribution.md` | Attribution index (no license replacement) |
| `docs/maintenance/documentation-audit-inventory.md` | This file |
| `docs/maintenance/legal-preservation-review.md` | Legal review |
| `docs/maintenance/blender-references-classification.md` | Remaining Blender refs |
| `docs/maintenance/validation-report.md` | Validation results |
| `docs/maintenance/change-log.md` | Files touched this pass |
| `CONTRIBUTING.md` | Contribution entry |

## Intentionally unchanged (high sensitivity)

- `COPYING`, `AUTHORS` body of Blender names, `doc/license/*`, `release/license/*`
- Per-file `SPDX-FileCopyrightText: … Blender Authors` headers
- Internal target names (`blender.exe`, `bpy`, `bl_app_templates_system`)
- File format `.blend`
- Git remotes, tags, history (per task rules)
