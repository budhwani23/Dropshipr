import os
from typing import List, Tuple
from django.utils.translation import gettext as _

from products.utils import read_upload_file


PRICE_HEADERS: List[str] = [
    "DealID",
    "VariantID",
    "ExternalID",
    "SKU",
    "Options",
    "DealTitle",
    "Price(IncGST)",
    "RRP(IncGST)",
]

INVENTORY_HEADERS: List[str] = [
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


def _validate_headers(file_path: str, required_headers: List[str]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate that the first row headers of the file exactly contain the required headers
    in any order (case-sensitive match by spec). Returns tuple(valid, missing, extra).
    """
    if not os.path.exists(file_path):
        return False, required_headers[:], ["<file not found>"]

    df = read_upload_file(file_path)
    actual_headers = list(df.columns)

    missing = [h for h in required_headers if h not in actual_headers]
    extra = [h for h in actual_headers if h not in required_headers]
    is_valid = len(missing) == 0 and len(extra) == 0
    return is_valid, missing, extra


def validate_price_template(file_path: str) -> Tuple[bool, str]:
    valid, missing, extra = _validate_headers(file_path, PRICE_HEADERS)
    if valid:
        return True, ""
    message_parts: List[str] = []
    if missing:
        message_parts.append(_(f"Missing headers: {', '.join(missing)}"))
    if extra:
        message_parts.append(_(f"Unexpected headers: {', '.join(extra)}"))
    return False, "; ".join(message_parts)


def validate_inventory_template(file_path: str) -> Tuple[bool, str]:
    valid, missing, extra = _validate_headers(file_path, INVENTORY_HEADERS)
    if valid:
        return True, ""
    message_parts: List[str] = []
    if missing:
        message_parts.append(_(f"Missing headers: {', '.join(missing)}"))
    if extra:
        message_parts.append(_(f"Unexpected headers: {', '.join(extra)}"))
    return False, "; ".join(message_parts) 