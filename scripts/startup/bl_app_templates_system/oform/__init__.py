# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""O-Form application template.

Blender imports this as ``bl_app_templates_system.oform`` and calls ``register``
inside ``RestrictBlend``, so this module must not touch ``bpy.context``.
Keymaps, the window layout, and the factory scene run from load handlers.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import tools
import ui

_registered = False


def register():
    global _registered
    if _registered:
        return
    ui.register_properties()
    tools.register()
    ui.register()
    _registered = True


def unregister():
    global _registered
    if not _registered:
        return
    ui.unregister()
    tools.unregister()
    ui.unregister_properties()
    _registered = False
