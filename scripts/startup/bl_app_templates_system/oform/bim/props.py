# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""BIM ID-properties on Scene / Object (safe read during draw)."""

from __future__ import annotations

PROP_IFC_CLASS = "oform_ifc_class"
PROP_IFC_GUID = "oform_ifc_guid"
PROP_IFC_NAME = "oform_ifc_name"
PROP_IFC_TYPE = "oform_ifc_type"  # type name / component definition bridge
PROP_STOREY = "oform_ifc_storey"  # storey name on the scene list
PROP_MATERIAL = "oform_ifc_material"

# Scene-level spatial project
SCENE_PROJECT = "oform_bim_project"
SCENE_SITE = "oform_bim_site"
SCENE_BUILDING = "oform_bim_building"
SCENE_STOREYS = "oform_bim_storeys"  # JSON list of {name, elevation, guid}
SCENE_ACTIVE_STOREY = "oform_bim_storey"


def get_str(id_data, key: str, default: str = "") -> str:
    if id_data is None:
        return default
    value = id_data.get(key, default)
    if value is None:
        return default
    return str(value)


def set_str(id_data, key: str, value: str) -> None:
    if id_data is None:
        return
    text = (value or "").strip()
    if text:
        id_data[key] = text
    elif key in id_data:
        del id_data[key]


def ifc_class_of(obj) -> str:
    return get_str(obj, PROP_IFC_CLASS)


def set_ifc_class(obj, ifc_class: str) -> None:
    set_str(obj, PROP_IFC_CLASS, ifc_class)


def guid_of(obj) -> str:
    return get_str(obj, PROP_IFC_GUID)


def set_guid(obj, guid: str) -> None:
    set_str(obj, PROP_IFC_GUID, guid)


def storey_of(obj) -> str:
    return get_str(obj, PROP_STOREY)


def set_storey(obj, storey: str) -> None:
    set_str(obj, PROP_STOREY, storey)


def element_name(obj) -> str:
    custom = get_str(obj, PROP_IFC_NAME)
    if custom:
        return custom
    return obj.name if obj is not None else ""
