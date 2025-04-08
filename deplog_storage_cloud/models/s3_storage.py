from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import boto3
import logging

_logger = logging.getLogger(__name__)

class S3StorageSettings(models.Model):
    _name = 's3.storage.settings'
    _description = 'S3 Storage Settings'

    name = fields.Char('Configuration Name', required=True)
    aws_access_key = fields.Char('AWS Access Key', required=True)
    aws_secret_key = fields.Char('AWS Secret Key', required=True, groups="base.group_system")
    bucket_name = fields.Char('S3 Bucket Name', required=True)
    region_name = fields.Char('AWS Region', required=True, default='us-east-1')
    is_active = fields.Boolean('Is Active', default=False)

    @api.model
    def get_active_config(self):
        """Obtiene la configuración activa de S3"""
        return self.search([('is_active', '=', True)], limit=1)

    def get_s3_client(self):
        """Devuelve un cliente S3 configurado correctamente"""
        config = self.get_active_config()
        if not config:
            _logger.error("No active S3 configuration found.")
            return None
        
        try:
            # Obtener y limpiar credenciales
            access_key = config.aws_access_key.strip()
            secret_key = config.aws_secret_key.strip()
            region_name = config.region_name.strip()
            
            # Crear config boto3
            from botocore.config import Config
            boto_config = Config(
                signature_version='s3v4',
                s3={'addressing_style': 'virtual'}
            )
            
            # Crear cliente con credenciales explícitas
            client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region_name,
                config=boto_config
            )
            
            return client
        except Exception as e:
            _logger.error("Error creating S3 client: %s", str(e))
            return None

    @api.constrains('is_active')
    def _check_active_uniqueness(self):
        """Solo una configuración puede estar activa a la vez. Si activamos una, desactivamos las demás."""
        for record in self:
            if record.is_active:
                self.search([('id', '!=', record.id)]).write({'is_active': False})

    def test_connection(self):
        """Prueba la conexión con S3"""
        try:
            # Limpiar posibles espacios en blanco
            access_key = self.aws_access_key.strip()
            secret_key = self.aws_secret_key.strip()
            region_name = self.region_name.strip()
            bucket_name = self.bucket_name.strip()
            
            # Crear cliente directamente para esta prueba
            s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region_name
            )
            
            # Verifica si el bucket existe
            s3_client.head_bucket(Bucket=bucket_name)
            
            # Intentar una operación de escritura simple
            test_key = f"test_connection_{self.id}.txt"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=b"Test connection from Odoo",
                ContentType="text/plain"
            )
            
            # Si llegamos hasta aquí, todo está funcionando
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Successfully connected to S3 bucket and wrote test file!'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error("S3 connection test failed: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Connection test failed: %s') % str(e),
                    'sticky': False,
                    'type': 'danger',
                }
            }