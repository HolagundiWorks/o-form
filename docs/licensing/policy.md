# O-Form open-source licensing policy

**Status:** Repository evidence policy (not a formal legal opinion).  
**Product:** O-Form (OSAS — Open Source Architecture Suit)  
**Repository:** https://github.com/HolagundiWorks/o-form

## 1. Open-source commitment

O-Form is an open-source 3D modelling application. The project provides
transparent source code, community participation, and independently managed
development and releases (no Blender upstream remote, merges, or sync).

Independence does **not** cancel license obligations for inherited code.

## 2. Verified application license

| Evidence | Finding |
| --- | --- |
| `COPYING` | Points to `doc/license/GPL-license.txt`; Blender Foundation notice |
| `doc/license/GPL-license.txt` | GNU GPL **Version 2**, June 1991 |
| Widespread SPDX | `GPL-2.0-or-later` on Blender and O-Form sources |
| O-Form template SPDX | `GPL-2.0-or-later` |
| Packaged notice | `release/text/copyright.txt` states GPL v2 or later |

**Documented arrangement:** O-Form, as a modified Blender distribution, remains
under the **GNU General Public License, version 2 or later**.

Do **not** introduce a proprietary or GPL-incompatible license for inherited
code. Do **not** advertise a different project license until compatibility is
reviewed.

## 3. File map (canonical vs explanatory)

| File | Role |
| --- | --- |
| [`LICENSE`](../../LICENSE) | O-Form project license statement + pointers |
| [`COPYING`](../../COPYING) | Retained Blender convention pointer |
| [`NOTICE`](../../NOTICE) | Attribution index |
| [`THIRD_PARTY_LICENSES.md`](../../THIRD_PARTY_LICENSES.md) | Points to third-party inventory |
| [`doc/license/GPL-license.txt`](../../doc/license/GPL-license.txt) | Full GPL-2 text |
| [`release/license/`](../../release/license/) | Third-party catalogue |
| [`release/text/copyright.txt`](../../release/text/copyright.txt) | Packaged copyright |
| This `docs/licensing/` tree | Guidance only — **not** a license substitute |

## 4. Copyright and branding

- O-Form branding identifies the **product**.  
- It does **not** transfer ownership of inherited Blender or third-party code.  
- Preserve original copyright and SPDX headers.  
- Add O-Form / Human Centric Works notices on original or clearly modified
  O-Form material (for example the `oform` app template).  
- Do not imply O-Form is an official Blender product.

## 5. Distribution requirements

Public Git hosting alone is not proof of compliant redistribution. Releases
must include or provide:

- License texts (`LICENSE` / `COPYING` / `doc/license/GPL-license.txt`)  
- Copyright / NOTICE materials  
- Third-party notices (`release/license/`)  
- Corresponding source access for GPL binaries (source repo tag/archive or
  written offer as applicable)

See the [release checklist](../developer/releases.md).

## 6. Unresolved questions (for qualified review)

1. Reconciliation of `release/license/license.md` intro (GPL-3.0-or-later
   wording) with `COPYING` / GPL-2 text / `GPL-2.0-or-later` SPDX.  
2. Whether every redistribution channel needs additional “prominent
   modification” notices beyond README, About, and `copyright.txt`.  
3. Trademark / logo risk while Blender marks remain in the executable chrome.  
4. Full pin-level audit of `lib/windows_x64` vs `licenses.json`.  
5. Whether to adopt a contributor DCO/CLA (none published yet).

Report **verified facts** and **assumptions** separately; never delete notices
to force branding consistency.
