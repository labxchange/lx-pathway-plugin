"""
Django application initialization for use inside the LabXchange application.

Here, the lx_pathway_plugin is just a normal app, not a Django plugin.
"""
from django.apps import AppConfig


class LxPathwayPluginAppConfig(AppConfig):
    """
    Configuration for the lx_pathway_plugin Django application.
    """

    name = 'lx_pathway_plugin'
