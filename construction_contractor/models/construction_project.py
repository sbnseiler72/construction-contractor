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

    # Contractor fee journal: used when paying the contractor their percentage fee
    contractor_fee_journal_id = fields.Many2one(
        'account.journal',
        string='Contractor Fee Journal',
        domain=[('type', 'in', ['cash', 'bank'])],
        tracking=True,
        help='Default journal used when recording contractor fee payments',
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

    # -------------------------------------------------------------------------
    # Contractor Fee
    # -------------------------------------------------------------------------
    contractor_percentage = fields.Float(
        string='Contractor Percentage (%)',
        default=0.0,
        tracking=True,
        help='Percentage of eligible costs that goes to the contractor (e.g. 10 for 10%).',
    )
    contractor_fee_base = fields.Monetary(
        string='Contractor Fee Base',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
        help='Sum of eligible confirmed expenses and paid invoice amounts included in the contractor fee.',
    )
    total_contractor_fee = fields.Monetary(
        string='Total Contractor Fee',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
        help='Contractor percentage applied to the eligible cost base.',
    )
    contractor_fee_paid = fields.Monetary(
        string='Contractor Fee Paid',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
        help='Total confirmed payments made to the contractor for their fee.',
    )
    contractor_fee_balance = fields.Monetary(
        string='Contractor Fee Balance',
        compute='_compute_financials',
        currency_field='currency_id',
        store=False,
        help='Remaining contractor fee still owed: Total Fee − Fee Paid.',
    )
    contractor_fee_payment_ids = fields.One2many(
        'construction.contractor.fee.payment',
        'project_id',
        string='Contractor Fee Payments',
    )

    # -------------------------------------------------------------------------
    # Document Archive
    # -------------------------------------------------------------------------
    folder_ids = fields.One2many(
        'construction.project.folder',
        'project_id',
        string='Folders',
    )
    document_ids = fields.One2many(
        'construction.project.document',
        'project_id',
        string='Documents',
    )

    # Related record counts for smart buttons
    expense_count = fields.Integer(compute='_compute_counts')
    card_transaction_count = fields.Integer(compute='_compute_counts')
    invoice_count = fields.Integer(compute='_compute_counts')
    financial_balance_count = fields.Integer(compute='_compute_counts')
    contractor_fee_payment_count = fields.Integer(compute='_compute_counts')
    document_count = fields.Integer(compute='_compute_counts')

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(
                    _('Expected End Date cannot be earlier than Start Date.')
                )

    @api.constrains('contractor_percentage')
    def _check_contractor_percentage(self):
        for rec in self:
            if not (0.0 <= rec.contractor_percentage <= 100.0):
                raise ValidationError(
                    _('Contractor Percentage must be between 0 and 100.')
                )

    # -------------------------------------------------------------------------
    # Compute methods
    # -------------------------------------------------------------------------
    @api.depends()
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

            # Contractor fee calculations
            eligible_expenses = expenses.filtered(lambda e: e.include_in_contractor_fee)
            eligible_invoices = invoices.filtered(lambda i: i.include_in_contractor_fee)
            project.contractor_fee_base = (
                sum(eligible_expenses.mapped('amount'))
                + sum(eligible_invoices.mapped('amount_paid'))
            )
            project.total_contractor_fee = project.contractor_fee_base * project.contractor_percentage / 100.0

            fee_payments = self.env['construction.contractor.fee.payment'].search([
                ('project_id', '=', project.id),
                ('state', '=', 'confirmed'),
            ])
            project.contractor_fee_paid = sum(fee_payments.mapped('amount'))
            project.contractor_fee_balance = project.total_contractor_fee - project.contractor_fee_paid

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
            project.financial_balance_count = self.env['construction.financial.balance'].search_count([
                ('project_id', '=', project.id),
            ])
            project.contractor_fee_payment_count = self.env['construction.contractor.fee.payment'].search_count([
                ('project_id', '=', project.id),
            ])
            project.document_count = self.env['construction.project.document'].search_count([
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

    def action_view_financial_balance(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Financial Balance'),
            'res_model': 'construction.financial.balance',
            'view_mode': 'list,pivot',
            'domain': [('project_id', '=', self.id)],
        }

    def action_view_contractor_fee_payments(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contractor Fee Payments'),
            'res_model': 'construction.contractor.fee.payment',
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

    def action_create_contractor_fee_journal(self):
        """Create a dedicated cash journal for this project's contractor fee payments."""
        self.ensure_one()
        if self.contractor_fee_journal_id:
            raise ValidationError(_('A contractor fee journal already exists for this project.'))
        journal = self.env['account.journal'].create({
            'name': _('Contractor Fee - %s') % self.name,
            'code': ('CF%s' % self.code)[:5],
            'type': 'cash',
            'company_id': self.company_id.id,
        })
        self.contractor_fee_journal_id = journal
        return True

    def action_view_documents(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Documents'),
            'res_model': 'construction.project.document',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'search_default_group_folder': 1,
            },
        }

    def action_view_folders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Folders'),
            'res_model': 'construction.project.folder',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'search_default_root_folders': 1,
            },
        }

    def _create_default_folders(self):
        """Create the default folder structure for a newly activated project."""
        Folder = self.env['construction.project.folder']
        for project in self:
            existing = Folder.search_count([('project_id', '=', project.id)])
            if existing:
                continue
            for folder_vals in Folder._get_default_folder_structure():
                Folder.create({
                    **folder_vals,
                    'project_id': project.id,
                })

    def action_set_active(self):
        for rec in self:
            if not rec.contracted_amount or rec.contracted_amount <= 0:
                raise ValidationError(
                    _('Please enter the Contracted Amount before activating the project.')
                )
        self.write({'state': 'active'})
        self._create_default_folders()

    def action_set_closed(self):
        for rec in self:
            outstanding = self.env['construction.invoice'].search_count([
                ('project_id', '=', rec.id),
                ('state', '=', 'posted'),
                ('payment_state', 'not in', ['paid', 'reversed']),
            ])
            if outstanding:
                raise ValidationError(
                    _('Cannot close project "%s": there are %d unpaid invoice(s) outstanding. '
                      'Please settle or cancel them first.')
                    % (rec.name, outstanding)
                )
        self.write({'state': 'closed'})

    def action_set_cancelled(self):
        for rec in self:
            confirmed_expenses = self.env['construction.expense'].search_count([
                ('project_id', '=', rec.id),
                ('state', '=', 'confirmed'),
            ])
            if confirmed_expenses:
                raise ValidationError(
                    _('Cannot cancel project "%s": there are %d confirmed expense(s). '
                      'Please cancel them first.')
                    % (rec.name, confirmed_expenses)
                )
            posted_invoices = self.env['construction.invoice'].search_count([
                ('project_id', '=', rec.id),
                ('state', '=', 'posted'),
            ])
            if posted_invoices:
                raise ValidationError(
                    _('Cannot cancel project "%s": there are %d posted invoice(s). '
                      'Please cancel them first.')
                    % (rec.name, posted_invoices)
                )
            confirmed_fee_payments = self.env['construction.contractor.fee.payment'].search_count([
                ('project_id', '=', rec.id),
                ('state', '=', 'confirmed'),
            ])
            if confirmed_fee_payments:
                raise ValidationError(
                    _('Cannot cancel project "%s": there are %d confirmed fee payment(s). '
                      'Please cancel them first.')
                    % (rec.name, confirmed_fee_payments)
                )
        self.write({'state': 'cancelled'})

    def action_set_draft(self):
        self.write({'state': 'draft'})
