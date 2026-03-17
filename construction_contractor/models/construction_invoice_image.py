# -*- coding: utf-8 -*-
from odoo import models, fields


class ConstructionInvoiceImage(models.Model):
    """
    An image attached to a construction invoice document.
    Using fields.Image ensures only valid image files are accepted.
    """
    _name = 'construction.invoice.image'
    _description = 'Construction Invoice Image'
    _order = 'sequence, id'

    invoice_id = fields.Many2one(
        'construction.invoice',
        required=True,
        ondelete='cascade',
    )
    image = fields.Image(
        string='Image',
        required=True,
        attachment=True,
    )
    name = fields.Char(string='Description')
    sequence = fields.Integer(default=10)
