# -*- coding: utf-8 -*-
import re
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from ..utils import JalaliUtils

# Compiled once at module load; matches the 8-digit date segment in filenames
# such as "IMG-14040225-WA0000.jpg" or "PTT-20250610-WA0024.jpeg".
_FILENAME_DATE_RE = re.compile(r'^[^-]+-(\d{8})-')


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
        default=lambda self: self._default_project_id(),
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
    # Default helpers
    # -------------------------------------------------------------------------
    @api.model
    def _default_project_id(self):
        """Pre-select a project for new expenses based on the current user's role.

        Searches projects managed by the user first, preferring active ones
        ('active' sorts before 'cancelled', 'closed', 'draft' alphabetically).
        Falls back to any accessible active project.
        """
        Project = self.env['construction.project']
        managed = Project.search(
            [('manager_id', '=', self.env.user.id)],
            order='state asc, date_start desc',
            limit=1,
        )
        if managed:
            return managed
        return Project.search(
            [('state', '=', 'active')],
            order='date_start desc',
            limit=1,
        )

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------
    @api.onchange('expense_type_id')
    def _onchange_expense_type_contractor_fee(self):
        if self.expense_type_id:
            self.include_in_contractor_fee = self.expense_type_id.include_in_contractor_fee

    @api.onchange('receipt_filename')
    def _onchange_receipt_filename_date(self):
        """Auto-fill the expense date from a date encoded in the receipt filename.

        Supported patterns (8-digit segment between the first two '-' delimiters):
          IMG-14040225-WA0000.jpg   → Jalali 1404/02/25
          PTT-20250610-WA0024.jpeg  → Gregorian 2025/06/10

        The field is left unchanged if no recognisable pattern is found.
        """
        if not self.receipt_filename:
            return
        match = _FILENAME_DATE_RE.search(self.receipt_filename)
        if not match:
            return
        digits = match.group(1)
        year = int(digits[:4])
        try:
            if JalaliUtils.JALALI_YEAR_MIN <= year <= JalaliUtils.JALALI_YEAR_MAX:
                jy, jm, jd = int(digits[:4]), int(digits[4:6]), int(digits[6:])
                gy, gm, gd = JalaliUtils.jalali_to_gregorian(jy, jm, jd)
                self.date = fields.Date.to_date('%04d-%02d-%02d' % (gy, gm, gd))
            elif JalaliUtils.GREGORIAN_YEAR_MIN <= year <= JalaliUtils.GREGORIAN_YEAR_MAX:
                self.date = fields.Date.to_date(
                    datetime.strptime(digits, '%Y%m%d').date().isoformat()
                )
        except ValueError:
            pass  # Malformed date components — leave the field unchanged

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
            if rec.project_id.state in ('closed', 'cancelled'):
                raise ValidationError(
                    _('Cannot confirm expense "%s": the project is %s.')
                    % (rec.name, dict(rec.project_id._fields['state'].selection)[rec.project_id.state])
                )
            if not rec.receipt_ref and not rec.receipt_file:
                raise ValidationError(
                    _('A receipt reference or file attachment is required before confirming an expense.')
                )
            rec.state = 'confirmed'

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
