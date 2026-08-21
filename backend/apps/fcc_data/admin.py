from django.contrib import admin

from .models import (
    AntennaStructure,
    FccImportBatch,
    UlsEmission,
    UlsFrequency,
    UlsLicense,
    UlsLocation,
)

admin.site.register(FccImportBatch)
admin.site.register(AntennaStructure)
admin.site.register(UlsLicense)
admin.site.register(UlsLocation)
admin.site.register(UlsFrequency)
admin.site.register(UlsEmission)
