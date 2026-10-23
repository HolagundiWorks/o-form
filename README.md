# O-Form

**Open Source. Built for Architects. Driven by Community.**

O-Form is the 3D modelling application in **OSAS** (Open Source Architecture Suit), developed by [Human Centric Works](https://github.com/HolagundiWorks).

It is a **clone of [Blender](https://www.blender.org) 5.2.3 LTS**: the full source tree lives here as an independent repository (no Blender upstream remote). The mesh kernel, `.blend` files, and internal build targets stay Blender’s. The product surface is push/pull solid modelling for architectural workflows—one active tool, a left tool pane, axis locks, and a measurements box.

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
| License | GNU GPL v2 or later ([COPYING](COPYING)) |

O-Form is **not** affiliated with the Blender Foundation or with Trimble. It does not use SketchUp files, icons, or artwork. It does **not** claim BIM/IFC certification, SketchUp file compatibility, or production readiness beyond what is listed below.

## Documentation

| Guide | Link |
| --- | --- |
| Documentation index | [docs/README.md](docs/README.md) |
| User overview | [docs/user/overview.md](docs/user/overview.md) |
| Developer architecture | [docs/developer/architecture.md](docs/developer/architecture.md) |
| Windows build | [docs/build/windows.md](docs/build/windows.md) |
| Licensing / attribution | [docs/licensing/attribution.md](docs/licensing/attribution.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Status (verified in this tree)

**Implemented**

- Windows lite build target `make oform 2022b` → `oform.exe`
- App template with suite branding (pastel green accent)
- Tools: Select, Eraser, Paint, Line, Arc, Rectangle, Circle, Push/Pull, Offset, Move, Rotate, Scale, Orbit, Pan, Zoom, Zoom Extents
- Axis locks, typed measurements, basic inference (endpoint, midpoint, on edge, on face, axis)
- Face split when drawing a closed shape on a face
- Headless selftest (`OFORM_SELFTEST_OK`)
- OBJ export (CMake); glTF via `io_scene_gltf2`

**Not implemented / out of scope for now**

- Follow Me, Tape Measure, Groups, Components
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

Same terms as Blender: **GNU GPL v2 or later**. See [COPYING](COPYING), [doc/license/GPL-license.txt](doc/license/GPL-license.txt), and [docs/licensing/attribution.md](docs/licensing/attribution.md). Third-party notices: [release/license/license.md](release/license/license.md). There is no warranty.

Blender author credits remain in [AUTHORS](AUTHORS). Do not remove upstream copyright headers.
