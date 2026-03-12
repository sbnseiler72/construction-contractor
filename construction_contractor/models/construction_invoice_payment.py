# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionInvoicePaymentWizard(models.TransientModel):
    """
    Wizard to register payment for a construction invoice.
    Captures payment source (Payroll Card or Employer) and pre-fills
    the appropriate accounting journal before opening Odoo's native
    payment registration wizard.
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
        Validate payment source, set invoice.payment_source, then open Odoo's
        native account.payment.register wizard pre-filled with the correct journal.
        """
        self.ensure_one()

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

        if not self.invoice_id.account_move_id:
            raise ValidationError(
                _('Please create the vendor bill for this invoice first.')
            )

        move = self.invoice_id.account_move_id
        if move.state == 'draft':
            move.action_post()

        # Record the payment source on the invoice before opening the payment wizard
        self.invoice_id.payment_source = self.payment_source

        # Open Odoo's native payment registration wizard, pre-filled
        ctx = dict(
            active_model='account.move',
            active_ids=[move.id],
            default_journal_id=self.journal_id.id,
            default_amount=self.amount,
            default_payment_date=self.payment_date,
            default_ref=self.memo or self.invoice_id.name,
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }
