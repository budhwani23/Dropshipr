from ninja.router import Router
from django.utils import timezone
from django.db.models import Count, Avg, Q, Max
from datetime import timedelta

from marketplace.models import Store, Marketplace
from products.models import Product, Upload
from vendor.models import Vendor, VendorPrice
from export.models import ExportArtifact

router = Router()


def _filter_products(marketplace_id=None, store_id=None, vendor_id=None):
    qs = Product.objects.all()
    if marketplace_id:
        qs = qs.filter(marketplace_id=marketplace_id)
    if store_id:
        qs = qs.filter(store_id=store_id)
    if vendor_id:
        qs = qs.filter(vendor_id=vendor_id)
    return qs


@router.get("/summary")
def dashboard_summary(request, marketplace_id: int | None = None, store_id: int | None = None, vendor_id: int | None = None):
    now = timezone.now()
    products_qs = _filter_products(marketplace_id, store_id, vendor_id)

    total_products = products_qs.count()

    active_stores = Store.objects.filter(is_active=True)
    if marketplace_id:
        active_stores = active_stores.filter(marketplace_id=marketplace_id)
    active_stores_count = active_stores.count()

    vendors_covered = products_qs.values('vendor_id').distinct().count()

    # Needs rescrape: approximate using VendorPrice.error_code not empty OR could be tracked via Scrape if available
    errors_24h = VendorPrice.objects.filter(
        product__in=products_qs,
        scraped_at__gte=now - timedelta(hours=24),
    ).exclude(Q(error_code__isnull=True) | Q(error_code__exact='')).count()

    # Items needing rescrape: approximate as latest vendor price with non-empty error
    needs_rescrape = VendorPrice.objects.filter(
        product__in=products_qs,
    ).exclude(Q(error_code__isnull=True) | Q(error_code__exact='')).values('product_id').distinct().count()

    # Uploads today: infer by expires_at window (created at ~ now + 30d)
    uploads_today = Upload.objects.filter(
        expires_at__gte=now + timedelta(days=29),
        expires_at__lte=now + timedelta(days=30)
    ).count()

    return {
        "totalProducts": total_products,
        "activeStores": active_stores_count,
        "vendorsCovered": vendors_covered,
        "itemsNeedingRescrape": needs_rescrape,
        "recentErrors24h": errors_24h,
        "uploadsToday": uploads_today,
    }


@router.get("/stores")
def dashboard_stores(request, marketplace_id: int | None = None):
    stores = Store.objects.select_related('marketplace')
    if marketplace_id:
        stores = stores.filter(marketplace_id=marketplace_id)

    # Aggregate product and vendor counts per store
    prod_counts = (Product.objects
                   .filter(store__in=stores)
                   .values('store_id')
                   .annotate(products=Count('id'), vendors=Count('vendor_id', distinct=True)))
    store_to_counts = {x['store_id']: x for x in prod_counts}

    # Last scrape per store via VendorPrice
    last_scrape = (VendorPrice.objects
                   .filter(product__store__in=stores)
                   .values('product__store_id')
                   .annotate(last=Max('scraped_at')))
    store_to_last = {x['product__store_id']: x['last'] for x in last_scrape}

    # Last export timestamps
    last_price = (ExportArtifact.objects
                  .filter(store__in=stores, kind=ExportArtifact.KIND_PRICE, status=ExportArtifact.STATUS_READY)
                  .values('store_id')
                  .annotate(last=Max('generated_at')))
    last_inventory = (ExportArtifact.objects
                      .filter(store__in=stores, kind=ExportArtifact.KIND_INVENTORY, status=ExportArtifact.STATUS_READY)
                      .values('store_id')
                      .annotate(last=Max('generated_at')))
    store_to_last_price = {x['store_id']: x['last'] for x in last_price}
    store_to_last_inventory = {x['store_id']: x['last'] for x in last_inventory}

    data = []
    for s in stores:
        counts = store_to_counts.get(s.id, {"products": 0, "vendors": 0})
        mydeal_ok = True
        try:
            code = str(getattr(s.marketplace, 'code', '')).lower()
            name = str(getattr(s.marketplace, 'name', '')).lower()
            if code == 'mydeal' or name == 'mydeal':
                md = (s.settings or {}).get('mydeal') or {}
                mydeal_ok = bool(md.get('price_template_upload_id') and md.get('inventory_template_upload_id'))
        except Exception:
            mydeal_ok = False

        data.append({
            "storeId": s.id,
            "storeName": s.name,
            "marketplace": {"id": s.marketplace.id, "code": s.marketplace.code, "name": s.marketplace.name},
            "isActive": s.is_active,
            "scrapingEnabled": s.scraping_enabled,
            "priceUpdateEnabled": s.price_update_enabled,
            "lastScrapeAt": store_to_last.get(s.id),
            "lastExportPriceAt": store_to_last_price.get(s.id),
            "lastExportInventoryAt": store_to_last_inventory.get(s.id),
            "products": counts.get('products', 0),
            "vendors": counts.get('vendors', 0),
            "myDealTemplatesOk": mydeal_ok,
        })
    return data


@router.get("/vendors")
def dashboard_vendors(request, marketplace_id: int | None = None, store_id: int | None = None):
    products_qs = _filter_products(marketplace_id, store_id, None)

    # Aggregate product counts per vendor
    prod_counts = (products_qs
                   .values('vendor_id')
                   .annotate(products=Count('id'),
                             avgFinalPrice=Avg('marketplace_final_price'),
                             outOfStock=Count('id', filter=Q(marketplace_final_inventory__lte=0))) )
    vendor_ids = [x['vendor_id'] for x in prod_counts]
    vendors = {v.id: v for v in Vendor.objects.filter(id__in=vendor_ids)}

    # Recent updates/errors per vendor
    now = timezone.now()
    price_updates = (VendorPrice.objects
                     .filter(product__in=products_qs, scraped_at__gte=now - timedelta(hours=24))
                     .values('product__vendor_id')
                     .annotate(updated=Count('id')))
    vendor_to_updates = {x['product__vendor_id']: x['updated'] for x in price_updates}

    errors = (VendorPrice.objects
              .filter(product__in=products_qs, scraped_at__gte=now - timedelta(hours=24))
              .exclude(Q(error_code__isnull=True) | Q(error_code__exact=''))
              .values('product__vendor_id')
              .annotate(errs=Count('id')))
    vendor_to_errors = {x['product__vendor_id']: x['errs'] for x in errors}

    rows = []
    for row in prod_counts:
        vid = row['vendor_id']
        v = vendors.get(vid)
        rows.append({
            "vendorId": vid,
            "vendorName": v.name if v else f"Vendor {vid}",
            "products": row.get('products', 0),
            "outOfStock": row.get('outOfStock', 0),
            "avgFinalPrice": row.get('avgFinalPrice') or 0,
            "priceUpdated24h": vendor_to_updates.get(vid, 0),
            "recentErrors24h": vendor_to_errors.get(vid, 0),
        })
    return rows 