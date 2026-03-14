# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionContractorFeePayment(models.Model):
    _name = 'construction.contractor.fee.payment'
    _description = 'Contractor Fee Payment'
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
        string='Payment Date',
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
    description = fields.Char(string='Description')

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain=[('type', 'in', ['cash', 'bank'])],
        tracking=True,
        help='Journal used to record this contractor fee payment',
    )

    # Receipt
    receipt_ref = fields.Char(
        string='Receipt Reference',
        tracking=True,
        help='Receipt or voucher number for this payment',
    )
    receipt_file = fields.Binary(
        string='Receipt Attachment',
        attachment=True,
    )
    receipt_filename = fields.Char(string='Receipt Filename')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', tracking=True, required=True)

    currency_id = fields.Many2one(
        'res.currency',
        related='project_id.currency_id',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='project_id.company_id',
        store=True,
    )

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.contractor.fee.payment') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------
    @api.onchange('project_id')
    def _onchange_project_id_journal(self):
        if self.project_id and self.project_id.contractor_fee_journal_id:
            self.journal_id = self.project_id.contractor_fee_journal_id

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero.'))

    # -------------------------------------------------------------------------
    # State transitions
    # -------------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if not rec.receipt_ref and not rec.receipt_file:
                raise ValidationError(
                    _('A receipt reference or file attachment is required before confirming a fee payment.')
                )
            rec.state = 'confirmed'

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
