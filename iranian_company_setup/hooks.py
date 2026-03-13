# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Decimal accuracy records to update for zero-decimal IRR environment
DECIMAL_ACCURACY_NAMES = [
    'Account',
    'Product Price',
    'Payment Terms',
    'Discount',
]

# Currency name to deactivate (Odoo internal default)
CURRENCY_TO_DEACTIVATE = 'EUR'

# Target currency
IRR_CURRENCY_NAME = 'IRR'
IRR_ROUNDING = 1.0
IRR_DECIMAL_PLACES = 0
IRR_SYMBOL = '\uFDFC'  # Unicode for Iranian Rial sign (﷼)


def post_init_hook(env):
    """
    Post-install hook executed once after this module is installed.

    Actions performed:
      1. Activate IRR currency if inactive.
      2. Set IRR rounding and decimal places via raw SQL (bypasses ORM constraint).
      3. Set IRR as the default currency for company with id=1.
      4. Update Decimal Accuracy records to 0 digits for IRR compatibility.
      5. Deactivate EUR to keep a clean single-currency environment.

    IMPORTANT: This hook is safe ONLY on a fresh database with no existing
    accounting entries. Do NOT install on a production DB that already has
    journal entries or invoices posted.
    """
    _logger.info("=== Iranian Company Setup: Starting post_init_hook ===")

    # ------------------------------------------------------------------
    # Step 1: Find IRR — search including inactive records
    # ------------------------------------------------------------------
    irr = env['res.currency'].with_context(active_test=False).search(
        [('name', '=', IRR_CURRENCY_NAME)], limit=1
    )

    if not irr:
        _logger.error(
            "IRR currency not found in res.currency. "
            "Make sure the 'account' or 'base' module data is loaded. Aborting."
        )
        return

    _logger.info("Found IRR currency: id=%s, active=%s", irr.id, irr.active)

    # ------------------------------------------------------------------
    # Step 2: Update IRR via raw SQL to bypass the ORM decimal constraint
    # This is the only safe way to set decimal_places on a fresh DB before
    # Odoo's constraint check fires ("cannot reduce decimal places if used
    # in accounting entries").
    # ------------------------------------------------------------------
    env.cr.execute("""
        UPDATE res_currency
        SET
            active          = true,
            rounding        = %s,
            decimal_places  = %s,
            symbol          = %s
        WHERE name = %s
    """, (IRR_ROUNDING, IRR_DECIMAL_PLACES, IRR_SYMBOL, IRR_CURRENCY_NAME))

    _logger.info(
        "IRR updated: rounding=%s, decimal_places=%s, symbol=%s",
        IRR_ROUNDING, IRR_DECIMAL_PLACES, IRR_SYMBOL
    )

    # ------------------------------------------------------------------
    # Step 3: Set IRR as the default currency for company id=1
    # Use raw SQL for consistency and to avoid any currency mismatch
    # triggers during initialization.
    # ------------------------------------------------------------------
    env.cr.execute("""
        UPDATE res_company
        SET currency_id = %s
        WHERE id = 1
    """, (irr.id,))

    _logger.info("Company id=1 default currency set to IRR (id=%s)", irr.id)

    # ------------------------------------------------------------------
    # Step 4: Update Decimal Accuracy table
    # This controls how many decimal digits are displayed and validated
    # across the entire application for monetary fields.
    # ------------------------------------------------------------------
    for da_name in DECIMAL_ACCURACY_NAMES:
        env.cr.execute("""
            UPDATE decimal_precision
            SET digits = 0
            WHERE name = %s
        """, (da_name,))
        affected = env.cr.rowcount
        if affected:
            _logger.info("decimal_precision '%s' set to 0 digits.", da_name)
        else:
            _logger.warning(
                "decimal_precision '%s' not found. "
                "It may not exist until Accounting is configured.",
                da_name
            )

    # ------------------------------------------------------------------
    # Step 5: Deactivate EUR (Odoo internal base currency)
    # In a single-currency IRR environment, having EUR active causes
    # confusion in reports and journal entries.
    # Skip if EUR == IRR (safety check).
    # ------------------------------------------------------------------
    eur = env['res.currency'].with_context(active_test=False).search(
        [('name', '=', CURRENCY_TO_DEACTIVATE)], limit=1
    )

    if eur and eur.id != irr.id:
        env.cr.execute("""
            UPDATE res_currency
            SET active = false
            WHERE name = %s
        """, (CURRENCY_TO_DEACTIVATE,))
        _logger.info("EUR deactivated to keep single-currency IRR environment.")
    else:
        _logger.info("EUR not found or same as IRR — skipping deactivation.")

    # ------------------------------------------------------------------
    # Invalidate ORM cache so subsequent reads reflect the DB changes
    # ------------------------------------------------------------------
    env.invalidate_all()

    _logger.info("=== Iranian Company Setup: post_init_hook completed successfully ===")
