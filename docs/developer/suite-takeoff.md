# Suite take-off coherence — Finch · Tren · Falcon

One ShilpiDB store (`127.0.0.1:7420`), one identity, two payload layers.

## Identity (shared)

| Key | Meaning |
|-----|---------|
| `drawing_id` | Stable UUID (`oform_drawing_id`) |
| `slot` | `SlotFor(drawing_id)` — same algorithm as Falcon `ShilpiTakeoff.SlotFor` |
| `project_office_id` | AORMS / suite project |
| `project_ref` | Optional `{v, company_uuid, project_id}` |

```
id = (kind << 56) | (slot << 32) | n
```

## Layers on the same slot

| kind | format | Consumer |
|------|--------|----------|
| **1** | `hcw-takeoff-shilpi` header | Falcon take-off import |
| **3–8** | bridge rows (walls, openings, …) | Falcon / Tren |
| **20** | `oform-ifc-shilpi` header | Finch IFC sidecar |
| **21** | IFC element JSON | Finch |

## Finch modules

| Module | Role |
|--------|------|
| `suite_ids.py` | SlotFor / MakeId / drawing_id (Falcon vectors) |
| `bridge_rows.py` | IfcWall/Slab/… → bridge row mm |
| `takeoff.py` | Push/read `hcw-takeoff-shilpi` |
| `shilpi_ifc.py` | Kinds 20–21 sidecar |
| `ifc4.py` | `.ifc` file I/O |

## UI

**BIM → Push BIM + Take-off** writes both layers with one `drawing_id`/`slot`.

## Protocol

`recording` header → rows → delete stale → `complete` → `save` (same as Tren `takeoff.record`).

## Project folder

Kivo scaffolds `osas.project.json` with a shared `drawing_id`. See [osas-project-folder.md](osas-project-folder.md).

## Project folder

Kivo scaffolds `osas.project.json` with a shared `drawing_id`. See [osas-project-folder.md](osas-project-folder.md).

## Project folder

Kivo scaffolds `osas.project.json` with a shared `drawing_id`. See [osas-project-folder.md](osas-project-folder.md).
