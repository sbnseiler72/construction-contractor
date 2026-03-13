# Iranian Company Setup — Odoo 19

## Purpose

This module initializes an Odoo 19 database for Iranian companies by:

- Activating **IRR (Iranian Rial)** as the default company currency
- Setting rounding factor to `1.0` (zero decimal places)
- Updating **Decimal Accuracy** for Account, Product Price, Payment Terms, Discount to `0`
- Deactivating EUR to avoid confusion in single-currency environments

## Installation

### Requirements

- Odoo 19.0
- `base` and `account` modules must be installed first
- **Fresh database only** — do NOT install on a DB that already has accounting entries

### Steps

1. Copy `iranian_company_setup/` folder into your Odoo addons path
2. Restart the Odoo service
3. Go to **Apps** → Update Apps List
4. Search for **"Iranian Company Setup"** and click **Install**

The `post_init_hook` runs automatically on install.

## Why Raw SQL?

Odoo's ORM enforces a constraint:

> *"You cannot reduce the number of decimal places of a currency which has already been used to make accounting entries."*

This constraint fires even on a fresh DB if you use the ORM `.write()` method.
Using `env.cr.execute()` bypasses the ORM constraint safely **on an empty database**,
which is the only supported use case for this module.

## Warning

Do **NOT** install this module on a production database that already has:
- Posted journal entries
- Confirmed invoices or bills
- Validated stock moves with monetary values

## Structure

```
iranian_company_setup/
├── __init__.py          # Imports post_init_hook
├── __manifest__.py      # Module metadata and hook declaration
├── hooks.py             # Core initialization logic
└── README.md
```

## Compatibility

| Odoo Version | Compatible |
|---|---|
| 19.0 | Yes |
| 17.0 / 18.0 | Likely (untested) |
| 16.0 and below | Not guaranteed |
