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
    _inherit = ['construction.payment.wizard.mixin']

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
            self._raise_missing_journal()

        if not invoice.account_move_id:
            raise ValidationError(_('Please create the vendor bill for this invoice first.'))

        if self.amount <= 0:
            raise ValidationError(_('Payment amount must be greater than zero.'))

        move = invoice.account_move_id
        if move.state == 'draft':
            move.action_post()

        payment = self.env['account.payment'].create(
            self._build_accounting_payment_vals(invoice)
        )
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
        })

        return {'type': 'ir.actions.act_window_close'}
