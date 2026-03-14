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
        currency_field='currency_id',
        tracking=True,
        help='Leave empty on draft invoices when the final amount is not yet known.',
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

    include_in_contractor_fee = fields.Boolean(
        string='Include in Contractor Fee',
        default=True,
        tracking=True,
        help='Uncheck to exclude this invoice from the contractor percentage calculation (e.g. insurance, government fees).',
    )

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

    # Prepayments / payments on account (registered while invoice is draft)
    prepayment_ids = fields.One2many(
        'construction.invoice.prepayment',
        'invoice_id',
        string='Payments on Account',
    )
    amount_prepaid = fields.Monetary(
        string='Prepaid Amount',
        compute='_compute_payment_amounts',
        currency_field='currency_id',
        store=False,
        help='Total confirmed payments on account made while invoice was in draft state',
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
    @api.depends(
        'account_move_id', 'account_move_id.amount_residual', 'amount_total',
        'prepayment_ids.amount', 'prepayment_ids.account_payment_id.state',
    )
    def _compute_payment_amounts(self):
        for rec in self:
            posted_prepayments = rec.prepayment_ids.filtered(
                lambda p: p.account_payment_id and p.account_payment_id.state in ('in_process', 'paid')
            )
            rec.amount_prepaid = sum(posted_prepayments.mapped('amount'))

            if rec.account_move_id:
                rec.amount_residual = rec.account_move_id.amount_residual
                rec.amount_paid = rec.amount_total - rec.account_move_id.amount_residual
            else:
                rec.amount_residual = max(rec.amount_total - rec.amount_prepaid, 0.0)
                rec.amount_paid = rec.amount_prepaid

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.invoice') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'amount_total' in vals:
            for rec in self:
                rec._sync_amount_to_vendor_bill()
        return res

    def unlink(self):
        for rec in self:
            rec._cancel_vendor_bill(force_delete=True)
        return super().unlink()

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('amount_total', 'state')
    def _check_amount(self):
        for rec in self:
            if rec.state != 'draft' and rec.amount_total <= 0:
                raise ValidationError(_('Invoice total must be greater than zero.'))

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_pay_on_account(self):
        """Open the Pay on Account wizard for a draft invoice."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(
                _('Payments on account can only be registered for draft invoices.')
            )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pay on Account'),
            'res_model': 'construction.invoice.prepayment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_invoice_id': self.id},
        }

    def action_create_vendor_bill(self):
        """
        Create the corresponding native vendor bill (account.move).
        Uses a single 'catch-all' line mapped to a general expense account.
        Invoice lines can be expanded in a future phase.
        """
        self.ensure_one()
        if self.account_move_id:
            raise ValidationError(_('A vendor bill already exists for this invoice.'))
        if not self.amount_total or self.amount_total <= 0:
            raise ValidationError(
                _('Please enter the Invoice Total before creating the vendor bill.')
            )

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

        # Post the bill and auto-reconcile any outstanding prepayments
        if move.state == 'draft':
            move.action_post()

        posted_prepayments = self.prepayment_ids.filtered(
            lambda p: p.account_payment_id and p.account_payment_id.state in ('in_process', 'paid')
        )
        if posted_prepayments:
            self._reconcile_prepayments_with_bill(move, posted_prepayments)

        return True

    def _reconcile_prepayments_with_bill(self, move, prepayments):
        """
        Reconcile posted prepayment lines with the vendor bill's payable line.
        Finds matching payable/credit lines by account and reconciles them so
        the bill reflects the already-paid amount.
        """
        # Get the payable line on the vendor bill
        payable_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled
        )
        if not payable_lines:
            return

        payable_account = payable_lines[:1].account_id

        # Gather unreconciled credit lines from each prepayment payment
        credit_lines = self.env['account.move.line']
        for prepayment in prepayments:
            payment_lines = prepayment.account_payment_id.line_ids.filtered(
                lambda l: l.account_id == payable_account and not l.reconciled
            )
            credit_lines |= payment_lines

        if credit_lines:
            (payable_lines[:1] | credit_lines).reconcile()

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
            active_prepayments = rec.prepayment_ids.filtered(
                lambda p: p.account_payment_id
                and p.account_payment_id.state in ('in_process', 'paid')
            )
            if active_prepayments:
                raise ValidationError(
                    _('Cannot cancel invoice %s: it has %d active prepayment(s) on account. '
                      'Please cancel those prepayments first.')
                    % (rec.name, len(active_prepayments))
                )
            rec._cancel_vendor_bill()
            rec.state = 'cancelled'

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------
    def _cancel_vendor_bill(self, force_delete=False):
        """
        Cancel (and optionally delete) the linked vendor bill when the
        construction invoice is cancelled or deleted.

        Rules:
        - Draft bill: always cancel/delete.
        - Posted bill with no payments: reset to draft then cancel/delete.
        - Posted bill with payments: raise – user must reverse payments first.
        """
        self.ensure_one()
        move = self.account_move_id
        if not move:
            return

        if move.state == 'posted':
            # Block if payments have been registered
            if move.payment_state not in ('not_paid', False):
                raise ValidationError(
                    _('Cannot cancel invoice %s: the linked vendor bill has registered '
                      'payments. Please reverse those payments in accounting first.')
                    % self.name
                )
            move.button_draft()

        if force_delete:
            self.account_move_id = False
            move.unlink()
        else:
            move.button_cancel()

    def _sync_amount_to_vendor_bill(self):
        """
        Keep the vendor bill's invoice line in sync when amount_total is edited.
        Only runs when a bill is linked and not yet fully paid.
        """
        self.ensure_one()
        move = self.account_move_id
        if not move or not self.amount_total:
            return

        if move.payment_state not in ('not_paid', False):
            raise ValidationError(
                _('Cannot change the invoice total after payments have been registered. '
                  'Please reverse the payments first.')
            )

        was_posted = move.state == 'posted'
        if was_posted:
            move.button_draft()

        # Update the single catch-all line with the new amount
        if move.invoice_line_ids:
            move.invoice_line_ids[0].price_unit = self.amount_total

        if was_posted:
            move.action_post()
