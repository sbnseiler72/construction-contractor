# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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

        Priority:
          1. Active projects where the user is the Project Manager (most recent first).
          2. Any-state projects where the user is the Project Manager (most recent first).
          3. Any active project accessible to the user (most recent first).
        """
        user = self.env.user
        Project = self.env['construction.project']

        # Priority 1 & 2: projects the user manages
        managed = Project.search(
            [('manager_id', '=', user.id), ('state', '=', 'active')],
            order='date_start desc',
            limit=1,
        )
        if not managed:
            managed = Project.search(
                [('manager_id', '=', user.id)],
                order='date_start desc',
                limit=1,
            )
        if managed:
            return managed

        # Priority 3: any active project accessible to this user
        return Project.search(
            [('state', '=', 'active')],
            order='date_start desc',
            limit=1,
        )

    # -------------------------------------------------------------------------
    # Jalali <-> Gregorian conversion (mirrors the JS algorithm in jalali_date_field.js)
    # -------------------------------------------------------------------------
    @staticmethod
    def _jalali_to_gregorian(jy, jm, jd):
        """Convert a Jalali (Shamsi) date to a Gregorian (year, month, day) tuple."""
        jy -= 979
        jm -= 1
        jd -= 1
        j_d_no = (
            365 * jy
            + (jy // 33) * 8
            + (jy % 33 + 3) // 4
        )
        for i in range(jm):
            j_d_no += 31 if i < 6 else 30
        j_d_no += jd
        g_d_no = j_d_no + 79
        gy = 1600 + 400 * (g_d_no // 146097)
        g_d_no %= 146097
        leap = True
        if g_d_no >= 36525:
            g_d_no -= 1
            gy += 100 * (g_d_no // 36524)
            g_d_no %= 36524
            if g_d_no >= 365:
                g_d_no += 1
            else:
                leap = False
        gy += 4 * (g_d_no // 1461)
        g_d_no %= 1461
        if g_d_no >= 366:
            leap = False
            g_d_no -= 1
            gy += g_d_no // 365
            g_d_no %= 365
        g_days_in_month = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        i = 0
        while i < 12 and g_d_no >= g_days_in_month[i]:
            g_d_no -= g_days_in_month[i]
            i += 1
        return gy, i + 1, g_d_no + 1

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

        Supported filename patterns (8-digit segment between first and second '-'):
          IMG-14040225-WA0000.jpg   → Jalali 1404/02/25  → Gregorian stored date
          PTT-20250610-WA0024.jpeg  → Gregorian 2025/06/10

        Years 1300–1500 are treated as Jalali; 1900–2100 as Gregorian.
        The field is left unchanged if no recognisable pattern is found.
        """
        if not self.receipt_filename:
            return
        match = re.search(r'^[^-]+-(\d{8})-', self.receipt_filename)
        if not match:
            return
        digits = match.group(1)
        year = int(digits[0:4])
        month = int(digits[4:6])
        day = int(digits[6:8])
        try:
            if 1300 <= year <= 1500:  # Jalali year
                gy, gm, gd = self._jalali_to_gregorian(year, month, day)
                self.date = '%04d-%02d-%02d' % (gy, gm, gd)
            elif 1900 <= year <= 2100:  # Gregorian year
                # Validate via fields.Date to ensure it is a real calendar date
                self.date = fields.Date.to_date('%04d-%02d-%02d' % (year, month, day))
        except Exception:
            pass  # Invalid date components — leave the field unchanged

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
