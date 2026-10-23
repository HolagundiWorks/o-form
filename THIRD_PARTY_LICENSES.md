# Third-party licenses (O-Form)

O-Form redistributes third-party libraries, fonts, and other components that
are **not** all under the same license as the application.

## Canonical inventory (do not duplicate here)

The verified, Blender-maintained inventory shipped with this tree is:

| File | Role |
| --- | --- |
| [`release/license/license.md`](release/license/license.md) | Human-readable third-party license texts and component list |
| [`release/license/licenses.json`](release/license/licenses.json) | Machine-readable license catalogue used by `make license` |
| [`doc/license/`](doc/license/) | Individual SPDX license text files |

That inventory is generated/maintained via Blender’s `make license` tooling
(`tools/utils_maintenance/make_license.py`). O-Form does **not** replace it
with a hand-written second copy that could drift.

## How to use this for O-Form releases

1. Ship `release/license/` with binary packages (same as Blender packaging).  
2. Ship `release/text/copyright.txt` and `release/text/readme.html`.  
3. Keep `LICENSE`, `COPYING`, and `NOTICE` available with source distributions.  
4. When adding a new dependency, update the Blender-era license machinery or
   document an explicit O-Form exception in `docs/licensing/` after review —
   do not silently omit notices.

## Important caveats (verified vs unresolved)

**Verified**

- Application source SPDX identifiers commonly use `GPL-2.0-or-later`.  
- Root `COPYING` points to `doc/license/GPL-license.txt` (GNU GPL Version 2).  
- O-Form product modules under `scripts/startup/bl_app_templates_system/oform/`
  use `GPL-2.0-or-later`.

**Unresolved / needs qualified review**

- The introduction of `release/license/license.md` states Blender is released
  under “GPU-GPL 3.0 or later” / GPL-3.0-or-later wording, which conflicts with
  `COPYING` + `GPL-license.txt` (GPL Version 2) and widespread `GPL-2.0-or-later`
  SPDX headers. Treat `license.md` as the **third-party** catalogue; treat
  `COPYING` / `GPL-license.txt` / SPDX as the **application** license evidence
  until counsel reconciles the wording.  
- This pass did not re-diff every `lib/windows_x64` binary against
  `licenses.json` version pins.  
- Sibling OSAS apps may use different licenses; do not assume they are GPL.

See [`docs/licensing/policy.md`](docs/licensing/policy.md).
