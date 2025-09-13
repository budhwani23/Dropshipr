import csv
import hashlib
import os
from datetime import datetime
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from marketplace.models import Store
from products.models import Product
from .models import ExportArtifact


EXPORTS_DIR = os.path.join("exports")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_csv(file_path: str, headers: list[str], rows: list[list[str]]) -> int:
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(r)
    return os.path.getsize(file_path)


def _sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_file_name(kind: str, store_id: int) -> tuple[str, str]:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.join(EXPORTS_DIR, f"store_{store_id}", kind)
    _ensure_dir(base_dir)
    filename = f"mydeal_{kind}_{store_id}_{ts}.csv"
    return base_dir, os.path.join(base_dir, filename)


def _collect_rows_for_store(store: Store, kind: str) -> tuple[list[str], list[list[str]]]:
    products = Product.objects.filter(store=store)

    if kind == ExportArtifact.KIND_PRICE:
        headers = [
            "DealID",
            "VariantID",
            "ExternalID",
            "SKU",
            "Options",
            "DealTitle",
            "Price(IncGST)",
            "RRP(IncGST)",
        ]
        rows: list[list[str]] = []
        for p in products:
            rows.append([
                p.marketplace_external_id or "",
                p.variation_id or "",
                p.marketplace_external_id or "",
                p.marketplace_child_sku,
                "",
                "",
                f"{p.marketplace_final_price or Decimal('0')}",
                f"{p.marketplace_final_price or Decimal('0')}",
            ])
        return headers, rows

    # inventory
    headers = [
        "DealID",
        "VariantID",
        "ExternalID",
        "SKU",
        "Options",
        "DealTitle",
        "StockOnHand",
        "Discontinued",
        "MyDealApproved",
    ]
    rows = []
    for p in products:
        inv = p.marketplace_final_inventory if p.marketplace_final_inventory is not None else 0
        rows.append([
            p.marketplace_external_id or "",
            p.variation_id or "",
            p.marketplace_external_id or "",
            p.marketplace_child_sku,
            "",
            "",
            str(max(0, int(inv))),
            "0",
            "1",
        ])
    return headers, rows


@transaction.atomic
def generate_mydeal_export(store_id: int, kind: str) -> ExportArtifact:
    store = Store.objects.select_related('marketplace').get(id=store_id)
    if str(getattr(store.marketplace, 'code', '')).lower() != 'mydeal' and str(getattr(store.marketplace, 'name', '')).lower() != 'mydeal':
        raise ValueError("Store is not a MyDeal marketplace")

    artifact = ExportArtifact.objects.create(
        store=store,
        marketplace_code=store.marketplace.code,
        kind=kind,
        status=ExportArtifact.STATUS_GENERATING,
        generated_at=timezone.now(),
    )

    base_dir, file_path = _build_file_name(kind, store.id)
    headers, rows = _collect_rows_for_store(store, kind)
    size = _write_csv(file_path, headers, rows)
    checksum = _sha256(file_path)

    artifact.file_path = file_path
    artifact.file_name = os.path.basename(file_path)
    artifact.size_bytes = size
    artifact.checksum = checksum
    artifact.status = ExportArtifact.STATUS_READY
    artifact.save(update_fields=['file_path','file_name','size_bytes','checksum','status'])
    return artifact 