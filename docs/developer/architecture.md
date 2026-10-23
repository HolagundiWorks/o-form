# O-Form developer architecture

O-Form keeps the Blender mesh kernel, depsgraph, draw manager, and most C/C++ modules. Product behaviour is layered mainly as an **application template** plus a **lite CMake config** and a few window-manager identity hooks.

## Repository layout (high level)

| Path | Role |
| --- | --- |
| `source/blender/` | Inherited Blender C/C++ core |
| `scripts/startup/bl_app_templates_system/oform/` | **O-Form product surface** (UI, tools, branding, selftest) |
| `build_files/cmake/config/oform.cmake` | Lite Windows modelling options |
| `build_files/windows/` | `make oform` target wiring |
| `source/creator/` | POST_BUILD copy `blender.exe` → `oform.exe` |
| `doc/` | Inherited Blender doc generators (Sphinx/Doxygen) |
| `docs/` | O-Form product documentation (this tree) |
| `release/text/` | Packaged readme / copyright |
| `lib/windows_x64/` | Prebuilt libraries (via `make update`) |

## O-Form template modules

Imported as `bl_app_templates_system.oform`. `register()` must not touch `bpy.context` (runs under `RestrictBlend`).

| Module | Responsibility |
| --- | --- |
| `__init__.py` | Register / unregister |
| `brand.py` | Colors, suite mark, product strings, theme |
| `ui.py` | Menus, left nav pane, splash/About/status, layout |
| `tools.py` | Modal tools and action operators (`oform.*`) |
| `geom.py` | BMesh edits (rectangle split, push/pull, etc.) |
| `inference.py` | Snap inference helpers |
| `selftest.py` | Headless mesh contract |

## Identity hooks (C++)

Minimal product naming in the window manager (internal symbols remain Blender’s):

- Default app template `oform` unless `--app-template` overrides  
- Window title suffix `O-Form`  
- Splash / About label `O-Form`  
- Properties context chrome hidden when `U.app_template == "oform"`

`--app-template default` still opens the stock Blender layout from the same binary.

## Extending O-Form safely

1. Prefer new operators and UI in `scripts/startup/bl_app_templates_system/oform/`.  
2. Avoid renaming `bpy`, DNA types, or serialized IDs.  
3. Keep `BLENDER_VERSION` aligned with the library set you build against.  
4. For CMake feature toggles, edit `oform.cmake` rather than scattering options.  
5. After Python-only edits, copy into the install tree’s `5.2/scripts/.../oform/` and delete `__pycache__` (no full rebuild required).

## Tests

```
oform.exe --background --factory-startup --python scripts\startup\bl_app_templates_system\oform\selftest.py
```

Expect `OFORM_SELFTEST_OK` and exit code 0.

Inherited Blender unit/regression suites under `tests/` remain Blender’s; they are not the O-Form product contract.
