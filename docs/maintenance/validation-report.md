# Validation report — documentation audit

**Date:** 2026-10-23  
**Branch:** `main`  
**Workspace:** `D:\o-form`

## Commands run

### Legal file presence

Checked existence of:

- `COPYING`
- `AUTHORS`
- `doc/license/GPL-license.txt`
- `release/license/license.md`
- `release/license/licenses.json`
- `release/text/copyright.txt`
- `release/text/readme.html`

**Result:** All present.

### Relative link check (Markdown under `docs/`, root README, CONTRIBUTING, `.github/README.md`)

Parsed `](…)` targets; resolved relative to each file; skipped `http(s):` and `mailto:`.

**Result:** All internal targets resolve after this report file was added. An initial check failed only on the then-missing `docs/maintenance/validation-report.md` (self-reference from the index) — resolved by creating this file.

### Product-facing GitHub leftovers

Searched `.github/README.md` and `.github/pull_request_template.md` for `projects.blender.org`, `fund.blender.org`, and “GitHub mirror” as an active mirror workflow.

**Result:** No contribution routing to projects.blender.org. `.github/README.md` states this repository is **not** the Blender Foundation mirror (intentional disclaimer). `FUNDING.yml` removed.

### AUTHORS integrity

Confirmed the file still identifies itself as the Blender authors list; only a comment block was added.

### Install-tree sync

Copied updated `brand.py` / `ui.py` into  
`D:\build_windows_OForm_x64_vc17_Release\bin\Release\5.2\scripts\startup\bl_app_templates_system\oform\`  
and cleared `__pycache__` when that install tree exists.

### Not run (limitations)

| Check | Reason |
| --- | --- |
| Sphinx / Doxygen doc build | Not required for O-Form product docs; inherited generators unchanged; heavy dependency |
| Full C++ rebuild | Documentation / Python branding only |
| `oform` selftest this pass | No mesh/tool logic changed; last known contract remains prior successful run |
| Exhaustive `rg Blender` over all of `source/` | Intentionally avoided; Class C technical names must remain |
| Formal license counsel review | Out of scope; see legal-preservation-review.md |
| GitHub repository settings API | Task forbids modifying repository settings this pass |

## Diff hygiene

Expected change set: documentation tree, README, CONTRIBUTING, `.github` product metadata, AUTHORS comment, `brand.py` / `ui.py` principle string. No bulk renames of Blender symbols.

## Conclusion

Documentation audit validation for **link resolution**, **legal file presence**, and **GitHub product-facing cleanup** completed with the limitations above. Do not treat this as a full license compliance certification.
