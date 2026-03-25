# -*- coding: utf-8 -*-
from odoo import models, fields, tools, _


class ConstructionFinancialBalance(models.Model):
    _name = 'construction.financial.balance'
    _description = 'Financial Balance'
    _auto = False
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    project_id = fields.Many2one(
        'construction.project',
        string='Project',
        readonly=True,
    )
    transaction_type = fields.Selection([
        ('expense', 'Expense'),
        ('invoice_payment', 'Invoice Payment'),
    ], string='Transaction Type', readonly=True)
    expense_type_id = fields.Many2one(
        'construction.expense.type',
        string='Expense Type',
        readonly=True,
    )
    description = fields.Char(string='Description', readonly=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor / Payee',
        readonly=True,
    )
    payment_source = fields.Selection([
        ('payroll_card', 'Payroll Card'),
        ('employer_cash', 'Employer Cash'),
        ('employer_check', 'Employer Check'),
    ], string='Payment Source', readonly=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
    )
    receipt_ref = fields.Char(string='Receipt Ref', readonly=True)
    project_phase_id = fields.Many2one(
        'construction.project.phase',
        string='Project Phase',
        readonly=True,
    )
    source_model = fields.Char(string='Source Model', readonly=True)
    source_id = fields.Integer(string='Source ID', readonly=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                -- Confirmed Expenses
                SELECT
                    e.id AS id,
                    e.name AS name,
                    e.date AS date,
                    e.project_id AS project_id,
                    'expense' AS transaction_type,
                    e.expense_type_id AS expense_type_id,
                    e.description AS description,
                    e.partner_id AS partner_id,
                    e.payment_source AS payment_source,
                    e.amount AS amount,
                    e.currency_id AS currency_id,
                    e.receipt_ref AS receipt_ref,
                    e.project_phase_id AS project_phase_id,
                    'construction.expense' AS source_model,
                    e.id AS source_id,
                    e.company_id AS company_id
                FROM construction_expense e
                WHERE e.state = 'confirmed'

                UNION ALL

                -- Posted invoices with payments
                SELECT
                    1000000 + i.id AS id,
                    i.name AS name,
                    i.invoice_date AS date,
                    i.project_id AS project_id,
                    'invoice_payment' AS transaction_type,
                    NULL AS expense_type_id,
                    COALESCE(i.description, i.invoice_number) AS description,
                    i.partner_id AS partner_id,
                    i.payment_source AS payment_source,
                    (i.amount_total - COALESCE(am.amount_residual, i.amount_total)) AS amount,
                    i.currency_id AS currency_id,
                    i.receipt_ref AS receipt_ref,
                    i.project_phase_id AS project_phase_id,
                    'construction.invoice' AS source_model,
                    i.id AS source_id,
                    i.company_id AS company_id
                FROM construction_invoice i
                LEFT JOIN account_move am ON am.id = i.account_move_id
                WHERE i.state = 'posted'
                  AND (i.amount_total - COALESCE(am.amount_residual, i.amount_total)) > 0
            )
        """ % self._table)

    def action_open_source_record(self):
        """Open the original expense or invoice record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.source_model,
            'res_id': self.source_id,
            'view_mode': 'form',
            'target': 'current',
        }
