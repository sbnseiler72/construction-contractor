# -*- coding: utf-8 -*-
from odoo import models, fields, api


# File type detection maps (shared with construction_project_document.py)
IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'tiff'}
DOC_EXTS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'odt'}
PLAN_EXTS = {'dwg', 'dxf', 'dwf'}

FILE_TYPE_SELECTION = [
    ('image', 'Image'),
    ('document', 'Document'),
    ('plan', 'Plan / Drawing'),
    ('permit', 'Permit'),
    ('report', 'Report'),
    ('other', 'Other'),
]


def _detect_file_type(filename):
    """Detect file type from filename extension."""
    if not filename or '.' not in filename:
        return 'other'
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext in IMAGE_EXTS:
        return 'image'
    elif ext in DOC_EXTS:
        return 'document'
    elif ext in PLAN_EXTS:
        return 'plan'
    return 'other'


class DocumentUploadWizard(models.TransientModel):
    _name = 'construction.document.upload.wizard'
    _description = 'Multi-File Upload Wizard'

    folder_id = fields.Many2one(
        'construction.project.folder',
        string='Folder',
        required=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        'construction.project',
        string='Project',
        required=True,
        readonly=True,
    )
    phase_id = fields.Many2one(
        'construction.project.phase',
        string='Phase (apply to all)',
    )
    tag_ids = fields.Many2many(
        'construction.document.tag',
        string='Tags (apply to all)',
    )
    line_ids = fields.One2many(
        'construction.document.upload.line',
        'wizard_id',
        string='Files',
    )

    def action_upload(self):
        """Create project documents from all upload lines."""
        self.ensure_one()
        Document = self.env['construction.project.document']
        created = Document
        for line in self.line_ids:
            if not line.file:
                continue
            vals = {
                'name': line.name or line.file_name or 'Untitled',
                'file': line.file,
                'file_name': line.file_name,
                'file_type': line.file_type or 'other',
                'folder_id': self.folder_id.id,
                'project_id': self.project_id.id,
            }
            if self.phase_id:
                vals['phase_id'] = self.phase_id.id
            if self.tag_ids:
                vals['tag_ids'] = [(6, 0, self.tag_ids.ids)]
            created |= Document.create(vals)
        return {'type': 'ir.actions.act_window_close'}


class DocumentUploadLine(models.TransientModel):
    _name = 'construction.document.upload.line'
    _description = 'Upload Wizard Line'

    wizard_id = fields.Many2one(
        'construction.document.upload.wizard',
        required=True,
        ondelete='cascade',
    )
    file = fields.Binary(string='File', required=True)
    file_name = fields.Char(string='File Name')
    name = fields.Char(string='Document Name')
    file_type = fields.Selection(
        FILE_TYPE_SELECTION,
        string='Type',
        default='other',
    )

    @api.onchange('file_name')
    def _onchange_file_name(self):
        if self.file_name:
            self.file_type = _detect_file_type(self.file_name)
            if not self.name:
                self.name = self.file_name.rsplit('.', 1)[0] if '.' in self.file_name else self.file_name
