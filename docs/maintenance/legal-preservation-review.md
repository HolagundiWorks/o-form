# Legal preservation and licensing review

**Audit date:** 2026-10-23  
**Product:** O-Form  
**Code provenance:** Clone of Blender 5.2.3 LTS (`BLENDER_VERSION` 502 / patch 3 / LTS), independent GitHub repository with no Blender upstream remote.

This is a **repository evidence review**, not a formal legal opinion. Unresolved items are listed explicitly.

## Verified facts (from the tree)

1. **Primary license pointer:** Root `COPYING` states Blender uses the GNU GPL and points to `doc/license/GPL-license.txt`. It names the Blender Foundation (2010) and `foundation@blender.org`. **Not replaced** by this audit.
2. **GPL text present:** `doc/license/GPL-license.txt` (GPL-2.0 family text as shipped with Blender). Additional texts exist (`GPL3-license.txt`, Apache, MIT, BSD, MPL, Boost, Zlib, LGPL, etc.).
3. **SPDX practice:** Many source files use `SPDX-License-Identifier: GPL-2.0-or-later` and `SPDX-FileCopyrightText: … Blender Authors`. O-Form product files under `scripts/startup/bl_app_templates_system/oform/` use `SPDX-FileCopyrightText: 2026 O-Form Authors` and `GPL-2.0-or-later`.
4. **Third-party inventory:** `release/license/license.md` and `licenses.json` catalogue redistributed library licenses. **Left intact.**
5. **Authors list:** Root `AUTHORS` is the Blender copyright author list. **Names not replaced.**
6. **Packaged notices:** `release/text/copyright.txt` retains Blender Foundation copyright and GPL terms; O-Form / Human Centric Works product lines were added as an additional notice, not as a substitute.
7. **Version string in binary:** Internal Blender version remains 5.2.3 LTS for library and `bpy` compatibility (product decision documented in prior work).

## Actions taken this pass

- Did **not** rewrite `COPYING`, `AUTHORS` name list, `doc/license/*`, or `release/license/*`.
- Did **not** change SPDX headers on inherited Blender C/C++/Python modules.
- Product-facing About / README language states O-Form is a **clone of Blender** under **GPL-2.0-or-later**, and disclaims affiliation with the Blender Foundation and Trimble.
- Removed `.github/FUNDING.yml` redirect to `fund.blender.org` so this independent repository does not imply Blender Foundation fundraising. No replacement funding URL was invented.

## Unresolved compliance questions

1. **Formal license counsel:** Whether additional “prominent notice of modification” language is required in every redistribution channel beyond README / About / `copyright.txt` has not been confirmed with counsel.
2. **Asset trademarks:** Window/taskbar icon and some C UI logos may still display Blender marks inside the executable. Replacing them is outstanding product work; legal risk of shipping Blender marks on an independent product should be reviewed.
3. **`.github/README.md` formerly claimed “GNU GPL Version 3” for Blender as a whole** (Blender mirror text). That file is being replaced with O-Form guidance; the canonical tree still uses GPL-2.0-or-later SPDX and `COPYING` → `GPL-license.txt`. Do not treat the old mirror README as authoritative.
4. **Complete third-party audit:** `release/license/license.md` is large; this pass did not re-verify every library version against the Windows `lib/windows_x64` snapshot.
5. **Contributor CLA / DCO:** No project-specific contributor agreement was found. Contribution process for O-Form-specific patches is documented in `CONTRIBUTING.md` without inventing a CLA.

## Guidance for future edits

- Prefer adding O-Form notices **alongside** Blender notices.
- Never delete third-party license files to “clean” branding.
- Never claim SketchUp, Trimble, or Blender Foundation affiliation.
- When unsure, leave the legal file unchanged and record the question here.
