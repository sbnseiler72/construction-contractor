# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionCardTransaction(models.Model):
    _name = 'construction.card.transaction'
    _description = 'Payroll Card Transaction'
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
    transaction_type = fields.Selection([
        ('deposit', 'Deposit to Card'),
        ('withdrawal', 'Cash Withdrawal / Expense'),
    ], string='Type', required=True, default='deposit', tracking=True)

    date = fields.Date(
        string='Transaction Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
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
    description = fields.Char(string='Description', required=True)

    # Receipt fields — both file upload and reference number required
    receipt_ref = fields.Char(
        string='Receipt Reference',
        tracking=True,
        help='Receipt or voucher number',
    )
    receipt_file = fields.Binary(
        string='Receipt Attachment',
        attachment=True,
    )
    receipt_filename = fields.Char(string='Receipt Filename')

    # Who performed this transaction
    performed_by = fields.Many2one(
        'res.users',
        string='Performed By',
        default=lambda self: self.env.user,
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', tracking=True)

    # Link to Odoo accounting journal entry (auto-created on confirm)
    account_move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        related='project_id.company_id',
        store=True,
    )

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.card.transaction') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Transaction amount must be greater than zero.'))

    # -------------------------------------------------------------------------
    # State transitions
    # -------------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if not rec.receipt_ref and not rec.receipt_file:
                raise ValidationError(
                    _('A receipt reference or file attachment is required before confirming a card transaction.')
                )
            rec.state = 'confirmed'

    def action_cancel(self):
        for rec in self:
            if rec.account_move_id:
                rec.account_move_id.button_cancel()
            rec.state = 'cancelled'

    def action_reset_draft(self):
        self.write({'state': 'draft'})
