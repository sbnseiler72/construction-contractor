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

    _sql_constraints = [
        ('key_unique', 'unique(key)', 'Expense type key must be unique.'),
    ]
