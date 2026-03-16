# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionInvoicePaymentWizard(models.TransientModel):
    """
    Wizard to register a final payment against a posted construction invoice
    (vendor bill must exist). Creates an account.payment directly, reconciles
    it with the vendor bill, and records it as a construction.invoice.prepayment
    (payment_type='final') so it appears alongside on-account payments in the
    invoice's unified payment list.
    """
    _name = 'construction.invoice.payment.wizard'
    _description = 'Construction Invoice Payment Wizard'

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
        help='Select the account from which this invoice will be paid.')
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
    receipt_file = fields.Binary(
        string='Receipt File',
        attachment=True,
    )
    receipt_filename = fields.Char(string='Receipt Filename')
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
            res['amount'] = invoice.amount_residual
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
    def action_pay(self):
        """
        Create an account.payment, post it, reconcile with the vendor bill,
        and record it as a final construction payment line on the invoice.
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

        if not invoice.account_move_id:
            raise ValidationError(_('Please create the vendor bill for this invoice first.'))

        if self.amount <= 0:
            raise ValidationError(_('Payment amount must be greater than zero.'))

        move = invoice.account_move_id
        if move.state == 'draft':
            move.action_post()

        # Create and post the accounting payment
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
        payment.action_post()

        # Reconcile with the vendor bill's payable line
        payable_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled
        )
        if payable_lines:
            payable_account = payable_lines[:1].account_id
            payment_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == payable_account and not l.reconciled
            )
            if payment_lines:
                (payable_lines[:1] | payment_lines).reconcile()

        # Record as a final payment line on the invoice
        invoice.payment_source = self.payment_source
        self.env['construction.invoice.prepayment'].create({
            'invoice_id': invoice.id,
            'payment_type': 'final',
            'payment_date': self.payment_date,
            'amount': self.amount,
            'payment_source': self.payment_source,
            'memo': self.memo or invoice.name,
            'account_payment_id': payment.id,
            'receipt_file': self.receipt_file,
            'receipt_filename': self.receipt_filename,
        })

        return {'type': 'ir.actions.act_window_close'}
