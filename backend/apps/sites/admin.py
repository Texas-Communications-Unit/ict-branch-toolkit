from django.contrib import admin

from .models import ManualRing, RadioSite, SiteAssignment

admin.site.register(RadioSite)
admin.site.register(ManualRing)
admin.site.register(SiteAssignment)
