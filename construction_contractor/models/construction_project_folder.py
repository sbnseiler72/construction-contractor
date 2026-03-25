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
        compute='_compute_counts',
    )
    subfolder_count = fields.Integer(
        string='Sub-folders',
        compute='_compute_counts',
    )
    total_document_count = fields.Integer(
        string='Total Documents',
        compute='_compute_counts',
        recursive=True,
        help='Total documents including sub-folders',
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

    @api.depends('document_ids', 'child_ids', 'child_ids.total_document_count')
    def _compute_counts(self):
        for folder in self:
            folder.document_count = len(folder.document_ids)
            folder.subfolder_count = len(folder.child_ids)
            # Recursive total: own documents + all sub-folder totals
            sub_total = sum(child.total_document_count for child in folder.child_ids)
            folder.total_document_count = folder.document_count + sub_total

    def action_open_folder(self):
        """Navigate into this folder - show its contents (sub-folders + documents)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'construction.project.folder',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_open_subfolder_kanban(self):
        """Open sub-folders of this folder as kanban cards."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'construction.project.folder',
            'view_mode': 'kanban,list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {
                'default_parent_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }

    def action_view_documents(self):
        """Open documents in this folder as kanban/list."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': '%s - Documents' % self.name,
            'res_model': 'construction.project.document',
            'view_mode': 'kanban,list,form',
            'domain': [('folder_id', '=', self.id)],
            'context': {
                'default_folder_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }

    def action_create_subfolder(self):
        """Quick-create a sub-folder inside this folder."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Sub-folder',
            'res_model': 'construction.project.folder',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_parent_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }

    def action_upload_document(self):
        """Quick-upload a document into this folder."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Upload Document',
            'res_model': 'construction.project.document',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_folder_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }

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
