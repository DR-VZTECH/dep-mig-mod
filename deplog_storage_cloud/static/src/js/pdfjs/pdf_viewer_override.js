odoo.define('deplog_storage_cloud.pdf_viewer_override', function (require) {
    "use strict";
    var core = require('web.core');
    var ajax = require('web.ajax');
    console.log("✅ Viewer.js personalizado cargado en Odoo!");
    
    function checkS3FileExists(proxyUrl) {
        return new Promise(function(resolve) {
            // Hacer una petición HEAD para verificar si el archivo existe en S3
            fetch(proxyUrl, {
                method: 'HEAD'
            })
            .then(function(response) {
                // Resolver con true si existe (código 200), false en caso contrario
                resolve(response.ok);
            })
            .catch(function() {
                // En caso de error, asumir que no existe
                resolve(false);
            });
        });
    }

    async function updatePdfViewer() {
        console.log("🔄 Buscando iframe del visor de PDF...");
        const pdfIframe = document.querySelector("iframe[src*='/web/static/lib/pdfjs/web/viewer.html']");
        if (!pdfIframe) {
            console.warn("⚠️ No se encontró el iframe del visor de PDF.");
            return;
        }
        console.log("✅ Visor encontrado:", pdfIframe);
        
        const urlParams = new URL(pdfIframe.src).searchParams;
        const fileParam = urlParams.get("file");
        if (!fileParam) {
            console.warn("⚠️ No se encontró el parámetro 'file' en la URL.");
            return;
        }
        
        // Verificar si ya estamos usando la URL del proxy o la URL nativa
        if (fileParam.includes('/s3/proxy/')) {
            console.log("🔍 Ya estamos usando la URL del proxy S3:", fileParam);
            return;
        }
        
        console.log("🔍 URL original detectada:", fileParam);
        if (fileParam.includes('/web/content/')) {
            const match = fileParam.match(/\/web\/content\/(\d+)/);
            if (match) {
                const attachmentId = match[1];
                console.log("📌 ID del documento detectado:", attachmentId);
                
                // Generar la URL del proxy
                const proxyUrl = `/s3/proxy/${attachmentId}`;
                console.log("📄 URL del proxy generada:", proxyUrl);
                
                // Verificar si el archivo existe en S3
                const fileExistsInS3 = await checkS3FileExists(proxyUrl);
                
                if (fileExistsInS3) {
                    console.log("✅ Archivo encontrado en S3, usando URL del proxy");
                    // Actualizar a la URL del proxy S3
                    const newViewerUrl = `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(proxyUrl)}#pagemode=none`;
                    console.log("🔄 Actualizando visor con URL de S3:", newViewerUrl);
                    pdfIframe.src = newViewerUrl;
                } else {
                    console.log("⚠️ Archivo no encontrado en S3, manteniendo URL nativa de Odoo");
                    // Mantener la URL original (filestore de Odoo)
                    // No hacemos nada, dejamos que use la URL original
                }
            }
        }
    }
    
    // Inicializar una sola vez al cargar
    document.addEventListener('DOMContentLoaded', function() {
        // Primera ejecución después de un breve retraso
        setTimeout(updatePdfViewer, 500);
        
        // Observar cambios en el DOM para detectar cuando se inserta un nuevo visor de PDF
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes && mutation.addedNodes.length > 0) {
                    // Verificar si alguno de los nodos añadidos es un iframe o contiene un iframe
                    for (let i = 0; i < mutation.addedNodes.length; i++) {
                        const node = mutation.addedNodes[i];
                        if (node.nodeType === 1) { // Elemento
                            if (node.tagName === 'IFRAME' && node.src && node.src.includes('/web/static/lib/pdfjs/web/viewer.html')) {
                                // Se ha añadido un iframe de PDF
                                setTimeout(updatePdfViewer, 100);
                            } else if (node.querySelector && node.querySelector("iframe[src*='/web/static/lib/pdfjs/web/viewer.html']")) {
                                // Se ha añadido un contenedor que contiene un iframe de PDF
                                setTimeout(updatePdfViewer, 100);
                            }
                        }
                    }
                }
            });
        });
        
        // Observar todo el documento para cambios
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    });
});