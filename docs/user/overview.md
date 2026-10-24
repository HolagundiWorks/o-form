# O-Form user overview

O-Form is the 3D modelling application in **OSAS** (Open Source Architecture Suit). It is built for focused solid modelling: draw on faces, push and pull, measure as you go.

The product UI is moving to a **single O-Form design system** (architecture-first chrome, SketchUp-like direct modelling, Blender-class geometry underneath)—not a mix of Blender and SketchUp interfaces. See [UI redesign audit](../developer/ui-redesign-audit.md).

**Principle:** Open Source. Built for Architects. Driven by Community.

## Status

| Area | Status |
| --- | --- |
| Windows desktop lite build (`oform.exe`) | Implemented |
| Modelling template (single view, left tool pane) | Implemented |
| SketchUp-aligned draw / edit / measure / view tools | Implemented |
| Headless mesh selftest | Implemented |
| Groups, Components, Make Component (G) | Implemented |
| Plane-aware drawing, inference guides, click-count selection | Implemented |
| Solid Boolean union / subtract / intersect | Implemented |
| Full perpendicular / intersection inference suite | Partial (axis, parallel, from-point, face plane) |
| macOS / Linux product builds | Not verified as product targets |
| SketchUp `.skp` | Not supported / not claimed |
| BIM / IFC4 | Native engine: classify, storeys, IFC I/O; **Push BIM + Take-off** writes suite `hcw-takeoff-shilpi` for O-Draft / O-CoreOp |
| Ask AI | Keyword channel + optional external ask command |

O-Form is **not** affiliated with the Blender Foundation or Trimble. It does not use SketchUp files, icons, or artwork.

## Workspace

On launch, O-Form opens an editable mesh named `Model` in edit mode. Tab does not leave edit mode. The shell follows the same pattern as **O-Draft**: menus, left tools/side panels, solid canvas, status bar, and an Ask channel.

- **Menus:** File, Edit, View, Camera, Draw, Tools, Solids, BIM, Window, Help  
- **Right-click** in the 3D view opens the **BIM** menu — map the selection to an IFC component (Wall, Slab, Door, …). Edit-mode faces are promoted to a component first.  
- **Left pane:** SketchUp-style Large Tool Set (icon rail, incl. Solid Union / Subtract / Intersect), Properties (context / groups), Ask (AI)  
- **View:** Perspective, Z-up, RGB axes, **no ground grid** — solid white/black paper like SketchUp / O-Draft  
- **Theme:** Status-bar Light/Dark toggle (Window → Preferences or status bar); canvas stays pure white or black  
- **Ask:** Left Ask panel (type there). On-canvas strip only for VCB while measuring or pending Allow/Decline — not a fake text field  
- **Status:** Tool hint, theme toggle, **VCB** measurements, Human Centric Works · Hospet  

**Navigation:** Middle mouse orbit, Shift+middle mouse pan, mouse wheel zoom.  
**Camera menu:** Top, Front, Right, Iso, perspective, parallel, zoom extents.

## Tools and shortcuts

Defaults follow [SketchUp’s keyboard shortcuts](https://help.sketchup.com/en/default-keyboard-shortcuts) where O-Form implements the tool.

| Tool | Key |
| --- | --- |
| Select | Space |
| Eraser | E |
| Paint | B |
| Line | L |
| Freehand | Shift+L |
| Arc | A |
| Rectangle | R |
| Circle | C |
| Polygon | N |
| Push/Pull | P |
| Follow Me | J |
| Offset | F |
| Move | M |
| Rotate | Q |
| Scale | S |
| Tape Measure | T |
| Protractor | X |
| Back Edges | K |
| Orbit | O |
| Pan | H |
| Zoom | Z |
| Zoom Extents | Shift+Z |
| Make Component | G |
| Make Group | Ctrl+G |
| Delete | Delete |

**Groups and components**

- Select geometry, then **G** (component) or **Ctrl+G** (group).  
- Click a group/component to select it; **Move** / **Rotate** / **Scale** transform the whole entity.  
- **Double-click** a group or component to edit inside it.
- **Esc** cancels the active command: clears in-progress points/VCB first, then selection / group edit, then returns to Select.
- **Right-click** opens BIM → **Map to IFC Component** (or Auto-Classify / Assign Storey).
- **Edit → Explode** merges the selection into the current context.  
- Components share a mesh definition; **Instance Component** places another linked copy.

**Selection (SketchUp-style)**

- **Single-click** — **point** (endpoint) if close, else **line** (edge); face only in the open interior. Groups/components still select as entities.
- **Double-click** — the **face**.
- **Triple-click** — all **connected faces**.
- Hover shows Endpoint / Midpoint / On Edge / On Face snap tips while selecting or drawing.
- Keyboard alternatives: **Alt+1** (point/line) / **Alt+2** (face) / **Alt+3** (connected). Shift/Ctrl extends; drag for window/crossing.
- **Delete** removes the current selection (faces / edges / verts, or a selected group/component). The root Model cannot be deleted.

**Solids**

- Select two closed mesh solids in Object mode (active = target / keep). Run **Solid Union / Subtract / Intersect** from the bottom of the left tool rail, the **Solids** menu, or Properties → Solids.  
- **Inspect Solid** (Properties or Solids menu) reports whether the active mesh is a closed manifold. Failed Booleans leave sources unchanged.

**Modifiers (SketchUp-style)**

- Move / Push/Pull: **Ctrl** copies  
- Eraser: **Ctrl** softens edges, **Shift** hides edges  
- Tape Measure: **Ctrl** on the second click creates a construction guide  
- Protractor: **Ctrl** on the third click creates guide lines  
- Polygon: type `8s` then Enter to set side count before picking the radius  

Arrow keys during a tool lock axes: Right = X (red), Left = Y (green), Up = Z (blue), Down = parallel to the inferred edge. Hold **Shift** to lock the current inference. Type a length and press Enter. Rectangle accepts `width, depth`. Circle accepts a segment count such as `24s`, then a radius.

**Units** — **Window → Units** sets the model unit for bare numbers and VCB display (`m`, `mm`, `cm`, `ft`, `in`). Typed lengths always accept mixed units: `10'` (feet), `6"` (inches), `5'6"` (feet+inches), `100mm`, `30cm`, `2.5m`. Geometry is stored in metres internally.

**Copy arrays (SketchUp power workflow)** — Move or Rotate, tap **Ctrl** to copy, place the first copy, then type `5x` (external) or `3/` (internal) and Enter. You can retype another count before switching tools.

**Push/Pull** — **Double-click** a face to repeat the last extrusion distance. Extruding a lone face builds a closed solid (bottom + sides + top). Pushing a face drawn on another face into a solid chops a pocket; push through the thickness to punch an opening.

**Offset** — Offsets every edge of the face evenly (inset).

**Power-user shortcuts** — `U` / `Shift+U` unhide last/all · `Ctrl+H` hide · `Ctrl+Shift+H` hide rest of model · `Y` reverse faces · `Shift+V` paste in place · `Ctrl+C` copy · `Ctrl+Shift+G` delete guides · `Ctrl+Shift+X` face style · `W` zoom window · `[` previous view.

See the [SketchUp case study](sketchup-case-study.md) for research sources and the full mapping.

Ctrl+Z and Ctrl+S remain available.

## Inference and working planes

Starting a draw on a face locks that face as the **working plane**; further points stay on the plane unless you lock an axis or pick a stronger snap. Snaps include endpoint, midpoint, on edge, on face, from-point alignments, and axis / parallel locks. Inference guides and snap labels appear while drawing. Drawing a closed shape on a face splits that face so the inner face can be pushed or pulled.

## Files

| Format | Role |
| --- | --- |
| `.blend` | Native save / open |
| Wavefront OBJ | Export (enabled in the lite build) |
| glTF | Export via the `io_scene_gltf2` Python add-on |

## More documentation

- [Documentation index](../README.md)  
- [Windows build](../build/windows.md)  
- [Licensing / attribution](../licensing/attribution.md)  
