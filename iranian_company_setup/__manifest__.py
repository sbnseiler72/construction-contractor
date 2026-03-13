# -*- coding: utf-8 -*-
{
    'name': 'Iranian Company Setup (IRR Currency)',
    'version': '19.0.1.0.0',
    'summary': 'Sets IRR as default currency with correct rounding and decimal precision',
    'description': """
        Initializes the Odoo database for Iranian companies:
        - Activates IRR (Iranian Rial) as the default company currency
        - Sets rounding factor to 1.0 (no decimal places)
        - Updates Decimal Accuracy for Account, Product Price, Payment Terms
        - Deactivates EUR to avoid confusion in single-currency setup
    """,
    'author': 'Your Company',
    'category': 'Localization',
    'depends': ['base', 'account'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
