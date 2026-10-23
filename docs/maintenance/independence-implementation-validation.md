# Validation report — independence / developer guide pass

**Date:** 2026-10-23  
**Branch:** `main`

## Commands and results

### Remotes (inspected, not modified)

```
git remote -v
```

Result:

```
origin  https://github.com/HolagundiWorks/o-form.git (fetch)
origin  https://github.com/HolagundiWorks/o-form.git (push)
```

### Independence checker

```
D:\build_windows_OForm_x64_vc17_Release\bin\Release\5.2\python\bin\python.exe tools\oform_check_independence.py
```

**Result:** `oform_check_independence: OK` (exit 0).

### Relative documentation links

Resolved `](…)` targets under `docs/`, `README.md`, `CONTRIBUTING.md`, `.github/README.md`.

**Result:** `link_or_legal_errors=0`.

### Legal files still present

`COPYING`, `AUTHORS`, `doc/license/GPL-license.txt`, `release/license/license.md`, `release/text/copyright.txt` — presence verified (no deletions).

### Not run

| Check | Reason |
| --- | --- |
| Full C++ rebuild | Documentation / tooling only |
| Product selftest | No mesh/tool logic changed |
| Sphinx/Doxygen | Inherited generators unchanged |

## Diff expectations

Documentation under `docs/`, `CONTRIBUTING.md`, `README.md` index links, `tools/oform_check_independence.py`, PR template note. No license file deletions. No git remote changes executed by this pass.
