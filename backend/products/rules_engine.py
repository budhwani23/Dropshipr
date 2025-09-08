from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache

from marketplace.models import StorePriceSettings, StoreInventorySettings, PriceRange


class StoreVendorRules:
    """
    Shared store+vendor pricing and inventory rules.

    Spreadsheet-equivalent pricing:
      - base = vendor_price * (1 + tax)
      - select tier by base (vendor + tax)
      - preliminary = base / (1 - (fee + margin))
      - enforce minimum absolute profit after fees by grossing up shortfall
      - round to 2dp (ROUND_HALF_UP)

    Inventory:
      - select multiplier tier by vendor quantity
      - final = floor(vendor_qty * multiplier)  (fallback to vendor_qty if no tier)
    """

    @staticmethod
    def quantize2(value: Decimal) -> Decimal:
        """Round a Decimal to 2dp using ROUND_HALF_UP."""
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _to_decimal(value) -> Decimal:
        """Coerce any numeric/text to Decimal safely."""
        return Decimal(str(value))

    @staticmethod
    def _match_range(value: Decimal, pr: PriceRange) -> bool:
        """
        Check if a value falls into a PriceRange with inclusive bounds.
        Uses: from_value <= value <= to_value; 'MAX' means no upper bound.
        """
        lo = StoreVendorRules._to_decimal(pr.from_value)
        hi = pr.to_value
        if str(hi) == "MAX":
            return value >= lo
        hi_dec = StoreVendorRules._to_decimal(hi)
        return lo <= value <= hi_dec

    @staticmethod
    @lru_cache(maxsize=4096)
    def _load_price_settings(store_id: int, vendor_id: int) -> StorePriceSettings:
        """
        Load StorePriceSettings and prefetch price ranges.
        Cached by (store_id, vendor_id) for batch performance.
        """
        return (
            StorePriceSettings.objects
            .select_related('store', 'vendor')
            .prefetch_related('price_ranges__price_range')
            .get(store_id=store_id, vendor_id=vendor_id)
        )

    @staticmethod
    @lru_cache(maxsize=4096)
    def _load_inventory_settings(store_id: int, vendor_id: int) -> StoreInventorySettings:
        """
        Load StoreInventorySettings and prefetch inventory ranges.
        Cached by (store_id, vendor_id) for batch performance.
        """
        return (
            StoreInventorySettings.objects
            .select_related('store', 'vendor')
            .prefetch_related('inventory_ranges__price_range')
            .get(store_id=store_id, vendor_id=vendor_id)
        )

    @staticmethod
    def _select_price_tier(sps: StorePriceSettings, base: Decimal):
        """
        Select the first price tier that matches the given base (vendor + tax).
        Sort by (from_value, to_value) to ensure deterministic selection.
        """
        tiers = sorted(
            sps.price_ranges.all(),
            key=lambda x: (
                StoreVendorRules._to_decimal(x.price_range.from_value),
                str(x.price_range.to_value),
            ),
        )
        for t in tiers:
            if StoreVendorRules._match_range(base, t.price_range):
                return t
        return None

    @staticmethod
    def _select_inventory_tier(sis: StoreInventorySettings, qty: Decimal):
        """Select the first inventory tier that matches the vendor quantity."""
        tiers = sorted(
            sis.inventory_ranges.all(),
            key=lambda x: (
                StoreVendorRules._to_decimal(x.price_range.from_value),
                str(x.price_range.to_value),
            ),
        )
        for t in tiers:
            if StoreVendorRules._match_range(qty, t.price_range):
                return t
        return None

    @classmethod
    def apply_price_rules(cls, product, vendor_price: Decimal) -> Decimal:
        """
        Compute marketplace price per agreed logic.

        Steps:
          1) base = vendor_price * (1 + tax)
          2) tier by base -> margin%, min_margin
          3) preliminary = base / (1 - (margin + fee))
          4) net_after_fees = preliminary * (1 - fee)
             profit = net_after_fees - base
             if profit < min_margin:
                 shortfall = min_margin - profit
                 preliminary += shortfall / (1 - fee)
          5) round to 2dp (ROUND_HALF_UP)
        """
        sps = cls._load_price_settings(product.store_id, product.vendor_id)
        tax = cls._to_decimal(sps.purchase_tax_percentage) / Decimal(100)
        fee = cls._to_decimal(sps.marketplace_fees_percentage) / Decimal(100)

        base = cls._to_decimal(vendor_price) * (Decimal(1) + tax)
        if base <= 0:
            return cls.quantize2(Decimal(0))

        tier = cls._select_price_tier(sps, base)
        if not tier:
            # No tier configured: gross-up only for fees (no margin requirement).
            return cls.quantize2(base / (Decimal(1) - fee))

        margin = cls._to_decimal(tier.margin_percentage) / Decimal(100)
        min_margin = cls._to_decimal(tier.minimum_margin_cents) / Decimal(100)

        if fee < 0 or margin < 0 or (fee + margin) >= 1:
            raise ValueError("Invalid fee/margin configuration: fee+margin must be < 100% and non-negative.")

        # Gross-up for combined (margin + fee)
        preliminary = base / (Decimal(1) - (fee + margin))

        # Enforce minimum absolute profit AFTER fees by grossing up shortfall
        net_after_fees = preliminary * (Decimal(1) - fee)
        profit = net_after_fees - base
        if profit < min_margin:
            shortfall = min_margin - profit
            preliminary += shortfall / (Decimal(1) - fee)

        return cls.quantize2(preliminary)

    @classmethod
    def apply_inventory_rules(cls, product, vendor_qty: int) -> int:
        """
        Compute marketplace inventory by applying the matching multiplier range.
        Fallback: if no tier is found, return vendor_qty unchanged.
        """
        sis = cls._load_inventory_settings(product.store_id, product.vendor_id)
        from math import floor
        qty_dec = cls._to_decimal(max(0, int(vendor_qty)))
        tier = cls._select_inventory_tier(sis, qty_dec)
        if not tier:
            return int(qty_dec)
        return int(max(0, floor(qty_dec * cls._to_decimal(tier.multiplier)))) 