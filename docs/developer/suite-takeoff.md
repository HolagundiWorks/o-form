# Suite take-off coherence — O-Form · O-Draft · O-CoreOp

One ShilpiDB store (`127.0.0.1:7420`), one identity, two payload layers.

## Identity (shared)

| Key | Meaning |
|-----|---------|
| `drawing_id` | Stable UUID (`oform_drawing_id`) |
| `slot` | `SlotFor(drawing_id)` — same algorithm as O-CoreOp `ShilpiTakeoff.SlotFor` |
| `project_office_id` | AORMS / suite project |
| `project_ref` | Optional `{v, company_uuid, project_id}` |

```
id = (kind << 56) | (slot << 32) | n
```

## Layers on the same slot

| kind | format | Consumer |
|------|--------|----------|
| **1** | `hcw-takeoff-shilpi` header | O-CoreOp take-off import |
| **3–8** | bridge rows (walls, openings, …) | O-CoreOp / O-Draft |
| **20** | `oform-ifc-shilpi` header | O-Form IFC sidecar |
| **21** | IFC element JSON | O-Form |

## O-Form modules

| Module | Role |
|--------|------|
| `suite_ids.py` | SlotFor / MakeId / drawing_id (O-CoreOp vectors) |
| `bridge_rows.py` | IfcWall/Slab/… → bridge row mm |
| `takeoff.py` | Push/read `hcw-takeoff-shilpi` |
| `shilpi_ifc.py` | Kinds 20–21 sidecar |
| `ifc4.py` | `.ifc` file I/O |

## UI

**BIM → Push BIM + Take-off** writes both layers with one `drawing_id`/`slot`.

## Protocol

`recording` header → rows → delete stale → `complete` → `save` (same as O-Draft `takeoff.record`).

## Project folder

O-Studio scaffolds `osas.project.json` with a shared `drawing_id`. See [osas-project-folder.md](osas-project-folder.md).

## Project folder

O-Studio scaffolds `osas.project.json` with a shared `drawing_id`. See [osas-project-folder.md](osas-project-folder.md).

## Project folder

O-Studio scaffolds `osas.project.json` with a shared `drawing_id`. See [osas-project-folder.md](osas-project-folder.md).
