# O-Form developer guide

Canonical developer documentation for **O-Form**, the 3D modelling application in **OSAS** (Open Source Architecture Suit).

**Open Source. Built for Architects. Driven by Community.**

Related: [Windows build](../build/windows.md) · [Releases](releases.md) · [Contributing](../../CONTRIBUTING.md) · [Attribution](../licensing/attribution.md)

---

## 1. Product identity

| | |
| --- | --- |
| Product | O-Form |
| Parent suite | OSAS — Open Source Architecture Suit |
| Purpose | Independently developed 3D modelling with an architectural workflow focus |
| Ownership | O-Form maintainers / Human Centric Works |
| Canonical repository | https://github.com/HolagundiWorks/o-form |
| Default branch | `main` |

O-Form is **not** an official Blender Foundation product. Product documentation, issues, releases, roadmap, and contribution workflow use **O-Form** identity only.

---

## 2. Independence policy (non-negotiable)

**No Blender upstream. No upstream merges. No upstream synchronization. No upstream development dependency.**

O-Form development must **not** require:

- A Blender upstream Git remote  
- Fetching from Blender’s source repositories for routine work  
- Merging or rebasing onto Blender upstream  
- Pulling Blender upstream changes  
- Automated upstream synchronization  
- Upstream-based release or version synchronization  
- Upstream issue tracking or release coordination  
- Scripts whose purpose is to fetch or merge Blender **source** into this tree  

All routine development uses O-Form’s own repository, branches, issues, tests, build, and release process.

Do **not** add a Blender upstream remote. Do **not** create an upstream synchronization mechanism.

### Four separate concepts

| Concept | Meaning |
| --- | --- |
| **Product and repository independence** | Day-to-day work never needs Blender Git remotes or merges |
| **Historical source-code provenance** | This tree was cloned from Blender 5.2.3 LTS; that history remains in Git |
| **Copyright and license compliance** | GPL and third-party notices stay intact ([attribution](../licensing/attribution.md)) |
| **Optional third-party dependencies** | Prebuilt libraries (`make update`) are dependency management, not “tracking Blender releases” |

Independence does **not** mean the code has no inherited dependencies or that GPL obligations disappeared.

---

## 3. Repository setup (O-Form only)

### Clone

```
git clone https://github.com/HolagundiWorks/o-form.git D:\o-form
cd /d D:\o-form
```

Use a path **without spaces** on Windows.

### Safe diagnostics

```
git remote -v
git branch --show-current
git status --short
git log -5 --oneline
```

Expected remote for normal work:

```
origin  https://github.com/HolagundiWorks/o-form.git (fetch)
origin  https://github.com/HolagundiWorks/o-form.git (push)
```

There should be **no** remote named `upstream` (or similar) pointing at `github.com/blender/blender` or `projects.blender.org/blender/blender`.

### Feature branch workflow

```
git checkout main
git pull origin main
git checkout -b feature/short-description
# … edit, build, test …
git add <paths>
git commit
git push -u origin HEAD
```

Open a pull request against `main` on https://github.com/HolagundiWorks/o-form.

### If a Blender remote appears

1. Confirm with `git remote -v` — note the **exact** remote name and URL.  
2. Only remove it when you have verified it is a Blender source remote, for example:

```
git remote remove upstream
```

3. If `origin` points at the wrong host, fix it only after verifying the intended O-Form URL:

```
git remote -v
git remote set-url origin https://github.com/HolagundiWorks/o-form.git
```

Never delete branches, rewrite history, reset published commits, delete tags, or remove remotes blindly.

### Libraries vs source remotes

`make update` downloads prebuilt Windows libraries into `lib/`. That may contact Blender infrastructure for **library/LFS assets**. That is dependency fetch, not an invitation to merge Blender source. After any temporary LFS helper remote (historically `lfs-fallback`) is used, remove it so the working tree again has only the O-Form `origin`. See [Windows build](../build/windows.md).

---

## 4. Architecture (what is O-Form vs inherited)

O-Form keeps the inherited mesh kernel, depsgraph, draw manager, and most C/C++ modules. Product behaviour is layered as an **application template**, a **lite CMake config**, and a few window-manager identity hooks. Inherited components are **not** claimed as independently rewritten unless the source shows that.

### Layout

| Path | Role |
| --- | --- |
| `source/blender/` | Inherited C/C++ core |
| `scripts/startup/bl_app_templates_system/oform/` | **O-Form product surface** |
| `build_files/cmake/config/oform.cmake` | Lite modelling options |
| `build_files/windows/` | `make oform` wiring |
| `source/creator/` | POST_BUILD `blender.exe` → `oform.exe` |
| `docs/` | O-Form product documentation |
| `doc/` | Inherited Sphinx/Doxygen generators |
| `lib/windows_x64/` | Prebuilt libraries |

### Template modules

Imported as `bl_app_templates_system.oform`. `register()` must not touch `bpy.context`.

| Module | Responsibility |
| --- | --- |
| `__init__.py` | Register / unregister |
| `brand.py` | Colors, mark, product strings, theme |
| `ui.py` | Menus, left pane, splash/About/status |
| `tools.py` | Modal tools / operators (`oform.*`) |
| `geom.py` | BMesh edits |
| `inference.py` | Snap helpers |
| `selftest.py` | Headless mesh contract |

### Identity hooks (C++)

Internal symbols stay Blender’s; product naming is thin:

- Default app template `oform`  
- Window title / About label `O-Form`  
- Properties chrome adjustments when `U.app_template == "oform"`  

`--app-template default` still opens the stock Blender layout from the same binary.

### Extending safely

1. Prefer new behaviour in `scripts/startup/bl_app_templates_system/oform/`.  
2. Do not rename `bpy`, DNA types, or serialized IDs for branding.  
3. Keep `BLENDER_VERSION` aligned with the library set you build against (file-format / lib compatibility). That internal version is **not** the O-Form product release number — see [Releases](releases.md).  
4. Toggle features in `oform.cmake`.  
5. Python-only edits: copy into the install tree `5.2/scripts/.../oform/` and delete `__pycache__`.

Document architectural changes in this guide (or a linked maintenance note) when you change extension points.

---

## 5. Build, test, package

- **Build:** [Windows build](../build/windows.md) — `make update` then `make oform 2022b`.  
- **Product selftest:**

```
oform.exe --background --factory-startup --python scripts\startup\bl_app_templates_system\oform\selftest.py
```

Expect `OFORM_SELFTEST_OK`.

- Inherited suites under `tests/` are Blender-era harnesses; they are not the O-Form product contract.  
- **Independence check:** [Running independence checks](#8-repository-independence-checks).

---

## 6. Versioning note

`BLENDER_VERSION` in `BKE_blender_version.h` remains **5.2.3 LTS** for `.blend` and library compatibility. O-Form **product** releases are versioned separately; do not assume product tags must match Blender release numbers. Details: [Releases](releases.md).

---

## 7. Legal integrity (developers)

O-Form is open source under **GPL-2.0-or-later** as a Blender derivative. See [licensing policy](../licensing/policy.md).

- Do not replace Blender or third-party copyright notices with O-Form ownership.  
- Do not delete `LICENSE`, `COPYING`, `NOTICE`, `doc/license/*`, or `release/license/*`.  
- Do not introduce a proprietary or incompatible license for inherited code.  
- Do not rewrite Git history to erase origin.  
- Do not claim independence removes GPL or source-distribution obligations.  
- New O-Form-only files should use an SPDX header consistent with dependencies (typically `GPL-2.0-or-later`).  
- Map: [attribution](../licensing/attribution.md) · evidence: [legal preservation review](../maintenance/legal-preservation-review.md).

---

## 8. Repository independence checks

Maintainers can run:

```
D:\build_windows_OForm_x64_vc17_Release\bin\Release\5.2\python\bin\python.exe tools\oform_check_independence.py
```

Or any Python 3 available on `PATH`:

```
python tools\oform_check_independence.py
```

The script fails on **active** Blender **source** remotes and on workflows/scripts that clearly synchronize Blender upstream into this repo. It does **not** fail merely because a copyright notice, license file, API name, or historical comment mentions Blender.

Audit background: [Upstream isolation audit](../maintenance/upstream-isolation-audit.md).
