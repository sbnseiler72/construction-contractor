# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api


class ConstructionProjectDocument(models.Model):
    """A file/document attached to a project, organized in folders."""
    _name = 'construction.project.document'
    _description = 'Construction Project Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'is_starred desc, date desc, id desc'

    name = fields.Char(
        string='Document Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
    )
    project_id = fields.Many2one(
        'construction.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    folder_id = fields.Many2one(
        'construction.project.folder',
        string='Folder',
        ondelete='set null',
        index=True,
        tracking=True,
        domain="[('project_id', '=', project_id)]",
    )
    phase_id = fields.Many2one(
        'construction.project.phase',
        string='Construction Phase',
        tracking=True,
    )
    file = fields.Binary(
        string='File',
        attachment=True,
        required=True,
    )
    file_name = fields.Char(string='File Name')
    file_size = fields.Integer(
        string='File Size (bytes)',
        compute='_compute_file_size',
        store=True,
    )
    file_size_display = fields.Char(
        string='File Size',
        compute='_compute_file_size',
        store=True,
    )
    file_type = fields.Selection(
        [
            ('image', 'Image'),
            ('document', 'Document'),
            ('plan', 'Plan / Drawing'),
            ('permit', 'Permit'),
            ('report', 'Report'),
            ('other', 'Other'),
        ],
        string='Type',
        default='other',
        required=True,
        tracking=True,
    )
    tag_ids = fields.Many2many(
        'construction.document.tag',
        'construction_document_tag_rel',
        'document_id',
        'tag_id',
        string='Tags',
    )
    description = fields.Text(string='Notes')
    date = fields.Date(
        string='Document Date',
        default=fields.Date.context_today,
    )
    uploaded_by = fields.Many2one(
        'res.users',
        string='Uploaded By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    is_starred = fields.Boolean(
        string='Starred',
        default=False,
    )
    thumbnail = fields.Image(
        string='Thumbnail',
        compute='_compute_thumbnail',
        store=True,
        max_width=256,
        max_height=256,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'construction.project.document'
                ) or 'New'
        return super().create(vals_list)

    @api.depends('file')
    def _compute_file_size(self):
        # Read without bin_size context so we get actual base64 data
        for doc in self.with_context(bin_size=False):
            if doc.file:
                try:
                    size = len(base64.b64decode(doc.file))
                except Exception:
                    size = 0
                doc.file_size = size
                if size < 1024:
                    doc.file_size_display = f'{size} B'
                elif size < 1024 * 1024:
                    doc.file_size_display = f'{size / 1024:.1f} KB'
                else:
                    doc.file_size_display = f'{size / (1024 * 1024):.1f} MB'
            else:
                doc.file_size = 0
                doc.file_size_display = ''

    @api.depends('file', 'file_type')
    def _compute_thumbnail(self):
        for doc in self:
            if doc.file_type == 'image' and doc.file:
                doc.thumbnail = doc.file
            else:
                doc.thumbnail = False

    def action_toggle_star(self):
        for doc in self:
            doc.is_starred = not doc.is_starred
