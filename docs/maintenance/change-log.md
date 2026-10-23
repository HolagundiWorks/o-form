# Documentation audit change log

**Pass date:** 2026-10-23

## Added

- `docs/README.md`
- `docs/user/overview.md`
- `docs/developer/architecture.md`
- `docs/build/windows.md`
- `docs/licensing/attribution.md`
- `docs/maintenance/documentation-audit-inventory.md`
- `docs/maintenance/legal-preservation-review.md`
- `docs/maintenance/blender-references-classification.md`
- `docs/maintenance/validation-report.md`
- `docs/maintenance/change-log.md`
- `CONTRIBUTING.md`

## Modified

- `README.md` — full O-Form product landing with docs index and verified status
- `.github/README.md` — replaced Blender mirror text
- `.github/pull_request_template.md` — O-Form PR checklist
- `AUTHORS` — header comment only (Blender names preserved)
- `scripts/startup/bl_app_templates_system/oform/brand.py` — `PRINCIPLE` string
- `scripts/startup/bl_app_templates_system/oform/ui.py` — About/splash show principle

## Removed

- `.github/FUNDING.yml` — removed Blender Foundation funding redirect (no replacement URL invented)

## Intentionally left unchanged

- `COPYING`, `doc/license/**`, `release/license/**`
- `release/text/readme.html`, `release/text/copyright.txt` (already O-Form from prior pass)
- Inherited `doc/python_api/**`, `doc/doxygen/**`, nested Blender READMEs under `build_files/`, `tools/`, `tests/`, `extern/`, `lib/`
- Git remotes, branches, tags, history
- C++ symbol names, `bpy`, executable target `blender`
