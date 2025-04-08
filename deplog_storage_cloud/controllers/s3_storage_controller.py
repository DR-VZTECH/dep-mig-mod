from odoo import http
from odoo.http import request, Response 
from botocore.exceptions import BotoCoreError, NoCredentialsError
import logging
import requests
import base64
import boto3
import json

_logger = logging.getLogger(__name__)

class S3StorageController(http.Controller):

    @http.route('/s3/proxy/<int:attachment_id>', type='http', auth="public", csrf=False)
    def proxy_s3_pdf(self, attachment_id, **kwargs):
        """ Descarga el archivo desde S3 y lo sirve desde Odoo """
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)

        if not attachment or not attachment.s3_url:
            return request.not_found()

        try:
            # Descargar el archivo desde S3
            response = requests.get(attachment.s3_url, stream=True)
            response.raise_for_status()

            # Devolver el PDF con el mismo Content-Type
            return Response(response.content, content_type="application/pdf", status=200)
        except requests.exceptions.RequestException:
            return request.not_found()
        
    @http.route('/s3/upload', type='http', auth="public", methods=['POST'], csrf=False)
    def upload_to_s3(self, **kwargs):
        """Maneja la carga de archivos en S3."""
        _logger.info("📤 Recibida solicitud de subida a S3 con parámetros: %s", kwargs)

        # Obtener el archivo binario
        file_data = request.httprequest.files.get('file')

        if not file_data:
            _logger.error("❌ Parámetro faltante: 'file'")
            response = request.make_response("Missing parameter: file")
            response.status_code = 400
            return response
        
        checksum = kwargs.get('checksum')
        filename = kwargs.get('filename')
        folder = kwargs.get('folder')

        # Validación de otros parámetros
        if not checksum or not filename or not folder:
            missing_params = [p for p in ['checksum', 'filename', 'folder'] if not kwargs.get(p)]
            _logger.error("❌ Parámetros faltantes: %s", ", ".join(missing_params))
            response = request.make_response(f"Missing parameters: {', '.join(missing_params)}")
            response.status_code = 400
            return response

        # Subir a S3 usando boto3
        try:
            s3_config = request.env['s3.storage.settings'].sudo().search([('is_active', '=', True)], limit=1)
            if not s3_config:
                _logger.error("❌ No hay configuración activa de S3")
                response = request.make_response("No active S3 configuration")
                response.status_code = 500
                return response

            s3_client = boto3.client(
                's3',
                aws_access_key_id=s3_config.aws_access_key,
                aws_secret_access_key=s3_config.aws_secret_key,
                region_name=s3_config.region_name
            )

            # Definir la clave en S3
            s3_key = f"{folder}/{filename}"

            # 🔥 **Corrección**: Leer el contenido del archivo directamente
            s3_client.put_object(
                Bucket=s3_config.bucket_name,
                Key=s3_key,
                Body=file_data.read(),
                ContentType=file_data.content_type
            )

            s3_url = f"https://{s3_config.bucket_name}.s3.{s3_config.region_name}.amazonaws.com/{s3_key}"
            _logger.info("✅ Archivo subido a S3 exitosamente: %s", s3_url)

            response = request.make_response(s3_url)
            response.status_code = 200
            return response

        except Exception as e:
            _logger.error("❌ Error al subir a S3: %s", str(e))
            response = request.make_response("Error uploading to S3")
            response.status_code = 500
            return response

    @http.route('/s3/get_file', type='http', auth='public', methods=['GET'], csrf=False)
    def get_file_from_s3(self, file_key):
        """Obtiene un archivo de S3 basado en su key."""
        s3_client = request.env['s3.storage.settings'].sudo().get_s3_client()
        if not s3_client:
            return "Error: No active S3 configuration found.", 500

        bucket_name = request.env['s3.storage.settings'].sudo().get_active_config().bucket_name

        try:
            _logger.info("🔍 Buscando archivo en S3: %s", file_key)

            # Verificar si el archivo existe en S3
            s3_client.head_object(Bucket=bucket_name, Key=file_key)

            # Generar la URL pública del archivo en S3
            s3_url = f"https://{bucket_name}.s3.{request.env['s3.storage.settings'].sudo().get_active_config().region_name}.amazonaws.com/{file_key}"
            return request.redirect(s3_url)

        except s3_client.exceptions.NoSuchKey:
            _logger.warning("⚠️ Archivo no encontrado en S3: %s", file_key)
            return "Error: File not found in S3.", 404

        except (BotoCoreError, NoCredentialsError) as e:
            _logger.error("❌ Error al obtener archivo de S3: %s", str(e))
            return "Error retrieving file from S3.", 500
        
    @http.route('/s3_storage/status', type='http', auth='public')
    def s3_storage_status(self, **kwargs):
        user = request.env.user
        
        if not user.has_group('base.group_system'):
            return "<h1>Acceso denegado</h1>"
        
        s3_config = request.env['s3.storage.settings'].sudo().search([('is_active', '=', True)], limit=1)
        
        status_data = {
            'configured': False,
            'bucket': '',
            'region': '',
            'statistics': {
                's3_files': 0,
                'total_files': 0,
                's3_percentage': 0
            },
            'message': ''
        }

        if s3_config:
            status_data['configured'] = True
            status_data['bucket'] = s3_config.bucket_name
            status_data['region'] = s3_config.region_name

            attachment_count = request.env['ir.attachment'].sudo().search_count([('store_fname', 'like', 's3://')])
            total_attachments = request.env['ir.attachment'].sudo().search_count([])
            percentage = round((attachment_count / total_attachments) * 100 if total_attachments else 0, 2)
            
            status_data['statistics'] = {
                's3_files': attachment_count,
                'total_files': total_attachments,
                's3_percentage': percentage
            }
        else:
            status_data['message'] = 'S3 Storage no configurado'

        # Renderizar el template con el contexto de los datos de estado
        return request.render('deplog_storage_cloud.s3_status_template', {'status': status_data})

    @http.route('/s3/get_s3_url', type='json', auth='public', methods=['GET'])
    def get_s3_url(self, attachment_id):
        try:
            # Extraer solo el número del attachment_id en caso de que venga con una URL
            match = re.search(r"/web/content/(\d+)", str(attachment_id))
            if match:
                attachment_id = match.group(1)  # Obtener solo el número
    
            _logger.info("📌 ID de documento solicitado: %s", attachment_id)  # Imprimir solo el número
    
            attachment = request.env['ir.attachment'].sudo().browse(int(attachment_id))
            if not attachment.exists():
                return {"error": "❌ Archivo no encontrado en Odoo"}
    
            if not attachment.s3_url:
                return {"error": "⚠️ Archivo no disponible en S3"}
    
            _logger.info("🔄 Devolviendo URL de S3: %s", attachment.s3_url)
            return {"s3_url": attachment.s3_url}
        
        except Exception as e:
            _logger.error("❌ Error en get_s3_url: %s", str(e))
            return {"error": "❌ Error al obtener la URL de S3"}