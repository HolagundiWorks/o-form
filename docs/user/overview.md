# O-Form user overview

O-Form is the 3D modelling application in **OSAS** (Open Source Architecture Suit). It is built for focused solid modelling: draw on faces, push and pull, measure as you go.

**Principle:** Open Source. Built for Architects. Driven by Community.

## Status

| Area | Status |
| --- | --- |
| Windows desktop lite build (`oform.exe`) | Implemented |
| Modelling template (single view, left tool pane) | Implemented |
| Draw / edit / view tools listed below | Implemented |
| Headless mesh selftest | Implemented |
| Follow Me, Tape Measure, Groups, Components | Not implemented |
| Full parallel / perpendicular / intersection inference | Not implemented |
| macOS / Linux product builds | Not verified as product targets |
| SketchUp `.skp`, BIM/IFC, AI features | Not supported / not claimed |

O-Form is **not** affiliated with the Blender Foundation or Trimble. It does not use SketchUp files, icons, or artwork.

## Workspace

On launch, O-Form opens an editable mesh named `Model` in edit mode. Tab does not leave edit mode.

- **Menus:** File, Edit, View, Camera, Draw, Tools, Window, Help  
- **Left pane:** Select, Draw, Edit, View tool groups  
- **View:** Perspective, Z-up, RGB axes, ground grid  
- **Status:** Tool hint, measurements box, Human Centric Works · Hospet  

**Navigation:** Middle mouse orbit, Shift+middle mouse pan, mouse wheel zoom.  
**Camera menu:** Top, Front, Right, Iso, perspective, parallel, zoom extents.

## Tools and shortcuts

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

Arrow keys during a tool lock axes: Right = X (red), Left = Y (green), Up = Z (blue), Down = parallel to the inferred edge. Type a length and press Enter. Rectangle accepts `width, depth`. Circle accepts a segment count such as `24s`, then a radius.

Ctrl+Z and Ctrl+S remain available.

## Inference (current)

Endpoint, midpoint, on edge, on face, and axis direction. Drawing a closed shape on a face splits that face so the inner face can be pushed or pulled.

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
