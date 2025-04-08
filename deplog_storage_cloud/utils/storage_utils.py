import re

def normalize_filename(filename):
    """Convierte el nombre del archivo a un formato seguro para S3 y Odoo."""
    filename = filename.lower().strip()
    filename = re.sub(r'[^a-z0-9_.-]', '_', filename)  # Reemplaza caracteres especiales
    return filename

def generate_s3_key(checksum, filename):
    """Genera la ruta esperada por Odoo para almacenamiento en S3."""
    sub_folder = checksum[:2]  # Extrae los primeros dos caracteres del checksum
    return f"files/{sub_folder}/{checksum}/{filename}"

def get_mimetype_from_filename(filename):
    """Determina el MIME type basado en la extensión del archivo"""
    extension_map = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.txt': 'text/plain',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.zip': 'application/zip',
        '.csv': 'text/csv'
    }
    
    ext = filename.lower().split('.')[-1]
    return extension_map.get(f".{ext}", 'application/octet-stream')
