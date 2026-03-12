# -*- coding: utf-8 -*-
{
    'name': 'Jalali Date Picker',
    'version': '19.0.1.0.0',
    'summary': 'Jalali (Shamsi) date picker widget for Odoo 19 with full Persian/RTL support',
    'description': """
        Provides a custom OWL field widget that displays and accepts Jalali (Shamsi/Persian)
        dates while storing Gregorian dates in the database.
        Uses the JalaliDatePicker library by majidh1.
        
        Features:
        - Jalali calendar display with full RTL support
        - Transparent Gregorian <-> Jalali conversion
        - Min/max date constraints
        - Holiday highlighting (Nowruz)
        - Readonly and edit mode rendering
        - Compatible with all Odoo date field types
    """,
    'category': 'Tools',
    'author': 'Your Company',
    'website': 'https://your-company.com',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            # Vendor: JalaliDatePicker library (place dist files in static/src/vendor/)
            'jalali_datepicker/static/src/vendor/jalalidatepicker.min.css',
            'jalali_datepicker/static/src/vendor/jalalidatepicker.min.js',
            # Widget XML template must load before JS
            'jalali_datepicker/static/src/xml/jalali_date_field.xml',
            # Widget JS component
            'jalali_datepicker/static/src/js/jalali_date_field.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
