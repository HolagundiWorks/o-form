# SketchUp interface & power-user case study → O-Form

Research date: 2026-10-24. Sources: SketchUp QRC 2024 (Windows), [Tips and Tricks](https://help.sketchup.com/en/sketchup/tips-and-tricks), [Measurements Box](https://help.sketchup.com/en/using-measurements-box), [Solid Tools](https://help.sketchup.com/en/sketchup/modeling-complex-3d-shapes-solid-tools), MasterSketchUp workspace guide, Level Up SketchUp *Status Bar Deep Dive* (YouTube), SketchUp Training Series *Copies and Arrays* (YouTube), r/Sketchup shortcut threads (2023–2024).

## Interface anatomy (what power users keep on screen)

| SketchUp | Role | O-Form mapping |
| --- | --- | --- |
| Large Tool Set (left) | Primary modelling tools, icon-only | Left PROPERTIES rail `_LARGE_TOOL_SET` |
| Status bar centre | Live tool prompt + modifiers | `oform_status` |
| Measurements / VCB (status right) | Typed dims without clicking | `oform_measure` + on-canvas VCB chip |
| Instructor tray | Active-tool how-to | **Instructor** panel |
| Entity Info | Selection metrics / solid? | **Entity Info** panel |
| Face styles (X-Ray, Wire, Mono) | See through / diagnose | View → Face Style / `Ctrl+Shift+X` |

Workspace advice from MasterSketchUp: enable Large Tool Set, memorize its shortcuts, use Styles (X-Ray) when Move needs a hidden reference.

## Core workflows (blogs + official tips)

1. **Click-release, not drag** for draw tools (official tips).
2. **Inference first** — endpoints (green), midpoints (blue), intersections; Shift locks; arrows lock axes (QRC).
3. **Groups isolate; components reuse** — Reddit + tips: never leave raw geometry stuck to the model.
4. **Push/Pull** — type distance; Ctrl copies face; **double-click repeats last** (QRC).
5. **Move/Rotate copy arrays** — Ctrl copy once, then `Nx` external or `N/` internal (Training Series + Measurements Box).
6. **Follow Me** — select path first, then face; Alt for full perimeter (QRC; O-Form: path then face).
7. **Solids** — watertight manifold; Union / Subtract / Intersect / Trim / Outer Shell (help + Notre Dame guide).
8. **ESC before Undo** — cancel in-progress tool state (tips).

## Power-user commands (Reddit + custom shortcuts)

| Habit | Typical binding | O-Form |
| --- | --- | --- |
| Unhide last | `U` | `U` |
| Unhide all | `Shift+U` | `Shift+U` |
| Hide | `Ctrl+H` / Home | `Ctrl+H` |
| Hide rest of model (edit group) | `X` / `Ctrl+H` isolate | `Ctrl+Shift+H` |
| Paste in place | `Shift+V` | `Shift+V` |
| Reverse faces | `Y` | `Y` |
| Delete guides | custom `G` | `Ctrl+Shift+G` |
| X-Ray / face style | `Alt+X` / `Ctrl+Shift+X` | `Ctrl+Shift+X` cycles |
| Zoom window | toolbar | `W` |
| Previous view | toolbar Previous | `[` |

## Implemented in this pass

- Move/Rotate **copy toggle** + **`Nx` / `N/` arrays** (`poweruser.py`)
- Push/Pull **double-click repeat last distance**
- **Shift** inference lock; arrow axis locks (existing)
- **Hide / Unhide Last / Unhide All / Hide Rest**
- **Copy + Paste in Place**
- **Reverse Faces**, **Delete Guides** (tagged edges)
- **Face styles** Shaded / X-Ray / Wireframe / Monochrome
- **Solid Trim** + Outer Shell (union)
- **Instructor** + richer **Entity Info**
- **Zoom Window**, **Previous View**
- Help / overview docs updated

## Still partial / future

- Solid **Split** and true Outer Shell topology (vs union)
- Lasso select, Rotated Rectangle, Section Plane, Walk/Look Around
- Soften/smooth Alt unsoften parity
- Paint Ctrl/Shift match-replace materials
- Non-destructive Procedural Solids (SketchUp 2025+)
- DPI matrix QA for icon rail

## Practice checklist

1. Rectangle → Push/Pull `2.5` → double-click adjacent face.  
2. Component → Move+Ctrl copy → `5x` Enter → retune with `8x`.  
3. Rotate+Ctrl 45° → `8x` circular array.  
4. Enter group → `Ctrl+Shift+H` → model in isolation → `Shift+U`.  
5. Tape+Ctrl guides → `Ctrl+Shift+G` clear.  
6. Cycle `Ctrl+Shift+X` for X-Ray while moving to a hidden edge.
