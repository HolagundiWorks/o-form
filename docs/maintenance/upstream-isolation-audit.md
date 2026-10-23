# Upstream isolation audit

**Date:** 2026-10-23  
**Repository:** https://github.com/HolagundiWorks/o-form  
**Branch:** `main`  
**Policy:** No Blender upstream. No upstream merges. No upstream synchronization. No upstream development dependency.

## Baseline (before this pass)

| Check | Result |
| --- | --- |
| `git remote -v` | Only `origin` → `https://github.com/HolagundiWorks/o-form.git` |
| `.github/workflows/` | **Absent** — no CI upstream sync jobs |
| Canonical developer doc | `docs/developer/architecture.md` (architecture-focused; expanded this pass) |
| Contribution doc | `CONTRIBUTING.md` (already forbade adding Blender upstream) |

## Findings classification

| Finding | Class | Action |
| --- | --- | --- |
| No Blender source remote on `origin` | — | Keep |
| `build_files/utils/make_update.py` can create `lfs-fallback` to `projects.blender.org/blender/blender.git` for **LFS** | Optional tooling / dependency fetch | Document: asset fallback only; remove after use; independence checker **warns** |
| `build_files/cmake/example_scripts/cmake_linux_install.sh` clones Blender | Historical example script | Leave in tree; not O-Form onboarding |
| `build_files/build_environment/**` URLs to projects.blender.org for lib packages | Third-party / lib download | Leave; not source merge |
| `tools/triage/*`, `release/release_notes/*` projects.blender.org APIs | Historical Blender release tooling | Leave; not wired into O-Form product workflow |
| `release/windows/batch/*.cmd` “report bug on projects.blender.org” | Obsolete product-facing string in Blender debug launchers | Left this pass (not O-Form `oform.exe` entry); tracked as optional cleanup |
| `docs/**`, `CONTRIBUTING.md` provenance mentions of Blender | Required legal / historical attribution | Preserve |
| SPDX / `AUTHORS` / `COPYING` / `release/license/**` | Required legal | Preserve |
| Internal `bpy`, `BLENDER_VERSION`, `.blend` | Technical identifiers | Preserve |

## Active upstream synchronization

**None found** in GitHub Actions or O-Form product docs. No scheduled workflow fetches or merges Blender source into this repository.

## Changes this pass

- Expanded [developer guide](../developer/architecture.md) with independence policy and remotes workflow  
- Expanded [CONTRIBUTING.md](../../CONTRIBUTING.md)  
- Added [releases.md](../developer/releases.md)  
- Added `tools/oform_check_independence.py`  
- Updated documentation index and build notes  

## Legal preservation

Independence does not authorize deleting copyright notices, changing licenses, or claiming the code has no Blender provenance. See [legal-preservation-review.md](legal-preservation-review.md).
