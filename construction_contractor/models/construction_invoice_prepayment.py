# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionInvoicePrepayment(models.Model):
    """
    Persistent record of a payment on account made against a draft
    construction invoice. Each record is backed by an account.payment so
    that the payment appears in the accounting ledger immediately.

    When the invoice is later formalised (vendor bill created), the linked
    account.payment entries are auto-reconciled against the new bill.
    """
    _name = 'construction.invoice.prepayment'
    _description = 'Construction Invoice Prepayment (Payment on Account)'
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
    payment_source = fields.Selection([
        ('payroll_card', 'Payroll Card'),
        ('employer_cash', 'Employer Account - Cash'),
        ('employer_check', 'Employer Account - Check'),
    ], string='Payment Source', required=True, tracking=True)
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
    @api.constrains('amount', 'invoice_id')
    def _check_amount_does_not_exceed_invoice(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Prepayment amount must be greater than zero.'))
            # Skip the cap check when the invoice total is not yet known (draft with no amount)
            if not rec.invoice_id.amount_total:
                continue
            other_active = rec.invoice_id.prepayment_ids.filtered(
                lambda p: p.id != rec.id
                and p.account_payment_id
                and p.account_payment_id.state in ('in_process', 'paid')
            )
            total = sum(other_active.mapped('amount')) + rec.amount
            if total > rec.invoice_id.amount_total:
                raise ValidationError(
                    _('Total prepayments (%s) would exceed the invoice total (%s). '
                      'Please enter a smaller amount.')
                    % (total, rec.invoice_id.amount_total)
                )

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_cancel(self):
        """Cancel this prepayment and reverse the linked accounting payment."""
        self.ensure_one()
        payment = self.account_payment_id
        if payment and payment.state not in ('cancel', 'draft'):
            # Check the payment is not already reconciled against a bill
            payable_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'liability_payable'
            )
            if any(l.reconciled for l in payable_lines):
                raise ValidationError(
                    _('Cannot cancel prepayment %s: it has already been reconciled '
                      'with a vendor bill. Please unreconcile it in accounting first.')
                    % self.name
                )
            # Must reset to draft before cancelling in Odoo 19
            payment.action_draft()
            payment.action_cancel()
        elif payment and payment.state == 'draft':
            payment.action_cancel()
        self.invoice_id.message_post(
            body=_('Prepayment %s of %s cancelled.')
            % (self.name, self.amount)
        )


class ConstructionInvoicePrepaymentWizard(models.TransientModel):
    """
    Wizard to register a payment on account for a draft construction invoice.
    Creates an account.payment (vendor prepayment) immediately so the
    disbursement is recorded in accounting, and links it to the invoice via
    a construction.invoice.prepayment record.
    """
    _name = 'construction.invoice.prepayment.wizard'
    _description = 'Pay on Account Wizard'

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
    payment_source = fields.Selection([
        ('payroll_card', 'Payroll Card'),
        ('employer_cash', 'Employer Account - Cash'),
        ('employer_check', 'Employer Account - Check'),
    ], string='Payment Source', required=True, default='payroll_card',
        help='Select the account from which this prepayment will be made.')
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
        help='Internal reference note for this prepayment',
    )
    post_payment = fields.Selection([
        ('draft', 'Save as Draft'),
        ('posted', 'Post Immediately'),
    ], string='Payment Status', required=True, default='posted',
        help='Post Immediately records the payment in accounting right away. '
             'Save as Draft lets you review before posting.')
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        compute='_compute_journal',
        readonly=True,
        store=False,
    )

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
    # Computed
    # -------------------------------------------------------------------------
    @api.depends('payment_source', 'project_id')
    def _compute_journal(self):
        for rec in self:
            if rec.payment_source == 'payroll_card':
                rec.journal_id = rec.project_id.payroll_journal_id
            else:
                rec.journal_id = rec.project_id.employer_journal_id

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_pay_on_account(self):
        """
        Validate inputs, create an account.payment for the vendor prepayment,
        and record it as a construction.invoice.prepayment linked to the invoice.
        """
        self.ensure_one()
        invoice = self.invoice_id

        if not self.journal_id:
            if self.payment_source == 'payroll_card':
                raise ValidationError(
                    _('This project does not have a Payroll Card Journal configured. '
                      'Please create one from the project form first.')
                )
            else:
                raise ValidationError(
                    _('This project does not have an Employer Journal configured. '
                      'Please set one on the project form first.')
                )

        if self.amount <= 0:
            raise ValidationError(_('Payment amount must be greater than zero.'))

        # Only check the cap when the invoice total is already known
        if invoice.amount_total:
            remaining = invoice.amount_total - invoice.amount_prepaid
            if self.amount > remaining + 0.001:
                raise ValidationError(
                    _('Payment amount (%(paid)s) exceeds the remaining balance (%(balance)s).',
                      paid=self.amount, balance=remaining)
                )

        # Create the accounting payment (outbound = paying a supplier)
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': invoice.partner_id.id,
            'amount': self.amount,
            'date': self.payment_date,
            'memo': self.memo or invoice.name,
            'journal_id': self.journal_id.id,
            'company_id': invoice.company_id.id,
        })
        if self.post_payment == 'posted':
            payment.action_post()

        # Record the prepayment linked to the invoice
        self.env['construction.invoice.prepayment'].create({
            'invoice_id': invoice.id,
            'payment_date': self.payment_date,
            'amount': self.amount,
            'payment_source': self.payment_source,
            'memo': self.memo or invoice.name,
            'account_payment_id': payment.id,
        })

        # Store payment source on the invoice if not already recorded
        if not invoice.payment_source:
            invoice.payment_source = self.payment_source

        return {'type': 'ir.actions.act_window_close'}
