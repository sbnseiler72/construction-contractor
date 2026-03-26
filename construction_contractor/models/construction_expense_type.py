# -*- coding: utf-8 -*-
from odoo import models, fields


class ConstructionExpenseType(models.Model):
    _name = 'construction.expense.type'
    _description = 'Construction Expense Type'
    _rec_name = 'label'
    _order = 'sequence, id'

    key = fields.Char(string='Key', required=True)
    label = fields.Char(string='Label', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    include_in_contractor_fee = fields.Boolean(
        string='Include in Contractor Fee',
        default=True,
        help='If unchecked, expenses of this type are excluded from the contractor percentage calculation.',
    )

    key_unique = models.Constraint('unique(key)', 'Expense type key must be unique.')
