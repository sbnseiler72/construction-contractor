# -*- coding: utf-8 -*-
{
    'name': 'Construction Contractor Management',
    'version': '19.0.1.0.0',
    'category': 'Construction',
    'summary': 'Manage construction contractor projects, payroll cards, expenses, and invoices',
    'description': """
        Construction Contractor Project Management
        ==========================================
        - Project management with dedicated payroll card (cash journal)
        - Expense tracking: labor, materials, equipment, subcontractors, transport
        - Payment source tracking: payroll card or employer accounts (cash/check)
        - Simplified invoice management using native vendor bills with partial payments
        - Receipt management: file upload + reference number
        - Comprehensive reporting: financial summary, card ledger, expense list, invoice status
    """,
    'author': 'Custom Development',
    'depends': [
        'base',
        'account',
        'project',
        'contacts',
        'jalali_datepicker',
    ],
    'data': [
        'security/construction_security.xml',
        'security/ir.model.access.csv',
        'data/construction_data.xml',
        'views/construction_project_views.xml',
        'views/construction_expense_views.xml',
        'views/construction_card_transaction_views.xml',
        'views/construction_invoice_payment_views.xml',
        'views/construction_invoice_views.xml',
        'report/construction_report_templates.xml',
        'report/construction_reports.xml',
        'views/construction_menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
