"""
Studio URL configuration for lx-pathway-plugin.
"""
from django.conf.urls import include, url

from . import views

urlpatterns = [
    url(r'^api/lx-pathways/v1/', include([
        url(r'pathway/$', views.create_pathway),
        # Get/edit/delete a specific pathway:
        url(r'pathway/(?P<pathway_key_str>[^/]+)/$', views.PathwayView.as_view()),
        # Publish or revert changes to a pathway:
        url(r'pathway/(?P<pathway_key_str>[^/]+)/publish/$', views.PathwayPublishView.as_view()),
    ])),
]
