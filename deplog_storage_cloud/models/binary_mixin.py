# -*- coding: utf-8 -*-
# models/binary_attachment_mixin.py

from odoo import models, fields, api
import logging

logger = logging.getLogger(__name__)

class BinaryAttachmentMixin(models.AbstractModel):
    _name = 'binary.attachment.mixin'
    _description = 'Mixin para adjuntar archivos sin perder los Binary Fields'
    
    attachment_ids = fields.One2many(
        'ir.attachment',
        'res_id',
        string="Documentos adjuntos",
        domain=lambda self: [('res_model', '=', self._name)],
        context={'default_res_model': 'res.partner'}
    )
    
    attachment_count = fields.Integer(
        string="Documentos",
        compute='_compute_attachment_count'
    )
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)
    
    def _is_model_allowed(self):
        """ Verifica si el modelo actual está en la lista de permitidos. """
        allowed_models = self.env['ir.config_parameter'].sudo().get_param('storage.allowed_models', '')
        if not allowed_models:
            return True  # Si no hay configuración, permitir todos
        return self._name in allowed_models.split(',')
    
    def _get_binary_fields(self):
        """ Obtiene todos los campos binarios del modelo actual. """
        if not self._is_model_allowed():
            return []
        return [field for field, info in self._fields.items() if info.type == 'binary']
    
    @api.model_create_multi
    def create(self, vals_list):
        """ Intercepta la creación para procesar campos binarios. """
        records = super(BinaryAttachmentMixin, self).create(vals_list)
        
        # Procesa los campos binarios para crear adjuntos
        for record in records:
            binary_fields = record._get_binary_fields()
            for field in binary_fields:
                if hasattr(record, field) and getattr(record, field):
                    binary_value = getattr(record, field)
                    
                    # Obtener un nombre más descriptivo si es posible
                    field_info = record._fields.get(field)
                    field_string = field_info.string if field_info else field
                    file_name = f"{field_string}_{record.id}"
                    
                    # Crear el adjunto SIN modificar el campo original
                    attachment_vals = {
                        'name': file_name,
                        'res_model': record._name,
                        'res_id': record.id,
                        'type': 'binary',
                        'datas': binary_value,
                    }
                    self.env['ir.attachment'].create(attachment_vals)
                    logger.info(f"Adjunto creado para el campo {field} del registro {record.id}")
        
        return records
    
    def write(self, vals):
        """ Intercepta la escritura para procesar campos binarios. """
        # Guarda los valores binarios que se van a actualizar
        binary_fields = self._get_binary_fields()
        files_to_attach = {}
        
        for field in binary_fields:
            if field in vals and vals[field]:
                files_to_attach[field] = vals[field]
        
        # Hace la escritura normal sin modificar nada
        result = super(BinaryAttachmentMixin, self).write(vals)
        
        # Ahora procesa los campos binarios que se actualizaron para crear adjuntos
        for field, binary_value in files_to_attach.items():
            for record in self:
                # Obtener un nombre más descriptivo si es posible
                field_info = record._fields.get(field)
                field_string = field_info.string if field_info else field
                file_name = f"{field_string}_{record.id}"
                
                # Crear el adjunto SIN modificar el campo original
                attachment_vals = {
                    'name': file_name,
                    'res_model': record._name,
                    'res_id': record.id,
                    'type': 'binary',
                    'datas': binary_value,
                }
                self.env['ir.attachment'].create(attachment_vals)
                logger.info(f"Nuevo adjunto creado para {field} en {record.display_name or record.id}")
        
        return result