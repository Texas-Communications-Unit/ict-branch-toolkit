from rest_framework.routers import DefaultRouter

from .views import AssetCheckoutViewSet, AssetViewSet, ProgrammingRecordViewSet

router = DefaultRouter()
router.register("inventory-assets", AssetViewSet, basename="inventory-asset")
router.register("inventory-checkouts", AssetCheckoutViewSet, basename="inventory-checkout")
router.register("inventory-programming", ProgrammingRecordViewSet, basename="inventory-programming")

urlpatterns = router.urls
