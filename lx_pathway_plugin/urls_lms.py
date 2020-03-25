"""
LMS URL configuration for lx-pathway-plugin.
"""
from django.conf.urls import include, url

from . import views

urlpatterns = [
    url(r'^api/lx-pathways/v1/', include([
        # Get a specific pathway:
        url(r'pathway/(?P<pathway_key_str>[^/]+)/$', views.PathwayView.as_view()),
    ])),
]
