# -*- coding: utf-8 -*-
from odoo import fields, api, models, _
import logging

logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'binary.attachment.mixin']
    
    # No es necesario redefinir los campos del mixin
    # ya que se heredarán automáticamente
    
    def action_view_attachments(self):
        """ Acción para abrir la vista de documentos adjuntos """
        self.ensure_one()
        return {
            'name': _("Documentos Adjuntos"),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'tree,form',
            'domain': [
                ('res_model', '=', 'res.partner'), 
                ('res_id', '=', self.id),
                '|', ('type', '=', 'binary'), ('type', '=', 'url')  # Incluir tanto binarios como URLs
            ],
            'context': {
                'default_res_model': 'res.partner', 
                'default_res_id': self.id,
                'create': True,
                'edit': True,
                'delete': True
            }
        }
    
    # Método opcional para forzar la sincronización de adjuntos S3
    def sync_s3_attachments(self):
        """Sincroniza adjuntos de S3 para este partner"""
        self.ensure_one()
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.id),
            ('type', '=', 'url'),
            ('url', 'like', '%.s3.amazonaws.com/%')
        ])
        
        # Asegúrate de que todos tengan el campo s3_url actualizado
        for attachment in attachments:
            if not attachment.s3_url and attachment.url:
                attachment.s3_url = attachment.url
                logger.info(f"Actualizado s3_url para adjunto {attachment.name}")
        
        return True