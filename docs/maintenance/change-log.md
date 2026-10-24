# Documentation audit change log

**Pass date:** 2026-10-23

## Later same day — pastel green suite rebrand + Delete

- Regenerated OSAS suite mark (C + arcs + centre ring) on pastel green `#C6E6D3` with ink strokes
- Assets: `mark.png`, `splash.png`, `mark.svg`, `app.ico`, `favicon.ico`, `file.ico`
- Windows `winblender.ico` / `winblenderfile.ico` + RC product strings → O-Form; freedesktop SVG icons
- `oform.delete_selection` on Delete key (and Edit menu) removes selected geometry / groups

## Later same day — SketchUp modelling foundation

- `inference.py`: working planes, ray–plane hit, snap priorities, guides/labels
- `selection.py`: ClickTracker + single/double/triple-click (and Alt+1/2/3)
- `solids.py` + `oform.boolean_*` / Inspect Solid; Solids menu and left pane
- Drawing tools (Line/Rect/Circle/Arc/Polygon) adopt plane on first click; preview shows inference cues
- Docs/user overview and selftest extended for plane, selection, Booleans

## Later same day — remove unused components (not hide)

- Unregister unused Blender UI modules (animation editors, physics, GP, sidebars)
- C++: do not create Properties nav bar / View3D tool-shelf / N-panel / asset shelf for oform
- Removed addons: `io_anim_bvh`, `pose_library`, `rigify`, `viewport_vr_preview`, `node_wrangler`, `hydra_storm`
- Removed system app templates: `2D_Animation`, `Sculpting`, `Storyboarding`, `VFX`, `Video_Editing`

## Later same day — O-Draft shell UI

- Light/dark theme toggle (status bar + Window); solid white/black canvas, no ground grid
- Left Properties + Ask panels; Ask overlay + Allow/Decline (`ai.py`)
- Docs/README status updated for shell parity with O-Draft

## Later same day — Groups and Components

- Added `scripts/startup/bl_app_templates_system/oform/groups.py`
- Wired Make Group (Ctrl+G), Make Component (G), enter/exit, explode, instance into `tools.py` / `ui.py`
- Extended selftest and `docs/user/overview.md` / root `README.md`

## Later same day — independence / developer guide

- Expanded `docs/developer/architecture.md` into the canonical developer guide (independence policy, remotes, checks)
- Added `docs/developer/releases.md`, `tools/oform_check_independence.py`
- Expanded `CONTRIBUTING.md`; updated `docs/README.md`, `docs/build/windows.md`, root `README.md`, PR template
- Added `docs/maintenance/upstream-isolation-audit.md`, `independence-implementation-validation.md`

## Later same day — open-source licensing policy

- Added `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES.md` (pointers; no replacement of `COPYING` / `doc/license` / `release/license`)
- Added `docs/licensing/policy.md`; expanded attribution, README, developer guide, releases, CONTRIBUTING
- Documented unresolved `license.md` GPL-3 intro vs GPL-2 / `GPL-2.0-or-later` SPDX discrepancy for counsel

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
