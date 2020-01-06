"""
Admin site for LabXchange pathways
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from django.contrib import admin
from .models import Pathway


@admin.register(Pathway)
class PathwayAdmin(admin.ModelAdmin):
    """
    Definition of django admin UI for Pathways
    """
    fields = ("id", "uuid", "owner_user", "owner_group", "draft_data", "published_data")
    list_display = ("title", "uuid")
    raw_id_fields = ("owner_user", "owner_group")
    readonly_fields = ["id", "uuid"]
