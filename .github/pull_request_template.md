## Summary

<!-- What changed and why (O-Form product / docs / build). -->

## Type

- [ ] Documentation
- [ ] O-Form app template (`scripts/startup/bl_app_templates_system/oform/`)
- [ ] Build / CMake / packaging
- [ ] Window manager / other C++
- [ ] Other

## Test plan

- [ ] `oform` selftest prints `OFORM_SELFTEST_OK` (if mesh/tools touched)
- [ ] Manual launch of `oform.exe` (if UI/branding touched)
- [ ] Documentation links checked (if docs touched)
- [ ] `python tools/oform_check_independence.py` exits 0 (if remotes/docs/automation touched)

## Independence

- [ ] No Blender upstream remote added
- [ ] No upstream fetch/merge/rebase/sync workflow introduced

## Licensing

- [ ] No license texts, `AUTHORS`, or third-party notices were removed or replaced
- [ ] New files include an appropriate SPDX header when applicable
