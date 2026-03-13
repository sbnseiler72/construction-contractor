# -*- coding: utf-8 -*-
from odoo import models, fields


class ConstructionProjectPhase(models.Model):
    _name = 'construction.project.phase'
    _description = 'Construction Project Phase'
    _rec_name = 'label'
    _order = 'sequence, id'

    key = fields.Char(string='Key', required=True)
    label = fields.Char(string='Label', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('key_unique', 'unique(key)', 'Phase key must be unique.'),
    ]
