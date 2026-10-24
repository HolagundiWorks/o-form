# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""O-Form BIM engine — spatial structure, classification, IFC4 + ShilpiDB.

Native implementation (not BlenderBIM / Bonsai). Geometry stays in
``tools`` / ``geom``; this package adds IFC semantics, IFC4 files, and
ShilpiDB sync shared with O-Draft (``127.0.0.1:7420``).
"""

from __future__ import annotations

from . import ops
from . import props
from . import spatial
from . import taxonomy

__all__ = (
    "ops",
    "props",
    "spatial",
    "taxonomy",
    "register",
    "unregister",
)


def register():
    ops.register()


def unregister():
    ops.unregister()
