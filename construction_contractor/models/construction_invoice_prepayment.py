# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

PAYMENT_SOURCE_SELECTION = [
    ('payroll_card', 'Payroll Card'),
    ('employer_cash', 'Employer Account - Cash'),
    ('employer_check', 'Employer Account - Check'),
]


class ConstructionInvoicePayment(models.Model):
    """
    Unified payment line for a construction invoice.

    Covers two cases:
      - on_account: payment made before the vendor bill is created (draft invoice).
        The linked account.payment is auto-reconciled when the bill is generated.
      - final: payment made against the posted vendor bill.
        The linked account.payment is reconciled with the bill immediately on creation.

    Both types are created by their respective wizards and displayed together
    in the invoice form's Payments tab.
    """
    _name = 'construction.invoice.prepayment'
    _description = 'Construction Invoice Payment'
    _order = 'payment_date desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    invoice_id = fields.Many2one(
        'construction.invoice',
        string='Invoice',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    payment_type = fields.Selection([
        ('on_account', 'Pay on Account'),
        ('final', 'Final Payment'),
    ], string='Payment Type', required=True, default='on_account',
        readonly=True, tracking=True,
    )
    payment_date = fields.Date(
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
    currency_id = fields.Many2one(
        'res.currency',
        related='invoice_id.currency_id',
        store=True,
    )
    payment_source = fields.Selection(
        PAYMENT_SOURCE_SELECTION,
        string='Payment Source',
        required=True,
        tracking=True,
    )
    memo = fields.Char(string='Memo / Reference')
    account_payment_id = fields.Many2one(
        'account.payment',
        string='Accounting Payment',
        readonly=True,
        copy=False,
        ondelete='restrict',
    )
    state = fields.Selection(
        related='account_payment_id.state',
        string='Payment State',
        store=True,
    )
    receipt_file = fields.Image(
        string='Receipt',
        attachment=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='invoice_id.company_id',
        store=True,
    )

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('construction.invoice.prepayment')
                    or _('New')
                )
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('amount', 'invoice_id', 'payment_type')
    def _check_amount_does_not_exceed_invoice(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Payment amount must be greater than zero.'))
            # Cap check only applies to on-account payments on invoices with a known total
            if rec.payment_type != 'on_account' or not rec.invoice_id.amount_total:
                continue
            other_active = rec.invoice_id.prepayment_ids.filtered(
                lambda p: p.id != rec.id
                and p.payment_type == 'on_account'
                and p.account_payment_id
                and p.account_payment_id.state in ('in_process', 'paid')
            )
            total = sum(other_active.mapped('amount')) + rec.amount
            if total > rec.invoice_id.amount_total:
                raise ValidationError(
                    _('Total payments on account (%s) would exceed the invoice total (%s). '
                      'Please enter a smaller amount.')
                    % (total, rec.invoice_id.amount_total)
                )

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_view_receipt(self):
        """Open the receipt image in a full-size dialog."""
        self.ensure_one()
        if not self.receipt_file:
            return
        wizard = self.env['construction.payment.receipt.wizard'].create({
            'payment_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Receipt — %s') % self.name,
            'res_model': 'construction.payment.receipt.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_cancel(self):
        """Cancel this payment and reverse the linked accounting payment."""
        self.ensure_one()
        payment = self.account_payment_id
        if payment and payment.state not in ('cancel', 'draft'):
            # For on-account payments: block if already reconciled against a bill
            # (user must unreconcile first). For final payments, action_draft()
            # handles unreconciliation automatically.
            if self.payment_type == 'on_account':
                payable_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'liability_payable'
                )
                if any(l.reconciled for l in payable_lines):
                    raise ValidationError(
                        _('Cannot cancel payment %s: it has already been reconciled '
                          'with a vendor bill. Please unreconcile it in accounting first.')
                        % self.name
                    )
            # Reset to draft first (required in Odoo 19; also unreconciles final payments)
            payment.action_draft()
            payment.action_cancel()
        elif payment and payment.state == 'draft':
            payment.action_cancel()
        self.invoice_id.message_post(
            body=_('Payment %s of %s cancelled.') % (self.name, self.amount)
        )


class ConstructionPaymentWizardMixin(models.AbstractModel):
    """
    Shared fields and helpers for payment wizard classes.

    Both the Pay-on-Account wizard and the Register Payment wizard share the
    same base fields, journal computation, and accounting payment creation logic.
    """
    _name = 'construction.payment.wizard.mixin'
    _description = 'Construction Payment Wizard Mixin'

    invoice_id = fields.Many2one(
        'construction.invoice',
        string='Invoice',
        required=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        'construction.project',
        related='invoice_id.project_id',
        string='Project',
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='invoice_id.currency_id',
        readonly=True,
    )
    payment_source = fields.Selection(
        PAYMENT_SOURCE_SELECTION,
        string='Payment Source',
        required=True,
        default='payroll_card',
        help='Select the account from which this payment will be made.',
    )
    amount = fields.Monetary(
        string='Amount to Pay',
        required=True,
        currency_field='currency_id',
    )
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.today,
    )
    memo = fields.Char(
        string='Memo / Reference',
        help='Internal reference note for this payment',
    )
    receipt_file = fields.Image(
        string='Receipt',
        attachment=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        compute='_compute_journal',
        readonly=True,
        store=False,
    )

    @api.depends('payment_source', 'project_id')
    def _compute_journal(self):
        for rec in self:
            if rec.payment_source == 'payroll_card':
                rec.journal_id = rec.project_id.payroll_journal_id
            else:
                rec.journal_id = rec.project_id.employer_journal_id

    def _raise_missing_journal(self):
        """Raise a descriptive ValidationError when no journal is configured."""
        if self.payment_source == 'payroll_card':
            raise ValidationError(
                _('This project does not have a Payroll Card Journal configured. '
                  'Please create one from the project form first.')
            )
        raise ValidationError(
            _('This project does not have an Employer Journal configured. '
              'Please set one on the project form first.')
        )

    def _build_accounting_payment_vals(self, invoice):
        """Return vals for creating an outbound supplier account.payment."""
        return {
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': invoice.partner_id.id,
            'amount': self.amount,
            'date': self.payment_date,
            'memo': self.memo or invoice.name,
            'journal_id': self.journal_id.id,
            'company_id': invoice.company_id.id,
        }


class ConstructionInvoicePrepaymentWizard(models.TransientModel):
    """
    Wizard to register a Pay-on-Account payment for a draft construction invoice.
    Creates an account.payment immediately and links it to the invoice via a
    construction.invoice.prepayment record (payment_type='on_account').
    """
    _name = 'construction.invoice.prepayment.wizard'
    _description = 'Pay on Account Wizard'
    _inherit = ['construction.payment.wizard.mixin']

    post_payment = fields.Selection([
        ('draft', 'Save as Draft'),
        ('posted', 'Post Immediately'),
    ], string='Payment Status', required=True, default='posted',
        help='Post Immediately records the payment in accounting right away. '
             'Save as Draft lets you review before posting.')

    # -------------------------------------------------------------------------
    # Defaults
    # -------------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        invoice_id = self.env.context.get('default_invoice_id')
        if invoice_id:
            invoice = self.env['construction.invoice'].browse(invoice_id)
            if invoice.amount_total:
                res['amount'] = max(invoice.amount_total - invoice.amount_prepaid, 0.0)
            res['memo'] = invoice.invoice_number or invoice.name
        return res

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_pay_on_account(self):
        """
        Validate inputs, create an account.payment for the vendor prepayment,
        and record it as a construction.invoice.prepayment (on_account) linked
        to the invoice.
        """
        self.ensure_one()
        invoice = self.invoice_id

        if not self.journal_id:
            self._raise_missing_journal()

        if self.amount <= 0:
            raise ValidationError(_('Payment amount must be greater than zero.'))

        if invoice.amount_total:
            remaining = invoice.amount_total - invoice.amount_prepaid
            if self.amount > remaining + 0.001:
                raise ValidationError(
                    _('Payment amount (%(paid)s) exceeds the remaining balance (%(balance)s).',
                      paid=self.amount, balance=remaining)
                )

        payment = self.env['account.payment'].create(
            self._build_accounting_payment_vals(invoice)
        )
        if self.post_payment == 'posted':
            payment.action_post()

        self.env['construction.invoice.prepayment'].create({
            'invoice_id': invoice.id,
            'payment_type': 'on_account',
            'payment_date': self.payment_date,
            'amount': self.amount,
            'payment_source': self.payment_source,
            'memo': self.memo or invoice.name,
            'account_payment_id': payment.id,
            'receipt_file': self.receipt_file,
        })

        if not invoice.payment_source:
            invoice.payment_source = self.payment_source

        return {'type': 'ir.actions.act_window_close'}


class ConstructionPaymentReceiptWizard(models.TransientModel):
    """
    Lightweight dialog used by action_view_receipt to display a payment's
    receipt image at full size in an Odoo modal window.
    """
    _name = 'construction.payment.receipt.wizard'
    _description = 'View Payment Receipt'

    payment_id = fields.Many2one(
        'construction.invoice.prepayment',
        readonly=True,
    )
    receipt_file = fields.Image(
        related='payment_id.receipt_file',
        readonly=True,
    )
    payment_name = fields.Char(
        related='payment_id.name',
        readonly=True,
    )
