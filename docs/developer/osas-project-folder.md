# OSAS project folder — O-Studio · O-Draft · O-Form · ShilpiDB

Creating a project in **O-Studio** scaffolds a folder beside the company file:

```text
<company_dir>/projects/<slug>-<id>/
  osas.project.json      # suite envelope
  draft/model.dxf        # O-Draft starter
  draft/project.json     # O-Draft wizard seed
  form/model.blend       # O-Form model (filled on first save)
  shilpi/project.vdb     # project ShilpiDB (created on first bind)
```

## Identity

| Field | Role |
|-------|------|
| `project_ref` | O-Studio `ProjectRef` (`company_uuid` + `project_id`) |
| `drawing_id` | Shared UUID for take-off + IFC sidecar slots |
| `project_office_id` | AORMS id when linked, else `company_uuid:project_id` |

## Live sync

`sync.mode = "live"` — O-Form polls ShilpiDB and pushes BIM/take-off when the model changes; O-Draft / O-CoreOp read the same `hcw-takeoff-shilpi` header on the same `drawing_id`.

## O-Form

**File → Open Project Folder…** binds `osas.project.json`, starts/joins ShilpiDB on `shilpi/project.vdb`, enables live sync.

See also [suite-takeoff.md](suite-takeoff.md) and [bim-shilpidb.md](bim-shilpidb.md).
