# O-Form user overview

O-Form is the 3D modelling application in **OSAS** (Open Source Architecture Suit). It is built for focused solid modelling: draw on faces, push and pull, measure as you go.

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
| SketchUp `.skp`, BIM/IFC, AI features | Not supported / not claimed |

O-Form is **not** affiliated with the Blender Foundation or Trimble. It does not use SketchUp files, icons, or artwork.

## Workspace

On launch, O-Form opens an editable mesh named `Model` in edit mode. Tab does not leave edit mode. The shell follows the same pattern as **O-Draft**: menus, left tools/side panels, solid canvas, status bar, and an Ask channel.

- **Menus:** File, Edit, View, Camera, Draw, Tools, Solids, Window, Help  
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
- **Double-click** a group or component to edit inside it. **Esc** (with nothing pending) closes back out.  
- **Edit → Explode** merges the selection into the current context.  
- Components share a mesh definition; **Instance Component** places another linked copy.

**Selection (SketchUp-style)**

- **Single-click** — one entity (edge, face, or group/component).  
- **Double-click** — related geometry (face + bounding edges, or edge + adjacent faces).  
- **Triple-click** — all connected geometry in the current edit context.  
- Keyboard alternatives: **Alt+1** / **Alt+2** / **Alt+3**. Shift/Ctrl extends selection; drag for window/crossing.  
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

Arrow keys during a tool lock axes: Right = X (red), Left = Y (green), Up = Z (blue), Down = parallel to the inferred edge. Type a length and press Enter. Rectangle accepts `width, depth`. Circle accepts a segment count such as `24s`, then a radius.

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
