from ninja import NinjaAPI
from marketplace.api import router as marketplace_router
from products.api import router as products_router
from vendor.api import router as vendor_router
from .dashboard import router as dashboard_router
from export.api import router as export_router

api = NinjaAPI()

# Include marketplace APIs
api.add_router("/marketplace/", marketplace_router)

# Include products APIs
api.add_router("/products/", products_router)

# Include vendor APIs
api.add_router("/vendor/", vendor_router)

# Include dashboard APIs
api.add_router("/dashboard/", dashboard_router)

# Include export APIs
api.add_router("/export/", export_router)

# Add other APIs here as needed
# api.add_router("/vendor/", vendor_api) 