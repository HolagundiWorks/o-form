# O-Form

**Open Source. Built for Architects. Driven by Community.**

O-Form is the 3D modelling application in **OSAS** (Open Source Architecture Suit), developed by [Human Centric Works](https://github.com/HolagundiWorks).

It is a **clone of [Blender](https://www.blender.org) 5.2.3 LTS**: the full source tree lives here as an independent repository. **No Blender upstream remote, merges, or synchronization** — see the [developer guide](docs/developer/architecture.md). The mesh kernel, `.blend` files, and internal build targets stay Blender’s. The product surface is push/pull solid modelling for architectural workflows—one active tool, a left tool pane, axis locks, and a measurements box.

| | |
| --- | --- |
| Product | O-Form |
| Category | 3D modelling |
| Suite | OSAS · Open Source Architecture Suit |
| Related | O-Studio, O-CoreOp, O-Draft |
| Developer | Human Centric Works · Hospet |
| Repository | [github.com/HolagundiWorks/o-form](https://github.com/HolagundiWorks/o-form) |
| Branch | `main` |
| Files | `.blend` (export: Wavefront OBJ, glTF) |
| License | GNU GPL v2 or later ([LICENSE](LICENSE), [COPYING](COPYING)) |

O-Form is **not** affiliated with the Blender Foundation or with Trimble. It does not use SketchUp files, icons, or artwork. It includes a **native BIM engine** (classify, storeys, IFC4 import/export) that is **not** BlenderBIM/Bonsai and is **not** IFC-certified. It does **not** claim SketchUp file compatibility.

## Documentation

| Guide | Link |
| --- | --- |
| Documentation index | [docs/README.md](docs/README.md) |
| User overview | [docs/user/overview.md](docs/user/overview.md) |
| Developer guide | [docs/developer/architecture.md](docs/developer/architecture.md) |
| Releases | [docs/developer/releases.md](docs/developer/releases.md) |
| Windows build | [docs/build/windows.md](docs/build/windows.md) |
| Licensing / attribution | [docs/licensing/attribution.md](docs/licensing/attribution.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Status (verified in this tree)

**Implemented**

- Windows lite build target `make oform 2022b` → `oform.exe`
- App template with suite branding (pastel green accent)
- SketchUp-aligned tools: Select, Eraser, Paint, Line, Freehand, Arc, Rectangle, Circle, Polygon, Push/Pull, Follow Me, Offset, Move, Rotate, Scale, Tape Measure, Protractor, Back Edges, Orbit, Pan, Zoom, Zoom Extents
- Groups and Components (G / Ctrl+G, double-click to edit, Esc to close, Explode)
- O-Draft-aligned shell: left tools + Properties/Ask side panels, light/dark toggle, Ask AI with Allow/Decline
- SketchUp-like canvas: solid paper, RGB axes, no ground grid
- SketchUp-style keys (Space, L, A, R, C, P, F, M, Q, S, T, E, B, G, O, H, Z, Shift+Z, plus N/J/X/K/Shift+L/Ctrl+G)
- Axis locks, typed measurements, basic inference (endpoint, midpoint, on edge, on face, axis)
- Face split when drawing a closed shape on a face; Ctrl copy on Move/Push-Pull
- Headless selftest (`OFORM_SELFTEST_OK`)
- OBJ export (CMake); glTF via `io_scene_gltf2`

**Not implemented / out of scope for now**

- Nested groups inside groups; full component browser
- Full parallel / perpendicular / intersection inference
- Verified macOS/Linux product packages
- Replacement of all Blender chrome icons inside the executable

## Branding

Identity module: `scripts/startup/bl_app_templates_system/oform/brand.py`.

| Token | Value |
| --- | --- |
| Product | O-Form |
| Subtitle | Modeling |
| Tagline | Push/pull solid modeling |
| Suite | OSAS · Open Source Architecture Suit |
| Credit | Developed by Human Centric Works · Hospet |
| Origin | A clone of Blender |
| Accent | Pastel green `#C6E6D3` (ink arcs `#17181B`) |

## Layout and tools

See [docs/user/overview.md](docs/user/overview.md) for the workspace, shortcuts, and inference notes.

Product code lives mainly in:

```
scripts/startup/bl_app_templates_system/oform/
```

Lite config: `build_files/cmake/config/oform.cmake`.  
`--app-template default` opens the unmodified Blender layout from the same binary.

## Build (Windows)

Path must not contain spaces (`D:\o-form` recommended). From `cmd.exe`:

```
git clone https://github.com/HolagundiWorks/o-form.git D:\o-form
cd /d D:\o-form
make update
make oform 2022b
```

Binary: `D:\build_windows_OForm_x64_vc17_Release\bin\Release\oform.exe`

Full steps: [docs/build/windows.md](docs/build/windows.md).

## Selftest

```
oform.exe --background --factory-startup --python scripts\startup\bl_app_templates_system\oform\selftest.py
```

Prints `OFORM_SELFTEST_OK` on success.

## License and attribution

O-Form is open source. As a modified Blender distribution it remains under the **GNU GPL, version 2 or later** (`GPL-2.0-or-later`). That is verified from `COPYING`, `doc/license/GPL-license.txt`, and source SPDX headers — not invented for branding.

| Document | Purpose |
| --- | --- |
| [LICENSE](LICENSE) | Project license statement |
| [COPYING](COPYING) | Retained Blender pointer to the GPL text |
| [NOTICE](NOTICE) | Attribution index |
| [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) | Pointer to third-party inventory |
| [doc/license/GPL-license.txt](doc/license/GPL-license.txt) | Full GPL-2 text |
| [docs/licensing/policy.md](docs/licensing/policy.md) | Licensing policy |
| [docs/licensing/attribution.md](docs/licensing/attribution.md) | File map |
| [release/license/license.md](release/license/license.md) | Bundled third-party notices |
| [AUTHORS](AUTHORS) | Blender author credits (do not remove) |

There is no warranty. Independent development (no Blender upstream) does not cancel GPL obligations. Do not remove copyright headers or advertise a conflicting license for inherited code.
