# -*- coding: utf-8 -*-
"""
lx_pathway_plugin Django application initialization.
"""
try:
    # Use the Open edX app config if we can
    from .openedx_apps import LxPathwayPluginAppConfig
except ModuleNotFoundError:
    # Otherwise, fall back to the LabXchange app config
    from .lx_apps import LxPathwayPluginAppConfig
