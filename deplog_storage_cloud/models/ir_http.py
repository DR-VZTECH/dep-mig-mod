from odoo import models
import logging

_logger = logging.getLogger(__name__)

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'
    
    @classmethod
    def _get_file_response(cls, id, field='datas', share_id=None, share_token=None, 
                          download=None, unique=None, filename_field='name', mimetype=None):
        """Método simplificado para redirigir a S3 cuando sea necesario"""
        env = cls.sudo().env if share_id or share_token else cls.env
        record = env['ir.attachment'].browse(int(id))
        
        # Si es un archivo S3 con URL, redirigir directamente
        if record.store_fname and record.store_fname.startswith('s3://') and record.s3_url:
            _logger.info("↪️ Redirigiendo a S3: %s", record.s3_url)
            return cls.redirect_to_url(record.s3_url)
        
        return super()._get_file_response(id, field=field, share_id=share_id, 
                                         share_token=share_token, download=download, 
                                         unique=unique, filename_field=filename_field, 
                                         mimetype=mimetype)