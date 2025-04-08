odoo.define('s3_storage.kanban_button', function(require) {
    "use strict";
    
    var KanbanController = require('web.KanbanController');
    var KanbanView = require('web.KanbanView');
    var viewRegistry = require('web.view_registry');
    var core = require('web.core');
    
    // Extender el controlador kanban correctamente
    var S3UploadKanbanController = KanbanController.extend({
        events: _.extend({}, KanbanController.prototype.events, {
            'click .s3_upload_wizard_action': '_openS3Wizard',
        }),
        
        /**
         * @override
         */
        renderButtons: function ($node) {
            // Llamar al método original
            this._super.apply(this, arguments);
            
            // Solo agregar el botón si estamos en el modelo correcto
            if (this.modelName === 'ir.attachment' && this.$buttons) {
                var $button = $('<button class="btn btn-primary s3_upload_wizard_action" style="margin-left: 8px;">Cargar Masivamente a S3</button>');
                this.$buttons.find('.o_list_button_add, .o-kanban-button-new').first().after($button);
            }
        },
        
        /**
         * Abrir el wizard al hacer clic en el botón
         * @private
         */
        _openS3Wizard: function () {
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 's3.storage.wizard',
                name: 'Subir Archivos a S3',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: {},
            });
        }
    });
    
    // Registrar la nueva vista kanban
    var S3UploadKanbanView = KanbanView.extend({
        config: _.extend({}, KanbanView.prototype.config, {
            Controller: S3UploadKanbanController,
        }),
    });
    
    // Registrar la vista con el nombre que usamos en el XML
    viewRegistry.add('s3_upload_button_kanban', S3UploadKanbanView);
    
    return {
        S3UploadKanbanController: S3UploadKanbanController,
        S3UploadKanbanView: S3UploadKanbanView,
    };
});