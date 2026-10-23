# O-Form

O-Form is a free 3D modeling application. It is a fork of [Blender](https://www.blender.org) 5.2.3 LTS with the visible workflow reduced to solid modeling: one active tool, a short toolbar, axis locks, and a measurements box.

O-Form is not affiliated with the Blender Foundation or with Trimble. The modeling interaction follows the same ideas as a push/pull modeler. It does not use SketchUp files or artwork.

Files are saved as `.blend`. File → Export writes Wavefront OBJ and glTF.

## License

O-Form is free software under the GNU General Public License, version 2 or later, the same terms as Blender. You can redistribute it and/or modify it under those terms.

See [COPYING](COPYING) and [doc/license/GPL-license.txt](doc/license/GPL-license.txt). There is no warranty.

## Build on Windows

The source path cannot contain spaces. This tree is meant to live at `D:\o-form`.

Requirements: Git, CMake, and Visual Studio 2022 Build Tools with the C++ workload.

From `cmd.exe` in this directory:

```
make update
make oform 2022b
```

`make update` downloads the prebuilt Windows libraries. `make oform` configures the lite modeling build (Cycles, compositing, and video codecs stay off; OBJ export stays on) and compiles it.

The application binary is `oform.exe`, copied next to `blender.exe` in the build folder, typically:

```
D:\build_windows_OForm_x64_vc17_Release\bin\Release\oform.exe
```

Launching it opens the O-Form template. `--app-template default` starts the unmodified Blender layout instead.

## Modeling

The window is a single 3D view. Middle mouse orbits, Shift+middle mouse pans, and the wheel zooms. Tab does not leave edit mode. Drawing a closed shape on a face splits that face, so the inner face can be pushed or pulled.

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

## Check the mesh tools

After the binary exists:

```
oform.exe --background --factory-startup --python scripts/startup/bl_app_templates_system/oform/selftest.py
```

The script draws a rectangle, splits it with a second rectangle, push/pulls the inner face, undoes, and prints `OFORM_SELFTEST_OK`.
