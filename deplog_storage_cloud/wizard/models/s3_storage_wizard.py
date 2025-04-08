from odoo import models, fields, api
from odoo.exceptions import ValidationError
import boto3
import logging
import base64

_logger = logging.getLogger(__name__)

class S3StorageWizard(models.TransientModel):
    _name = 's3.storage.wizard'
    _description = 'S3 Storage Wizard'
    
    mimetype_filter = fields.Selection([
        ('application/pdf', 'PDF'),
        ('image/png', 'PNG'),
        ('image/jpeg', 'JPEG'),
        ('image/gif', 'GIF'),
        ('application/zip', 'ZIP'),
    ], string="Filtrar por Tipo de Archivo")
    
    # Campos adicionales
    file_count = fields.Integer(string="Archivos detectados", readonly=True)
    total_size_bytes = fields.Integer(string="Bytes", readonly=True)
    total_size_mb = fields.Float(string="Megabytes (MB)", readonly=True, digits=(16, 2))
    total_size_gb = fields.Float(string="Gigabytes (GB)", readonly=True, digits=(16, 4))
    attachment_ids = fields.Many2many('ir.attachment', string="Archivos a subir")
    show_files = fields.Boolean(string="Mostrar lista de archivos", default=False)
    individual_upload = fields.Boolean(string="Carga individual", default=False)
    
    @api.onchange('mimetype_filter')
    def _onchange_mimetype_filter(self):
        """Actualiza el contador de archivos cuando cambia el filtro"""
        if not self.individual_upload and self.mimetype_filter:
            attachments = self.env['ir.attachment'].search([('mimetype', '=', self.mimetype_filter)])
            self.file_count = len(attachments)
            self.attachment_ids = attachments
            
            # Calcular tamaño total en diferentes unidades
            self._calculate_file_sizes()
    
    @api.onchange('attachment_ids')
    def _onchange_attachment_ids(self):
        """Actualiza contador y tamaño cuando cambian los adjuntos"""
        if self.attachment_ids:
            self.file_count = len(self.attachment_ids)
            self._calculate_file_sizes()
    
    def _calculate_file_sizes(self):
        """Calcula el tamaño total de los archivos en diferentes unidades"""
        total_bytes = sum(attachment.file_size for attachment in self.attachment_ids if attachment.file_size)
        self.total_size_bytes = total_bytes
        self.total_size_mb = total_bytes / (1024 * 1024)
        self.total_size_gb = total_bytes / (1024 * 1024 * 1024)
        
    @api.model
    def default_get(self, fields_list):
        res = super(S3StorageWizard, self).default_get(fields_list)
        
        # Si viene de la acción de servidor para carga individual
        if self._context.get('default_attachment_ids'):
            attachment_ids = self._context.get('default_attachment_ids')
            if attachment_ids:
                attachments = self.env['ir.attachment'].browse(attachment_ids)
                res.update({
                    'attachment_ids': [(6, 0, attachments.ids)],
                    'file_count': len(attachments),
                    'individual_upload': True,
                    'show_files': True,
                })
                
                # Calcular tamaño
                total_bytes = sum(attachment.file_size for attachment in attachments if attachment.file_size)
                res.update({
                    'total_size_bytes': total_bytes,
                    'total_size_mb': total_bytes / (1024 * 1024),
                    'total_size_gb': total_bytes / (1024 * 1024 * 1024),
                })
                
                # Si todos los archivos seleccionados tienen el mismo tipo MIME, establecerlo
                if len(set(a.mimetype for a in attachments if a.mimetype)) == 1:
                    mime_type = next((a.mimetype for a in attachments if a.mimetype), False)
                    valid_types = dict(self._fields['mimetype_filter'].selection)
                    if mime_type in valid_types:
                        res['mimetype_filter'] = mime_type
                
        return res
        
    def upload_to_s3(self):
        """Carga archivos a S3 (masiva o individual)"""
        # Obtener la configuración activa de S3
        s3_settings = self.env['s3.storage.settings'].get_active_config()
        if not s3_settings:
            raise ValidationError("No hay configuración activa para S3")
        
        # Obtener el cliente S3
        client = s3_settings.get_s3_client()
        if not client:
            raise ValidationError("No se pudo establecer conexión con S3")
        
        # Determinar qué archivos procesar
        if self.individual_upload:
            # Usar los archivos ya seleccionados
            attachments = self.attachment_ids
        else:
            # Buscar adjuntos por filtro MIME
            attachments = self.env['ir.attachment'].search([('mimetype', '=', self.mimetype_filter)])
        
        # Si no hay archivos para procesar
        if not attachments:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No hay archivos',
                    'message': 'No se encontraron archivos para procesar.',
                    'type': 'warning',
                    'sticky': False
                }
            }
    
        # Contador para estadísticas
        uploaded_count = 0
        error_count = 0
        skipped_count = 0
        total_size_uploaded = 0
        
        # Cargar los archivos a S3
        for attachment in attachments:
            try:
                # Verificar si el archivo tiene datos antes de intentar cargarlo
                if not attachment.datas:
                    _logger.warning(f"⚠️ El archivo {attachment.name} no tiene datos y será ignorado.")
                    skipped_count += 1
                    continue
                
                # Asegurar que tenemos un store_fname, si no, usar una combinación de id y nombre
                if attachment.store_fname:
                    key = attachment.store_fname
                else:
                    # Sanitizar el nombre para usarlo como clave en S3
                    import re
                    sanitized_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', attachment.name)
                    key = f"{attachment.id}_{sanitized_name}"
                
                # Decodificar los datos en base64
                file_content = base64.b64decode(attachment.datas)
                
                # Subir el archivo a S3
                _logger.info(f"📤 Subiendo archivo a S3: {attachment.name}")
                client.put_object(
                    Bucket=s3_settings.bucket_name,
                    Key=key,
                    Body=file_content,
                    ContentType=attachment.mimetype or 'application/octet-stream'
                )
                
                # Actualizar la URL del archivo en Odoo
                s3_url = f"https://{s3_settings.bucket_name}.s3.{s3_settings.region_name}.amazonaws.com/{key}"
                attachment.write({
                    'url': s3_url,
                    'type': 'url',  # Cambiar el tipo a URL
                })
                
                # Actualizar estadísticas
                uploaded_count += 1
                if attachment.file_size:
                    total_size_uploaded += attachment.file_size
                    
                _logger.info(f"✅ Archivo subido correctamente: {s3_url}")
                
            except Exception as e:
                # Log de errores si falla la subida
                _logger.error(f"❌ Error subiendo {attachment.name} a S3: {str(e)}")
                error_count += 1
        
        # Formatear el tamaño total subido
        if total_size_uploaded < 1024:
            size_display = f"{total_size_uploaded} bytes"
        elif total_size_uploaded < 1024 * 1024:
            size_display = f"{total_size_uploaded / 1024:.2f} KB"
        elif total_size_uploaded < 1024 * 1024 * 1024:
            size_display = f"{total_size_uploaded / (1024 * 1024):.2f} MB"
        else:
            size_display = f"{total_size_uploaded / (1024 * 1024 * 1024):.2f} GB"
        
        # Mensaje detallado con las estadísticas
        message = f"""
        Carga a S3 completada:
        - {uploaded_count} archivos subidos exitosamente
        - {error_count} errores
        - {skipped_count} archivos omitidos (sin datos)
        - Tamaño total subido: {size_display}
        """
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Carga Completada',
                'message': message.strip(),
                'type': 'success',
                'sticky': True  # Hacerlo sticky para que el usuario pueda leer el resumen
            }
        }