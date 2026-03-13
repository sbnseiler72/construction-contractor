# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionInvoice(models.Model):
    """
    Thin wrapper around account.move (vendor bill) for construction projects.
    - Hides line complexity from the project-facing UI
    - Tracks partial payments natively through account.move reconciliation
    - Supports invoice amendments via Odoo native reset-to-draft workflow
    """
    _name = 'construction.invoice'
    _description = 'Construction Project Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'invoice_date desc, id desc'

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
    invoice_date = fields.Date(
        string='Invoice Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor / Contractor',
        required=True,
        tracking=True,
    )
    invoice_number = fields.Char(
        string='Invoice Number',
        tracking=True,
        help='Vendor invoice number / reference',
    )
    description = fields.Text(
        string='Description / Scope',
        help='Description of work or services covered by this invoice',
    )
    amount_total = fields.Monetary(
        string='Invoice Total',
        required=True,
        currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='project_id.currency_id',
        store=True,
    )

    # Receipt/attachment for the original invoice document
    receipt_ref = fields.Char(
        string='Receipt Reference',
        tracking=True,
    )
    receipt_file = fields.Binary(
        string='Invoice Document',
        attachment=True,
    )
    receipt_filename = fields.Char(string='Invoice Filename')

    project_phase_id = fields.Many2one(
        'construction.project.phase',
        string='Project Phase',
        tracking=True,
    )

    notes = fields.Text(string='Notes / Remarks')

    # Payment source — set when payment is registered via the payment wizard
    payment_source = fields.Selection([
        ('payroll_card', 'Payroll Card'),
        ('employer_cash', 'Employer Account - Cash'),
        ('employer_check', 'Employer Account - Check'),
    ], string='Payment Source', tracking=True,
        help='Account from which this invoice was (or will be) paid')

    # Link to native Odoo vendor bill
    account_move_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )

    # Payment status computed from native bill
    payment_state = fields.Selection(
        related='account_move_id.payment_state',
        string='Payment Status',
        store=True,
    )
    amount_paid = fields.Monetary(
        string='Amount Paid',
        compute='_compute_payment_amounts',
        currency_field='currency_id',
        store=False,
    )
    amount_residual = fields.Monetary(
        string='Outstanding Balance',
        compute='_compute_payment_amounts',
        currency_field='currency_id',
        store=False,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Recorded'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', tracking=True)

    company_id = fields.Many2one(
        'res.company',
        related='project_id.company_id',
        store=True,
    )

    # -------------------------------------------------------------------------
    # Computed
    # -------------------------------------------------------------------------
    @api.depends('account_move_id', 'account_move_id.amount_residual', 'amount_total')
    def _compute_payment_amounts(self):
        for rec in self:
            if rec.account_move_id:
                rec.amount_residual = rec.account_move_id.amount_residual
                rec.amount_paid = rec.amount_total - rec.account_move_id.amount_residual
            else:
                rec.amount_residual = rec.amount_total
                rec.amount_paid = 0.0

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.invoice') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('amount_total')
    def _check_amount(self):
        for rec in self:
            if rec.amount_total <= 0:
                raise ValidationError(_('Invoice total must be greater than zero.'))

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_create_vendor_bill(self):
        """
        Create the corresponding native vendor bill (account.move).
        Uses a single 'catch-all' line mapped to a general expense account.
        Invoice lines can be expanded in a future phase.
        """
        self.ensure_one()
        if self.account_move_id:
            raise ValidationError(_('A vendor bill already exists for this invoice.'))

        # Resolve expense account: use partner's default purchase account,
        # then fall back to any expense-type account in the company.
        account = self.partner_id.property_account_payable_id
        # Try to get a proper expense/cost account from account.account
        expense_account = self.env['account.account'].search([
            ('account_type', 'in', ['expense', 'expense_direct_cost', 'expense_depreciation']),
            ('company_ids', 'in', self.company_id.id),
        ], limit=1)
        if not expense_account:
            expense_account = self.env['account.account'].search([
                ('account_type', 'not in', [
                    'equity', 'equity_unaffected', 'off_balance',
                    'asset_receivable', 'liability_payable',
                    'asset_cash', 'liability_current', 'liability_non_current',
                ]),
                ('company_ids', 'in', self.company_id.id),
            ], limit=1)
        if not expense_account:
            raise ValidationError(
                _('No expense account found. Please configure a chart of accounts.')
            )

        move_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.invoice_date,
            'ref': self.invoice_number or self.name,
            'narration': self.description,
            'company_id': self.company_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': self.description or _('Construction services - %s') % self.name,
                'quantity': 1.0,
                'price_unit': self.amount_total,
                'account_id': expense_account.id,
            })],
        }
        move = self.env['account.move'].create(move_vals)
        self.account_move_id = move
        self.state = 'posted'
        return True

    def action_open_vendor_bill(self):
        self.ensure_one()
        if not self.account_move_id:
            return self.action_create_vendor_bill()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
        }

    def action_register_payment(self):
        """Open the construction payment wizard to select payment source and journal."""
        self.ensure_one()
        if not self.account_move_id:
            raise ValidationError(_('Please create the vendor bill first.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'construction.invoice.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
            },
        }

    def action_cancel(self):
        for rec in self:
            if rec.account_move_id and rec.account_move_id.state == 'posted':
                raise ValidationError(
                    _('Cannot cancel: the linked vendor bill is already posted. '
                      'Please cancel or reset it in accounting first.')
                )
            rec.state = 'cancelled'

    def action_reset_draft(self):
        self.write({'state': 'draft'})
