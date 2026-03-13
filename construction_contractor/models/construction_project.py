# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionProject(models.Model):
    _name = 'construction.project'
    _description = 'Construction Contractor Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, name'

    # -------------------------------------------------------------------------
    # Basic Info
    # -------------------------------------------------------------------------
    name = fields.Char(
        string='Project Name',
        required=True,
        tracking=True,
        help='Name of the construction project',
    )
    code = fields.Char(
        string='Project Code',
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)

    employer_id = fields.Many2one(
        'res.partner',
        string='Employer',
        required=True,
        tracking=True,
        help='The employer / client funding this project',
    )
    manager_id = fields.Many2one(
        'res.users',
        string='Project Manager',
        default=lambda self: self.env.user,
        tracking=True,
    )
    date_start = fields.Date(string='Start Date', tracking=True)
    date_end = fields.Date(string='Expected End Date', tracking=True)
    description = fields.Text(string='Description')

    # -------------------------------------------------------------------------
    # Financial
    # -------------------------------------------------------------------------
    contracted_amount = fields.Monetary(
        string='Contracted Amount',
        currency_field='currency_id',
        tracking=True,
        help='Total contracted value of the project',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    # Payroll card: a dedicated cash journal created per project
    payroll_journal_id = fields.Many2one(
        'account.journal',
        string='Payroll Card Journal',
        domain=[('type', 'in', ['cash', 'bank'])],
        tracking=True,
        help='Dedicated cash/bank journal acting as the project payroll card',
    )

    # Employer journal: used when employer pays invoices/expenses directly
    employer_journal_id = fields.Many2one(
        'account.journal',
        string='Employer Journal',
        domain=[('type', 'in', ['cash', 'bank'])],
        tracking=True,
        help='Journal used when the employer pays invoices or expenses directly',
    )

    # -------------------------------------------------------------------------
    # Computed financial summaries
    # -------------------------------------------------------------------------
    total_card_deposits = fields.Monetary(
        string='Total Card Deposits',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
    )
    total_expenses = fields.Monetary(
        string='Total Expenses',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
    )
    total_invoiced = fields.Monetary(
        string='Total Invoiced',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
    )
    total_paid_invoices = fields.Monetary(
        string='Total Paid on Invoices',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
    )
    outstanding_invoices = fields.Monetary(
        string='Outstanding Invoice Balance',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
    )

    # Payment source breakdowns
    total_paid_from_card = fields.Monetary(
        string='Total Paid from Payroll Card',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
        help='Sum of confirmed payroll-card expenses plus invoice payments made from the payroll card',
    )
    total_paid_by_employer = fields.Monetary(
        string='Total Paid by Employer',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
        help='Sum of confirmed employer expenses plus invoice payments made by the employer',
    )
    payroll_card_balance = fields.Monetary(
        string='Payroll Card Balance',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
        help='Remaining balance on the payroll card: Deposits minus all card payments',
    )

    # Related record counts for smart buttons
    expense_count = fields.Integer(compute='_compute_counts')
    card_transaction_count = fields.Integer(compute='_compute_counts')
    invoice_count = fields.Integer(compute='_compute_counts')

    # -------------------------------------------------------------------------
    # Compute methods
    # -------------------------------------------------------------------------
    @api.depends('company_id')
    def _compute_financials(self):
        for project in self:
            expenses = self.env['construction.expense'].search([
                ('project_id', '=', project.id),
                ('state', '=', 'confirmed'),
            ])
            project.total_expenses = sum(expenses.mapped('amount'))

            deposits = self.env['construction.card.transaction'].search([
                ('project_id', '=', project.id),
                ('transaction_type', '=', 'deposit'),
                ('state', '=', 'confirmed'),
            ])
            project.total_card_deposits = sum(deposits.mapped('amount'))

            invoices = self.env['construction.invoice'].search([
                ('project_id', '=', project.id),
            ])
            project.total_invoiced = sum(invoices.mapped('amount_total'))
            project.total_paid_invoices = sum(invoices.mapped('amount_paid'))
            project.outstanding_invoices = sum(invoices.mapped('amount_residual'))

            # Payment source breakdowns
            card_expenses = expenses.filtered(
                lambda e: e.payment_source == 'payroll_card'
            )
            employer_expenses = expenses.filtered(
                lambda e: e.payment_source in ('employer_cash', 'employer_check')
            )
            card_invoices = invoices.filtered(
                lambda i: i.payment_source == 'payroll_card'
            )
            employer_invoices = invoices.filtered(
                lambda i: i.payment_source in ('employer_cash', 'employer_check')
            )

            project.total_paid_from_card = (
                sum(card_expenses.mapped('amount'))
                + sum(card_invoices.mapped('amount_paid'))
            )
            project.total_paid_by_employer = (
                sum(employer_expenses.mapped('amount'))
                + sum(employer_invoices.mapped('amount_paid'))
            )
            project.payroll_card_balance = (
                project.total_card_deposits - project.total_paid_from_card
            )

    def _compute_counts(self):
        for project in self:
            project.expense_count = self.env['construction.expense'].search_count([
                ('project_id', '=', project.id),
            ])
            project.card_transaction_count = self.env['construction.card.transaction'].search_count([
                ('project_id', '=', project.id),
            ])
            project.invoice_count = self.env['construction.invoice'].search_count([
                ('project_id', '=', project.id),
            ])

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code('construction.project') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Action methods for smart buttons
    # -------------------------------------------------------------------------
    def action_view_expenses(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Expenses'),
            'res_model': 'construction.expense',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_card_transactions(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payroll Card Transactions'),
            'res_model': 'construction.card.transaction',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'construction.invoice',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_create_payroll_journal(self):
        """Create a dedicated cash journal for this project's payroll card."""
        self.ensure_one()
        if self.payroll_journal_id:
            raise ValidationError(_('A payroll card journal already exists for this project.'))
        journal = self.env['account.journal'].create({
            'name': _('Payroll Card - %s') % self.name,
            'code': ('PC%s' % self.code)[:5],
            'type': 'cash',
            'company_id': self.company_id.id,
        })
        self.payroll_journal_id = journal
        return True

    def action_create_employer_journal(self):
        """Create a dedicated cash journal for this project's employer payments."""
        self.ensure_one()
        if self.employer_journal_id:
            raise ValidationError(_('An employer journal already exists for this project.'))
        journal = self.env['account.journal'].create({
            'name': _('Employer - %s') % self.name,
            'code': ('EM%s' % self.code)[:5],
            'type': 'cash',
            'company_id': self.company_id.id,
        })
        self.employer_journal_id = journal
        return True

    def action_set_active(self):
        self.write({'state': 'active'})

    def action_set_closed(self):
        self.write({'state': 'closed'})

    def action_set_cancelled(self):
        self.write({'state': 'cancelled'})

    def action_set_draft(self):
        self.write({'state': 'draft'})
