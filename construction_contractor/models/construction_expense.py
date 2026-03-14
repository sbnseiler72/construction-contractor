# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionExpense(models.Model):
    _name = 'construction.expense'
    _description = 'Construction Project Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    project_id = fields.Many2one(
        'construction.project',
        string='Project',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    date = fields.Date(
        string='Expense Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    expense_type_id = fields.Many2one(
        'construction.expense.type',
        string='Expense Type',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    description = fields.Char(string='Description', required=True)
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='project_id.currency_id',
        store=True,
    )

    # Payment source
    payment_source = fields.Selection([
        ('payroll_card', 'Payroll Card'),
        ('employer_cash', 'Employer Account - Cash'),
        ('employer_check', 'Employer Account - Check'),
    ], string='Payment Source', required=True, default='payroll_card', tracking=True)

    # Vendor / payee
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor / Payee',
        tracking=True,
    )

    # Receipt fields
    receipt_ref = fields.Char(
        string='Receipt Reference',
        tracking=True,
        help='Receipt, invoice, or voucher number',
    )
    receipt_file = fields.Binary(
        string='Receipt Attachment',
        attachment=True,
    )
    receipt_filename = fields.Char(string='Receipt Filename')

    project_phase_id = fields.Many2one(
        'construction.project.phase',
        string='Project Phase',
        tracking=True,
    )

    # Who recorded/paid this expense
    recorded_by = fields.Many2one(
        'res.users',
        string='Recorded By',
        default=lambda self: self.env.user,
        tracking=True,
    )
    notes = fields.Text(string='Notes')

    include_in_contractor_fee = fields.Boolean(
        string='Include in Contractor Fee',
        default=True,
        tracking=True,
        help='Uncheck to exclude this expense from the contractor percentage calculation.',
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', tracking=True, required=True)

    company_id = fields.Many2one(
        'res.company',
        related='project_id.company_id',
        store=True,
    )

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.onchange('expense_type_id')
    def _onchange_expense_type_contractor_fee(self):
        if self.expense_type_id:
            self.include_in_contractor_fee = self.expense_type_id.include_in_contractor_fee

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.expense') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Expense amount must be greater than zero.'))

    @api.constrains('payment_source', 'project_id')
    def _check_payroll_card_journal(self):
        for rec in self:
            if rec.payment_source == 'payroll_card' and not rec.project_id.payroll_journal_id:
                raise ValidationError(
                    _('The project "%s" does not have a payroll card journal configured. '
                      'Please create the payroll card journal first.')
                    % rec.project_id.name
                )

    # -------------------------------------------------------------------------
    # State transitions
    # -------------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if not rec.receipt_ref and not rec.receipt_file:
                raise ValidationError(
                    _('A receipt reference or file attachment is required before confirming an expense.')
                )
            rec.state = 'confirmed'

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
