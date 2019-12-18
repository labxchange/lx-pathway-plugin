"""
Common settings for the lx-pathway-plugin app.

See apps.py for details on how this sort of plugin configures itself for
integration with Open edX.
"""
# Declare defaults: ############################################################

# The list of usernames that have permission to use this API
# (primarily the LabXchange service user)
LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES = []

# Register settings: ###########################################################


def plugin_settings(settings):
    """
    Add our default settings to the edx-platform settings. Other settings files
    may override these values later, e.g. via envs/private.py.
    """
    settings.LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES = LX_PATHWAY_PLUGIN_AUTHORIZED_USERNAMES
