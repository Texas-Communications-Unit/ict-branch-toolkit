from django.conf import settings
from django.db import models

if settings.ENABLE_GIS:
    from django.contrib.gis.db import models as gis_models

    class PortablePointField(gis_models.PointField):
        """A PostGIS point with a JSON fallback for credential-free SQLite tests."""

else:

    class PortablePointField(models.JSONField):
        """Store GeoJSON-like coordinates when a spatial database is unavailable."""

        def __init__(
            self,
            *args,
            srid=4326,
            geography=True,
            spatial_index=True,
            **kwargs,
        ):
            self.srid = srid
            self.geography = geography
            self.spatial_index = spatial_index
            super().__init__(*args, **kwargs)

        def deconstruct(self):
            name, path, args, kwargs = super().deconstruct()
            path = "apps.sites.fields.PortablePointField"
            kwargs.update(
                {
                    "srid": self.srid,
                    "geography": self.geography,
                    "spatial_index": self.spatial_index,
                }
            )
            return name, path, args, kwargs
