# O-Form UI redesign — Phase 1 audit

**Date:** 2026-10-24  
**Policy:** Independent OSAS product. No Blender upstream sync.  
**Rule:** Do not mix Blender and SketchUp UI conventions. Preserve capability; redesign discovery and control.

Companion canvas: `canvases/oform-unified-ui-redesign.canvas.tsx`  
Design system: [ui-design-system.md](ui-design-system.md)

---

## Verdict

O-Form already ships a SketchUp-*inspired* modelling shell on top of a Blender app template: menus, left PROPERTIES rail, paper VIEW_3D, status/VCB, Ask. That is still **two presentation languages stitched together** (PROPERTIES editor + SketchUp tool names + residual `wm.*` chrome). The redesign must introduce an **O-Form-owned workspace layer**, then migrate commands into it behind a feature flag—without rewriting the geometry engine.

---

## Visible shell inventory

| Region today | Implementation | Conflict |
| --- | --- | --- |
| Top menus | Swapped `TOPBAR_MT_editor_menus` | File still calls `wm.quit_blender`, etc. |
| Topbar right | Default Blender draw (left swapped only) | Dual chrome |
| Left tools | `OFORM_PT_*` on **PROPERTIES** | Wrong host editor for a tool rail |
| Viewport | VIEW_3D + C++ region strip | Correct direction |
| Status | Swapped statusbar + VCB | Also mirrored in Ask overlay chip |
| Ask | Left panel + POST_PIXEL chip | Dual surfaces |
| Theme | `brand.apply_theme` | Suite green vs redesign “restrained blue” — resolve in tokens |

**Hard hooks to re-home (not delete):** `brand.apply_theme`, PROPERTIES panels, `screen.area_split`, three `SpaceView3D` draw handlers, addon keymap, C++ `U.app_template == "oform"` region gates.

---

## Command map (summary)

Full operators live in `tools.py` / `ui.py`. Taxonomy for the new shell:

| Group | Commands (user-facing) |
| --- | --- |
| **Draw** | Line · Rectangle · Circle · Arc · Polygon · Freehand |
| **Edit** | Select · Eraser · Move · Rotate · Scale · Offset · Reverse Faces |
| **Model** | Push/Pull · Follow Path · Boolean (Union/Subtract/Intersect/Trim) |
| **Organize** | Group · Component · Explode · Enter/Exit · Hide Rest |
| **Inspect** | Measure · Protractor · Entity Info · Inspect Solid · Delete Guides |
| **View** | Orbit · Pan · Zoom · Extents · Window · Standard views · Face Style |
| **Shell** | Theme · Preferences (O-Form) · Ask |

Classify: **Preserve** engine; **Adapt** presentation; **Hide** unused Blender editors (already largely done); **Defer** Section/Walk/Lasso/.skp.

---

## Duplicates & conflicts

1. Same tools on rail + Draw/Tools menus + keymap (+ solids also on Entity Info).  
2. Modal `oform.tool_*` and non-modal `oform.rectangle` / `line_add` dual API.  
3. PROPERTIES-as-rail caused full-width layout failures when size assignment inverted.  
4. Architecture terms (Push/Pull, Component) sit beside Blender terms (Properties editor, quit_blender).  
5. Ask panel vs decorative overlay history.

---

## Classification matrix (major)

| Capability | Class |
| --- | --- |
| BMesh draw / push-pull / inference / groups / solids | Preserve |
| Large Tool Set interaction model | Adapt → O-Form primary strip + left rail |
| Status + VCB | Adapt → single bottom status |
| Ask | Adapt → inspector or dedicated dock, one entry |
| Unregistered animation/outliner/etc. | Hide (keep) |
| Non-modal duplicate ops | Hide / deprecate after AI allow-list update |
| Section, Walk, Lasso, SKP | Defer |

---

## Recommended sequence (locked)

1. **Audit** — this document (done).  
2. **Design system** — O-Draft tokens via `brand.py` / `design.py` (done).  
3. **Product shell** — O-Draft layout restored (`UI_SHELL_V2=False`): left tools + Entity Info + Ask | canvas | status.  
4. **Shell v2** — kept in `shell_v2.py` behind the flag for experiments only.  
5. **QA** — selection, snap, VCB, undo, files, DPI, themes.

**Do not** skin Blender headers and call it done. **Do not** delete modelling operators during shell work.
