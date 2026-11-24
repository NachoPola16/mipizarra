/* Registra el service worker mínimo (sin caché) para poder instalar MiPizarra como app. */
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
        navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
}
