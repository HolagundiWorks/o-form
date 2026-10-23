# O-Form

**O-Form is a clone of [Blender](https://www.blender.org) 5.2.3 LTS.**

This repository is that Blender tree, kept as its own project with no Blender upstream remote. The mesh kernel, `.blend` files, and internal build targets stay Blender’s. The product surface is push/pull solid modeling: one active tool, a left tool pane, axis locks, and a measurements box.

| | |
| --- | --- |
| Product | O-Form |
| Role | Modeling |
| Suite | OSAS · Open Source Architecture Suit |
| Developer | Human Centric Works · Hospet |
| Repository | [github.com/HolagundiWorks/o-form](https://github.com/HolagundiWorks/o-form) |
| Branch | `oform` |
| Files | `.blend` (export: Wavefront OBJ, glTF) |
| License | GNU GPL v2 or later ([COPYING](COPYING)) |

O-Form is not affiliated with the Blender Foundation or with Trimble. It does not use SketchUp files, icons, or artwork.

## Branding

O-Form is part of **OSAS**, the Open Source Architecture Suit, alongside O-Studio, O-CoreOp, and O-Draft. Identity lives in `scripts/startup/bl_app_templates_system/oform/brand.py`.

| Token | Value |
| --- | --- |
| Product | O-Form |
| Subtitle | Modeling |
| Tagline | Push/pull solid modeling |
| Suite | OSAS · Open Source Architecture Suit |
| Credit | Developed by Human Centric Works · Hospet |
| Origin | A clone of Blender |

**Mark.** Same suite geometry as the other apps (left half-ring, lower half-ring, centre ring) on a rounded plate. Sister apps use a saturated plate with white arcs. O-Form’s plate is pastel green `#C6E6D3`; arcs are suite ink `#17181B` so they stay readable.

**Shell.** Light suite chrome: page fog `#F2F4F7`, navigation soft `#ECEEF2`, white bars, ink text, edge `#D0D4DC`. Selected controls use `#8FCBAA`; viewport selection uses `#3FA36A`. UI font prefers Segoe UI when present.

**Assets.** `mark.png` (suite mark) and `splash.png` (lockup) ship with the app template.

## What this clone changes

Almost all product UI and tools live in:

```
scripts/startup/bl_app_templates_system/oform/
```

Windows lite config: `build_files/cmake/config/oform.cmake`  
Build target: `make oform 2022b` → `oform.exe` (copy of `blender.exe`)

Launching `oform.exe` opens the O-Form template. `--app-template default` starts the unmodified Blender layout from the same binary.

## Layout

The first window is a single editable mesh named `Model`, already in edit mode. Tab does not leave edit mode.

- Menu bar: File, Edit, View, Camera, Draw, Tools, Window, Help
- Left pane: tools grouped as Select, Draw, Edit, and View
- Work area: one 3D view (perspective, Z-up, RGB axes, ground grid)
- Status strip: tool hint, measurements box, and Human Centric Works · Hospet

Navigation: middle mouse orbits, Shift+middle mouse pans, wheel zooms. Camera menu: Top, Front, Right, Iso, perspective, parallel, zoom extents.

## Tools

| Tool | Key |
| --- | --- |
| Select | Space |
| Eraser | E |
| Paint | B |
| Line | L |
| Arc | A |
| Rectangle | R |
| Circle | C |
| Push/Pull | P |
| Offset | F |
| Move | M |
| Rotate | Q |
| Scale | S |
| Orbit | O |
| Pan | H |
| Zoom | Z |
| Zoom Extents | Shift+Z |

Arrow keys during a tool: Right locks red (X), Left locks green (Y), Up locks blue (Z), Down locks parallel to the inferred edge. Type a length and press Enter. A rectangle accepts `width, depth`. A circle accepts a segment count such as `24s`, then a radius.

Drawing a closed shape on a face splits that face so the inner face can be pushed or pulled. Inference this release covers endpoints, midpoints, on-edge, on-face, and axis direction. Ctrl+Z and Ctrl+S stay available.

Out of scope for now: Follow Me, Tape Measure, Groups, Components, and full parallel/perpendicular/intersection inference.

## License

Same terms as Blender: GNU General Public License, version 2 or later. See [COPYING](COPYING) and [doc/license/GPL-license.txt](doc/license/GPL-license.txt). There is no warranty.

## Build on Windows

The source path cannot contain spaces. This tree is meant to live at `D:\o-form`.

Requirements: Git, CMake, and Visual Studio 2022 Build Tools with the C++ workload.

```
git clone https://github.com/HolagundiWorks/o-form.git D:\o-form
cd /d D:\o-form
git checkout oform
```

From `cmd.exe` in this directory:

```
make update
make oform 2022b
```

`make update` downloads the prebuilt Windows libraries (same library layout Blender uses). `make oform` configures the lite modeling build (Cycles, compositing, and video codecs stay off; OBJ export stays on) and compiles it.

The application binary is `oform.exe`, next to `blender.exe`:

```
D:\build_windows_OForm_x64_vc17_Release\bin\Release\oform.exe
```

Python-only template edits under `scripts/startup/bl_app_templates_system/oform/` can be copied into that install tree’s matching `5.2\scripts\...` path without a full C++ rebuild. Delete `__pycache__` after copying.

## Check the mesh tools

After the binary exists:

```
oform.exe --background --factory-startup --python scripts\startup\bl_app_templates_system\oform\selftest.py
```

The script draws a rectangle, splits it with a second rectangle, push/pulls the inner face, undoes, and prints `OFORM_SELFTEST_OK`.
