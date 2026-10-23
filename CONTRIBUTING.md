# Contributing to O-Form

O-Form is developed by Human Centric Works for **OSAS** (Open Source Architecture Suit). It is an independently maintained product whose source tree originated as a Blender 5.2.3 LTS clone.

**Open Source. Built for Architects. Driven by Community.**

**Policy:** No Blender upstream. No upstream merges. No upstream synchronization. No upstream development dependency.

Full developer guide: [docs/developer/architecture.md](docs/developer/architecture.md).

## Before you start

1. Read the [developer guide](docs/developer/architecture.md) and [user overview](docs/user/overview.md).  
2. Prefer product changes under `scripts/startup/bl_app_templates_system/oform/`.  
3. Do not remove or rewrite license texts, `AUTHORS`, or third-party notices.  
4. Do **not** add a Blender upstream remote, restore upstream sync scripts, or rewrite Git history.  
5. Confirm remotes with `git remote -v` — `origin` should be https://github.com/HolagundiWorks/o-form.git.

## Issues and features

- File issues and feature requests on **this** repository: https://github.com/HolagundiWorks/o-form/issues  
- Describe the O-Form workflow impact, steps to reproduce, and platform (Windows build is the verified product path).  
- Do not open Blender Foundation tracker tickets expecting them to be handled here, and do not expect projects.blender.org review of O-Form patches.

## Branches and commits

- Base branch: `main`  
- Feature branches: `feature/…`, `fix/…`, or `docs/…` from up-to-date `main`  
- Commits: short imperative subject; body explains **why** when non-obvious  
- Keep documentation updates in the same PR when behaviour or workflow changes  

## Pull requests

Open PRs against `main` on https://github.com/HolagundiWorks/o-form. Use the repository PR template.

Include:

- Summary of what changed and why  
- Test plan (selftest and/or manual steps)  
- Note if docs-only, template Python, CMake, or C++  
- Confirmation that no Blender upstream remote or sync workflow was introduced  

### Review

- Prefer small, reviewable diffs  
- Call out license or third-party dependency changes explicitly  
- External technical reading (including Blender docs) is fine; **copying** external code requires normal technical, licensing, security, and provenance review in the PR  

## Required checks

| Change type | Minimum verification |
| --- | --- |
| Mesh / tools | `oform` selftest prints `OFORM_SELFTEST_OK` |
| UI / branding | Launch `oform.exe`; About/splash/status look correct |
| Docs | Internal links resolve; no new “merge Blender upstream” instructions |
| Remotes / automation | `python tools/oform_check_independence.py` exits 0 |

Build steps: [docs/build/windows.md](docs/build/windows.md).  
Releases: [docs/developer/releases.md](docs/developer/releases.md).

## Dependencies and licenses

- Project policy: [docs/licensing/policy.md](docs/licensing/policy.md).  
- New third-party code must keep compatible licenses and attribution (`release/license/`, `NOTICE`, file SPDX headers).  
- Do not rebrand third-party projects as O-Form.  
- Do not add a conflicting license to inherited Blender code.  
- Do not delete `LICENSE`, `COPYING`, `NOTICE`, or third-party notice files.  
- Map: [docs/licensing/attribution.md](docs/licensing/attribution.md).

## Security

No `SECURITY.md` is published yet. Report security issues privately via the HolagundiWorks organization contact on GitHub until a public policy exists. Do not file sensitive exploits in public issues.

## License

O-Form is **GPL-2.0-or-later**. Contributions are expected under the same terms as the files you modify, typically **GPL-2.0-or-later**, unless a file header states a compatible existing license that must be preserved.
