# -*- coding: utf-8 -*-
"""
lx_pathway_plugin Django application initialization.
"""
from django.apps import AppConfig
from openedx.core.djangoapps.plugins.constants import PluginSettings, PluginURLs, ProjectType, SettingsType


class LxPathwayPluginAppConfig(AppConfig):
    """
    Configuration for the lx_pathway_plugin Django plugin application.

    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """

    name = 'lx_pathway_plugin'
    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.CMS: {
                # The namespace to provide to django's urls.include.
                PluginURLs.NAMESPACE: 'lx_pathway_plugin',
            },
            ProjectType.LMS: {
                # The namespace to provide to django's urls.include.
                PluginURLs.NAMESPACE: 'lx_pathway_plugin',
                # use a different set of URLs/views in the LMS
                PluginURLs.RELATIVE_PATH: 'urls_lms',
            },
        },
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.PRODUCTION: {PluginSettings.RELATIVE_PATH: 'settings'},
            },
            ProjectType.LMS: {
                SettingsType.PRODUCTION: {PluginSettings.RELATIVE_PATH: 'settings'},
            },
        },
    }

    def ready(self):
        """
        Load signal handlers when the app is ready.
        """
