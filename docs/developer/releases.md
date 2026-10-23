# O-Form releases

O-Form owns its release process. Releases are **not** synchronized to Blender upstream tags or schedules.

## Versioning

| Kind | Where | Notes |
| --- | --- | --- |
| Internal Blender compatibility version | `source/blender/blenkernel/BKE_blender_version.h` (`BLENDER_VERSION` 502 / patch 3 / LTS) | Keeps `.blend` and prebuilt libs aligned. **Do not bump casually.** |
| O-Form product release | Git tags / GitHub Releases on this repository | Chosen by O-Form maintainers; need not match Blender’s marketing version |

Do **not** automate “follow latest Blender tag” version sync. Changing `BLENDER_VERSION` can break libraries and file IO; treat it as a compatibility project, not a branding knob.

## Release checklist (maintainers)

1. **Select version** — agree product version string and git tag name (for example `oform-0.x.y`). Document known issues.  
2. **Changelog** — summarize user-visible changes since the previous product tag (docs, tools, build).  
3. **Regression** — run the product selftest; manually smoke-test launch, draw, push/pull, save/open `.blend`, export OBJ/glTF if touched.  
4. **Build artifact** — produce `oform.exe` via `make oform 2022b`; confirm it sits next to the install tree scripts.  
5. **License packaging** — binary and source distributions must include or clearly provide:
   - `LICENSE`, `COPYING`, and/or `doc/license/GPL-license.txt`  
   - `NOTICE` and `release/text/copyright.txt`  
   - `release/license/` (third-party notices)  
   - `release/text/readme.html`  
   - Corresponding **source** for the tagged release (public tag/archive on https://github.com/HolagundiWorks/o-form, or another GPL-compliant offer)  
   Do not strip notices. A public repo alone does not prove a given binary build was compliant — attach or link the matching source tag.  
6. **Independence check** — run `tools/oform_check_independence.py`.  
7. **Publish** — tag on `main`, attach artifacts on GitHub Releases for https://github.com/HolagundiWorks/o-form, write release notes and known issues.  
8. **Install / upgrade notes** — document unpack path (no spaces), launch `oform.exe`, and that files remain `.blend`.

## What not to do

- Do not merge Blender release branches into O-Form to “catch up.”  
- Do not require projects.blender.org for release coordination.  
- Do not rewrite history when tagging.  
- Do not ship builds without license/notice files to “simplify” branding.  
