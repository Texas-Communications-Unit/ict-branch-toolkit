from rest_framework.routers import DefaultRouter

from .views import (
    AssetAttachmentViewSet,
    AssetCheckoutViewSet,
    AssetImportViewSet,
    AssetViewSet,
    ChargingRecordViewSet,
    MaintenanceRecordViewSet,
    ProgrammingRecordViewSet,
)

router = DefaultRouter()
router.register("inventory-assets", AssetViewSet, basename="inventory-asset")
router.register("inventory-checkouts", AssetCheckoutViewSet, basename="inventory-checkout")
router.register("inventory-programming", ProgrammingRecordViewSet, basename="inventory-programming")
router.register("inventory-maintenance", MaintenanceRecordViewSet, basename="inventory-maintenance")
router.register("inventory-charging", ChargingRecordViewSet, basename="inventory-charging")
router.register("inventory-attachments", AssetAttachmentViewSet, basename="inventory-attachment")
router.register("inventory-asset-imports", AssetImportViewSet, basename="inventory-asset-import")

urlpatterns = router.urls
