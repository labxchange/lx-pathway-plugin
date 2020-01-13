"""
Common settings for the lx-pathway-plugin app.

See apps.py for details on how this sort of plugin configures itself for
integration with Open edX.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

# Register settings: ###########################################################


def plugin_settings(settings):
    """
    Add our default settings to the edx-platform settings. Other settings files
    may override these values later, e.g. via envs/private.py.
    """
    env_tokens = getattr(settings, 'ENV_TOKENS', {})

    # LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES:
    # The list of usernames that have permission to use this API
    # (primarily the LabXchange service user)
    settings.LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES = env_tokens.get(
        'LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES',
        [],
    )
    assert isinstance(settings.LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES, list)
