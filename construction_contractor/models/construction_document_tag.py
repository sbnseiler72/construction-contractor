# -*- coding: utf-8 -*-
from odoo import models, fields


class ConstructionDocumentTag(models.Model):
    """Tags for categorizing project documents (e.g., Plan, Drawing, Permit)."""
    _name = 'construction.document.tag'
    _description = 'Construction Document Tag'
    _order = 'name'

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tag name must be unique!'),
    ]
