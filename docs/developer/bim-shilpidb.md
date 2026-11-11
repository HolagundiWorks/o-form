# Myna3D BIM ↔ ShilpiDB ↔ MynaCAD

Myna3D stores IFC/BIM **semantics** in the same ShilpiDB suite server MynaCAD uses.

## Defaults

| | Address | Notes |
|---|---|---|
| `shilpid` | `127.0.0.1:7420` | Same as MynaCAD take-off / `vdb.connect` |
| `shilpi-http` | `127.0.0.1:7421` | JSON gateway for Python |
| Data file (if Myna3D starts the server) | `%LocalAppData%\OSAS\oform\bim.vdb` | If 7420 already answers (MynaCAD), that store is reused |

## Record layout

Same id scheme as MynaCAD take-off / MynaOps (`SlotFor` fold — see `suite_ids.py`):

```
id = (kind << 56) | (slot << 32) | n
```

| kind | Meaning |
|------|---------|
| **1** | Suite take-off header `hcw-takeoff-shilpi` |
| **3–8** | Bridge rows (wall, opening, column, lintel, room, slab) |
| **20** | IFC sidecar header `oform-ifc-shilpi` |
| **21** | IFC element row |

See [suite-takeoff.md](suite-takeoff.md) for full coherence rules.

## UI

- **BIM → Push BIM + Take-off** — IFC sidecar + suite take-off (MynaOps-readable)
- **BIM → Push Take-off (suite)** — kinds 1+3–8 only
- **AORMS Project Id…** — shared `project_office_id`

## Not BlenderBIM

Native Myna3D BIM + ShilpiDB. Does not embed Bonsai.
