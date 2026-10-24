# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""IFC building-element taxonomy used by the O-Form BIM engine."""

from __future__ import annotations

# Spatial structure (containers — scene / collections, not mesh products).
SPATIAL = (
    ("IfcProject", "Project"),
    ("IfcSite", "Site"),
    ("IfcBuilding", "Building"),
    ("IfcBuildingStorey", "Storey"),
    ("IfcSpace", "Space"),
)

# Product elements (mesh objects).
ELEMENTS = (
    ("IfcWall", "Wall"),
    ("IfcWallStandardCase", "Wall (standard)"),
    ("IfcSlab", "Slab / Floor"),
    ("IfcRoof", "Roof"),
    ("IfcColumn", "Column"),
    ("IfcBeam", "Beam"),
    ("IfcDoor", "Door"),
    ("IfcWindow", "Window"),
    ("IfcStair", "Stair"),
    ("IfcRailing", "Railing"),
    ("IfcCurtainWall", "Curtain Wall"),
    ("IfcMember", "Member"),
    ("IfcPlate", "Plate"),
    ("IfcCovering", "Covering"),
    ("IfcFurnishingElement", "Furnishing"),
    ("IfcBuildingElementProxy", "Proxy / Generic"),
)

ALL_IFC_CLASSES = SPATIAL + ELEMENTS

ELEMENT_IDS = tuple(item[0] for item in ELEMENTS)
SPATIAL_IDS = tuple(item[0] for item in SPATIAL)

# Default when auto-classify fails.
DEFAULT_ELEMENT = "IfcBuildingElementProxy"


def label_of(ifc_class: str) -> str:
    for key, label in ALL_IFC_CLASSES:
        if key == ifc_class:
            return label
    return ifc_class or "—"


def is_spatial(ifc_class: str) -> bool:
    return ifc_class in SPATIAL_IDS


def is_element(ifc_class: str) -> bool:
    return ifc_class in ELEMENT_IDS
