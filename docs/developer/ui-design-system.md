# O-Form design system & workspace specification

**Status:** Product UI matches **O-Draft WinUI** Density + ColorTokens.  
**Flag:** `design.UI_SHELL_V2` off.  
**Sources:** `O-DRAFT/apps/aad-winui/Density.cs`, `Themes/ColorTokens.xaml`, `ToolCatalog`.

---

## 1. Design tokens (ColorTokens.xaml)

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `fog` | `#E4EAF2` | `#1B1B1B` | App chrome |
| `panel` | `#EEF2F8` | `#202020` | Side pane |
| `surface` | `#FFFFFF` | `#2C2C2C` | Controls |
| `ink` / accent | `#1A2332` | `#60CDFF` | Text / chrome accent |
| `muted` | `#64748B` | `#C8C8C8` | Secondary |
| `edge` | `#D8DEE8` | `#3D3D3D` | Borders |
| `selected` | `#FFFFFF` | `#1A3B5C` | Selected control |
| `ai` | `#1A2332` | `#60CDFF` | Ask top accent |
| `cad` | `#0F7B3A` | `#6CCB8A` | VCB left edge |
| `canvas` | `#FFFFFF` | `#000000` | Modelling paper |
| mark plate | `#C6E6D3` | | Suite logo only |

Density: **32 DIP** tool buttons, **280 DIP** side panel, Ask bar max **600**, strip column **40**.

---

## 2. Workspace layout (O-Draft WinUI)

```
┌──────────────────────────────────────────────────────────────┐
│  Menu bar                                                     │
├────┬───────────┬─────────────────────────────────────────────┤
│ 32 │ 280 panel │              VIEWPORT                       │
│ px │ Entity    │           (solid paper)                     │
│tool│ Ask       │                                             │
│strip│           │         [ Ask bar · bottom-centre ]         │
├────┴───────────┴─────────────────────────────────────────────┤
│ Status · theme · VCB                                          │
└──────────────────────────────────────────────────────────────┘
```

Tool strip catalog mirrors O-Draft `ToolCatalog` (Select, Line, Circle, Arc, Rect, Move, Rotate, Offset, Push/Pull, Trim, Eraser, Measure, Paint).

---

## 3. Command taxonomy

| Group | Essential (always visible or one click) | Advanced (overflow / search / context) |
| --- | --- | --- |
| Draw | Line, Rectangle, Circle, Arc, Polygon | Freehand |
| Edit | Select, Move, Rotate, Scale, Offset | Eraser modes, Reverse Faces |
| Model | Push/Pull, Boolean menu | Follow Path, Trim, Outer Shell |
| Organize | Group, Component | Explode, Instance, Hide Rest |
| Inspect | Measure, Entity Properties | Protractor, Inspect Solid, Guides |
| View | Orbit, Pan, Zoom, Extents | Face Style, Zoom Window, Previous, Standard views |

Architecture-friendly names preferred (`Follow Path` may replace `Follow Me` in chrome; keep operator id stable during migration).

---

## 4. Interaction contracts

| Action | Contract |
| --- | --- |
| Select | Click entity · double related · triple connected; Shift extend; right-click context (phase 3+) |
| Draw | Click-release; inference snap; Shift locks; arrows lock axes; type → Enter for VCB |
| Transform | Preview in viewport; Ctrl copy where applicable; arrays `Nx` / `N/` after copy |
| Cancel | Esc clears in-progress state before Undo |
| Numeric | Always typeable without focusing a dialog; units in status |

---

## 5. Migration rules

- Geometry, undo, file I/O stay until replacements are tested.  
- `UI_SHELL_V2=False` keeps today’s shell.  
- New chrome consumes existing `oform.tool_*` operators.  
- Retire PROPERTIES-as-rail only after left rail + primary strip work.  
- No Blender upstream remotes or sync assumptions.
