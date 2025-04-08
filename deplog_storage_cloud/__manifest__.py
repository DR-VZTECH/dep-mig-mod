{
    'name': "S3 Storage Integration",
    'summary': "Store Odoo attachments in AWS S3",
    'description': """
        This module integrates Odoo with Amazon S3 to store
        all uploaded files automatically in S3 buckets
    """,
    'author': "DFVZ Tech",
    'coauthor': "Dayron Romero",
    'website': "https://www.vztech.odoo.com",
    'category': 'Technical',
    'version': '1.0',
    'depends': ['base', 'mail', 'website'],
    'data': [
        'security/ir_model_access.xml',
        'views/s3_storage_views.xml',
        'views/res_partner_views.xml',
        'wizard/views/s3_storage_wizard_views.xml',
        'templates/s3_status_template.xml',
        'data/ir_actions_server.xml',
    ],
    'demo': [
        'data/s3_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'deplog_storage_cloud/static/src/js/pdfjs/pdf_viewer_override.js',
            'deplog_storage_cloud/static/src/js/upload_button/s3_upload_button.js',
        ],
        'web.pdf_viewer_assets': [
            'deplog_storage_cloud/static/src/js/pdfjs/pdf_viewer_override.js',
        ],
        'web.assets_qweb': [
            'deplog_storage_cloud/static/src/xml/s3_upload_button.xml',
        ],
    },
    'external_dependencies': {
        'python': ['boto3'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}