from django.contrib import admin

from .models import Assignment, AssignmentRelationship, ICS205Plan, PlanRevision

admin.site.register(ICS205Plan)
admin.site.register(PlanRevision)
admin.site.register(Assignment)
admin.site.register(AssignmentRelationship)
