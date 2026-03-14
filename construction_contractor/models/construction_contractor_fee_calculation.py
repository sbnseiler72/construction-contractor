# -*- coding: utf-8 -*-
from odoo import models, fields, tools


class ConstructionContractorFeeCalculation(models.Model):
    _name = 'construction.contractor.fee.calculation'
    _description = 'Contractor Fee Calculation'
    _auto = False
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    project_id = fields.Many2one('construction.project', string='Project', readonly=True)
    transaction_type = fields.Selection([
        ('expense', 'Expense'),
        ('invoice_payment', 'Invoice Payment'),
    ], string='Type', readonly=True)
    expense_type_id = fields.Many2one(
        'construction.expense.type', string='Expense Type', readonly=True)
    description = fields.Char(string='Description', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Vendor / Payee', readonly=True)
    payment_source = fields.Selection([
        ('payroll_card', 'Payroll Card'),
        ('employer_cash', 'Employer Cash'),
        ('employer_check', 'Employer Check'),
    ], string='Payment Source', readonly=True)
    project_phase_id = fields.Many2one(
        'construction.project.phase', string='Project Phase', readonly=True)
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id', readonly=True)
    contractor_percentage = fields.Float(
        string='Contractor %', digits=(5, 2), readonly=True)
    fee_amount = fields.Monetary(
        string='Fee Amount', currency_field='currency_id', readonly=True,
        help='Amount × Contractor Percentage')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    source_model = fields.Char(string='Source Model', readonly=True)
    source_id = fields.Integer(string='Source ID', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                -- Eligible confirmed expenses
                SELECT
                    e.id                                            AS id,
                    e.name                                          AS name,
                    e.date                                          AS date,
                    e.project_id                                    AS project_id,
                    'expense'                                       AS transaction_type,
                    e.expense_type_id                               AS expense_type_id,
                    e.description                                   AS description,
                    e.partner_id                                    AS partner_id,
                    e.payment_source                                AS payment_source,
                    e.project_phase_id                              AS project_phase_id,
                    e.amount                                        AS amount,
                    p.contractor_percentage                         AS contractor_percentage,
                    e.amount * p.contractor_percentage / 100.0      AS fee_amount,
                    e.currency_id                                   AS currency_id,
                    e.company_id                                    AS company_id,
                    'construction.expense'                          AS source_model,
                    e.id                                            AS source_id
                FROM construction_expense e
                JOIN construction_project p ON p.id = e.project_id
                WHERE e.state = 'confirmed'
                  AND e.include_in_contractor_fee = TRUE

                UNION ALL

                -- Eligible posted invoice payments
                SELECT
                    2000000 + i.id                                                              AS id,
                    i.name                                                                      AS name,
                    i.invoice_date                                                              AS date,
                    i.project_id                                                                AS project_id,
                    'invoice_payment'                                                           AS transaction_type,
                    NULL                                                                        AS expense_type_id,
                    COALESCE(i.description, i.invoice_number)                                   AS description,
                    i.partner_id                                                                AS partner_id,
                    i.payment_source                                                            AS payment_source,
                    i.project_phase_id                                                          AS project_phase_id,
                    (i.amount_total - COALESCE(am.amount_residual, i.amount_total))             AS amount,
                    p.contractor_percentage                                                     AS contractor_percentage,
                    (i.amount_total - COALESCE(am.amount_residual, i.amount_total))
                        * p.contractor_percentage / 100.0                                       AS fee_amount,
                    i.currency_id                                                               AS currency_id,
                    i.company_id                                                                AS company_id,
                    'construction.invoice'                                                      AS source_model,
                    i.id                                                                        AS source_id
                FROM construction_invoice i
                JOIN construction_project p ON p.id = i.project_id
                LEFT JOIN account_move am ON am.id = i.account_move_id
                WHERE i.state = 'posted'
                  AND i.include_in_contractor_fee = TRUE
                  AND (i.amount_total - COALESCE(am.amount_residual, i.amount_total)) > 0
            )
        """ % self._table)

    def action_open_source_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.source_model,
            'res_id': self.source_id,
            'view_mode': 'form',
            'target': 'current',
        }
