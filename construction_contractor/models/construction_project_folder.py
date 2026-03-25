# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ConstructionProjectFolder(models.Model):
    """Hierarchical folder structure for organizing project documents."""
    _name = 'construction.project.folder'
    _description = 'Construction Project Folder'
    _order = 'sequence, name'
    _parent_name = 'parent_id'
    _parent_store = True

    name = fields.Char(string='Folder Name', required=True, translate=True)
    project_id = fields.Many2one(
        'construction.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    parent_id = fields.Many2one(
        'construction.project.folder',
        string='Parent Folder',
        ondelete='cascade',
        index=True,
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many(
        'construction.project.folder',
        'parent_id',
        string='Sub-folders',
    )
    document_ids = fields.One2many(
        'construction.project.document',
        'folder_id',
        string='Documents',
    )
    phase_id = fields.Many2one(
        'construction.project.phase',
        string='Construction Phase',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    document_count = fields.Integer(
        string='Documents',
        compute='_compute_document_count',
    )
    color = fields.Integer(string='Color')

    _sql_constraints = [
        (
            'name_parent_project_uniq',
            'unique (name, parent_id, project_id)',
            'A folder with this name already exists at this level!',
        ),
    ]

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError('Error! You cannot create recursive folders.')

    @api.depends('document_ids')
    def _compute_document_count(self):
        for folder in self:
            folder.document_count = len(folder.document_ids)

    @api.model
    def _get_default_folder_structure(self):
        """Return list of default folder definitions for new projects."""
        return [
            {'name': 'عکس‌های سایت', 'sequence': 10},        # Site Photos
            {'name': 'نقشه‌ها و طرح‌ها', 'sequence': 20},     # Plans & Drawings
            {'name': 'مجوزها و تأییدیه‌ها', 'sequence': 30},  # Permits & Approvals
            {'name': 'قراردادها', 'sequence': 40},             # Contracts
            {'name': 'گزارش‌های بازرسی', 'sequence': 50},     # Inspection Reports
            {'name': 'مستندات اجرایی', 'sequence': 60},       # As-Built Documents
        ]
