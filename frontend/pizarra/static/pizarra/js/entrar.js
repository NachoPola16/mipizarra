/* Pantalla de entrada: mostrar u ocultar la contraseña. */
(function () {
    var campo = document.getElementById('id_password'), boton = document.getElementById('ver-clave');
    if (!campo || !boton) return;
    boton.addEventListener('click', function () {
        var visible = campo.type === 'password';
        campo.type = visible ? 'text' : 'password';
        boton.textContent = visible ? 'Ocultar' : 'Mostrar';
        boton.setAttribute('aria-pressed', visible ? 'true' : 'false');
        campo.focus();
    });
})();
