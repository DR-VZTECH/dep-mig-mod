from odoo import models, api, fields
import requests
import logging
import os

_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = "ir.attachment"
    
    s3_url = fields.Char("S3 URL", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        """Intercepta la creación de archivos y los sube a S3 manteniendo indicador visual."""
        records = super(IrAttachment, self).create(vals_list)
        
        for record in records:
            if record.store_fname and not record.store_fname.startswith('s3://') and not record._is_web_asset():
                try:
                    bin_data = record._file_read(record.store_fname)
                    s3_config = self._get_s3_settings_safe()
                    if s3_config:
                        s3_key = record._file_upload_to_s3(bin_data, record)
                        if s3_key:
                            # Guarda la URL de S3
                            s3_url = f"https://{s3_config.bucket_name}.s3.{s3_config.region_name}.amazonaws.com/{s3_key}"
                            
                            # Si es un campo binario en res.partner, mantén un archivo ficticio
                            if record.res_model == 'res.partner' and record.res_field:
                                # Crear un pequeño archivo ficticio como indicador visual (1x1 pixel transparente)
                                dummy_file = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
                                
                                # Guarda la URL de S3 pero no elimines el archivo local
                                record.write({
                                    'datas': dummy_file,  # Archivo GIF 1x1 transparente
                                    's3_url': s3_url
                                })
                                _logger.info("👁️ Manteniendo indicador visual para %s y guardando en S3", record.res_field)
                            else:
                                # Comportamiento normal para los demás archivos
                                record.write({
                                    'store_fname': f"s3://{s3_key}",
                                    's3_url': s3_url
                                })
                                record._delete_local_file()
                except Exception as e:
                    _logger.error("❌ Error al subir archivo a S3: %s", str(e))
        
        return records

    def _file_upload_to_s3(self, bin_data, record):
        """Sube un archivo directamente a S3 usando boto3"""
        s3_config = self._get_s3_settings_safe()
        if not s3_config:
            _logger.error("❌ No hay configuración S3 activa")
            return False
        
        try:
            import boto3
            from botocore.config import Config
            
            # Obtener credenciales directamente
            access_key = s3_config.aws_access_key.strip()
            secret_key = s3_config.aws_secret_key.strip()
            region_name = s3_config.region_name.strip()
            bucket_name = s3_config.bucket_name.strip()
            
            # Crear config boto3
            boto_config = Config(
                signature_version='s3v4',
                s3={'addressing_style': 'virtual'}
            )
            
            # Crear cliente boto3 directamente
            s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region_name,
                config=boto_config
            )
            
            # Preparar datos del archivo
            filename = self._normalize_filename(record.name or 'unnamed_file')
            folder = self._generate_odoo_path(record.checksum)
            s3_key = f"{folder}/{filename}"
            
            # Determinar MIME type
            mimetype = record.mimetype or 'application/octet-stream'
            
            _logger.info("📤 Subiendo archivo a S3: %s (bucket=%s, key=%s)", 
                        filename, bucket_name, s3_key)
            
            # Subir a S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=bin_data,
                ContentType=mimetype
            )
            
            s3_url = f"https://{bucket_name}.s3.{region_name}.amazonaws.com/{s3_key}"
            _logger.info("✅ Archivo subido exitosamente: %s", s3_url)
            
            return s3_key
        except Exception as e:
            import traceback
            _logger.error("❌ Error al subir archivo a S3: %s\n%s", 
                         str(e), traceback.format_exc())
            return False

    def _file_read(self, fname):
        """Verifica si el archivo está en S3 antes de devolverlo."""
        if not fname or not fname.startswith('s3://'):
            return super()._file_read(fname)

        s3_key = fname[5:]
        s3_config = self._get_s3_settings_safe()
        if not s3_config:
            _logger.error("❌ No hay configuración S3 activa")
            return False
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=s3_config.aws_access_key.strip(),
                aws_secret_access_key=s3_config.aws_secret_key.strip(),
                region_name=s3_config.region_name.strip()
            )
            response = s3_client.get_object(Bucket=s3_config.bucket_name.strip(), Key=s3_key)
            return response['Body'].read()
        except Exception as e:
            _logger.error("❌ Error al leer archivo de S3: %s", str(e))
            return False
                
    def _delete_local_file(self):
        """Elimina el archivo local después de subirlo a S3."""
        for attachment in self:
            if attachment.store_fname and not attachment.store_fname.startswith('s3://'):
                local_path = self._full_path(attachment.store_fname)
                try:
                    if os.path.exists(local_path):
                        os.unlink(local_path)
                        _logger.info("🗑️ Archivo local eliminado: %s", local_path)
                except Exception as e:
                    _logger.error("❌ Error eliminando archivo local: %s", str(e))
                    
    def _get_s3_settings_safe(self):
        """Obtiene la configuración activa de S3 de manera segura."""
        try:
            return self.env['s3.storage.settings'].search([('is_active', '=', True)], limit=1)
        except Exception as e:
            _logger.error("❌ Error al obtener configuración de S3: %s", str(e))
            return False

    def _generate_odoo_path(self, checksum):
        """Genera la estructura de carpetas que Odoo espera en S3."""
        return f"files/{checksum[:2]}/{checksum}"

    def _normalize_filename(self, filename):
        """Convierte nombres de archivos en un formato seguro para S3."""
        import re
        filename = filename.lower().strip()
        return re.sub(r'[^a-z0-9_.-]', '_', filename)

    def _is_web_asset(self):
        self.ensure_one()

        url = self.url or ""  # Evita que self.url sea None
        name = self.name or ""  # Evita que self.name sea None

        # 1. Verificar URL
        if any(pattern in url for pattern in [
            '/web/assets/', '/web/static/', '/web/content/', 
            '.js', '.css', '.scss', 'web_editor', 'assets_'
        ]):
            return True

        # 2. Verificar nombre del archivo
        if any(pattern in name for pattern in [
            '.js', '.css', '.scss', 'web.assets_', 'assets_common',
            'assets_backend', 'assets_frontend'
        ]):
            return True

        # 3. Verificar modelo relacionado
        if self.res_model in ['ir.ui.view', 'ir.qweb', 'web_editor.assets']:
            return True

        # 4. Verificar MIME type
        if self.mimetype in ['text/css', 'text/javascript', 'application/javascript']:
            return True

        return False

    def _get_attachment_url(self):
        """Si el archivo está en S3, devuelve la URL de S3."""
        self.ensure_one()

        if self.s3_url:
            _logger.info("🔄 Devolviendo URL de S3: %s", self.s3_url)
            return self.s3_url

        return super()._get_attachment_url()

    def _get_public_url(self):
        """Devuelve la URL de S3 si existe, en lugar de la de Odoo."""
        self.ensure_one()
        if self.s3_url:
            _logger.info("🔄 Forzando URL de S3 en `_get_public_url`: %s", self.s3_url)
            return self.s3_url
        return super()._get_public_url()
        