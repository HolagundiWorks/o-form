# Build O-Form on Windows

Verified product path: **Windows**, Visual Studio **2022** Build Tools (`2022b`), lite **Release** configuration.

The source path must **not** contain spaces. Recommended location: `D:\o-form`.

## Prerequisites

- Git  
- CMake  
- Visual Studio 2022 Build Tools with the C++ desktop workload  
- Windows SDK (as required by the Blender 5.2 Windows build)

Use `cmd.exe` for `make` (not PowerShell), matching Blender’s Windows scripts.

## Get the source

```
git clone https://github.com/HolagundiWorks/o-form.git D:\o-form
cd /d D:\o-form
```

Default branch is `main`.

## Libraries and compile

Confirm remotes first (`git remote -v`). Routine development uses only the O-Form `origin` (https://github.com/HolagundiWorks/o-form.git). Do not add a Blender source upstream.

```
make update
make oform 2022b
```

- `make update` fetches prebuilt libraries into `lib/windows_x64` (same layout Blender uses). That is **dependency** fetch, not merging Blender source. If a temporary LFS helper remote appears, remove it after assets are present (`git remote -v`, then `git remote remove <name>` only when confirmed).  
- `make oform` applies `build_files/cmake/config/oform.cmake` (Cycles, compositor extras, and video codecs off; Wavefront OBJ on) and builds.

Typical output:

```
D:\build_windows_OForm_x64_vc17_Release\bin\Release\oform.exe
```

`oform.exe` is a POST_BUILD copy of `blender.exe`. Launching it loads the O-Form app template.

## Python-only iteration

Edit files under `scripts/startup/bl_app_templates_system/oform/`, then copy them into:

```
D:\build_windows_OForm_x64_vc17_Release\bin\Release\5.2\scripts\startup\bl_app_templates_system\oform\
```

Delete `__pycache__` in that folder after copying.

## Selftest

```
cd /d D:\build_windows_OForm_x64_vc17_Release\bin\Release
oform.exe --background --factory-startup --python D:\o-form\scripts\startup\bl_app_templates_system\oform\selftest.py
```

Success prints `OFORM_SELFTEST_OK`.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| CMake fatal on tiny `startup.blend` | Git LFS object not fetched; restore LFS objects before configure |
| Install tries `C:\Program Files (x86)\Blender` | Use the build-tree install into `bin\Release` as produced by `make oform` |
| PowerShell `${BUILD_TYPE}` empty | Prefer `cmd.exe` for Blender `make` scripts |
| Path with spaces | Relocate the tree (Windows Blender build rejects spaces) |

## Independence check

```
python tools\oform_check_independence.py
```

Expect `oform_check_independence: OK`. See the [developer guide](../developer/architecture.md#8-repository-independence-checks).

## Other platforms

macOS and Linux Blender build scripts remain in-tree. They are **not** verified O-Form product deliverables in this documentation pass.
