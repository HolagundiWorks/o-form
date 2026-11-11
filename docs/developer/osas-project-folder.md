# OSAS project folder — MynaHub · MynaCAD · Myna3D · ShilpiDB

Creating a project in **MynaHub** scaffolds a folder beside the company file:

```text
<company_dir>/projects/<slug>-<id>/
  osas.project.json      # suite envelope
  draft/model.dxf        # MynaCAD starter
  draft/project.json     # MynaCAD wizard seed
  form/model.blend       # Myna3D model (filled on first save)
  shilpi/project.vdb     # project ShilpiDB (created on first bind)
```

## Identity

| Field | Role |
|-------|------|
| `project_ref` | MynaHub `ProjectRef` (`company_uuid` + `project_id`) |
| `drawing_id` | Shared UUID for take-off + IFC sidecar slots |
| `project_office_id` | AORMS id when linked, else `company_uuid:project_id` |

## Live sync

`sync.mode = "live"` — Myna3D polls ShilpiDB and pushes BIM/take-off when the model changes; MynaCAD / MynaOps read the same `hcw-takeoff-shilpi` header on the same `drawing_id`.

## Myna3D

**File → Open Project Folder…** binds `osas.project.json`, starts/joins ShilpiDB on `shilpi/project.vdb`, enables live sync.

See also [suite-takeoff.md](suite-takeoff.md) and [bim-shilpidb.md](bim-shilpidb.md).
