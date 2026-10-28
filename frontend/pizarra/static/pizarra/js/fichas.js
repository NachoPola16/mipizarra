// Pestaña «Fichas» (solo administrador): lista, filtros y editor de una ficha cada vez. Todo el texto entra con
// textContent / value: nada de innerHTML (el diagrama lo gestiona fichas_diagrama.js).
(function () {
    'use strict';
    var $ = function (id) { return document.getElementById(id); };
    var URL_DATOS = document.body.getAttribute('data-url-datos');
    var URL_FICHA = document.body.getAttribute('data-url-ficha');
    var URL_VISTA = document.body.getAttribute('data-url-vista');
    var editorDiagrama = null;   // se crea la primera vez que se abre una ficha
    var CATEGORIAS = ['juego_equipo', '1c1', 'ventaja_numerica', 'calentamiento', 'tiro', 'fisico', 'bloqueo_directo', 'bloqueo_indirecto'];
    var ESPACIOS = ['media_pista', 'pista_completa', 'flexible'];
    var EDADES = ['U8', 'U10', 'U12', 'U14', 'U16', 'U18', 'Senior'];

    var fichas = [];          // todas, con los cambios aplicados
    var modificadas = {};     // id → true
    var visibles = [];        // las que pasan el filtro
    var actual = null;        // ficha abierta
    var instantanea = '';     // estado del formulario al abrir/guardar, para saber si hay cambios
    var campos = {};          // nombre de campo → función que lee su valor
    var confirmaRestaurar = false;

    function csrf() { var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/); return m ? decodeURIComponent(m[1]) : ''; }
    function api(url, opciones) {
        opciones = opciones || {};
        opciones.credentials = 'same-origin';
        opciones.headers = Object.assign({ 'X-CSRFToken': csrf() }, opciones.headers || {});
        return fetch(url, opciones).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (cuerpo) { return { ok: r.ok, status: r.status, cuerpo: cuerpo }; });
        });
    }
    function el(tag, clase, texto) {
        var e = document.createElement(tag);
        if (clase) e.className = clase;
        if (texto != null) e.textContent = texto;
        return e;
    }
    function estado(t) { $('fi-estado').textContent = t || ''; }

    // ── Lista y filtros ──────────────────────────────────────────────────────
    function norm(t) { return String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
    function textoDe(f) {
        return norm([f.id, f.nombre, f.categoria, f.subcategoria, f.descripcion, (f.puntos_clave || []).join(' ')].join(' '));
    }
    function filtra() {
        var q = norm($('fi-buscar').value.trim()), edad = $('fi-edad').value, cat = $('fi-cat').value, solo = $('fi-mod').checked;
        visibles = fichas.filter(function (f) {
            return (!q || textoDe(f).indexOf(q) >= 0) && (!edad || (f.edades || []).indexOf(edad) >= 0) &&
                (!cat || f.categoria === cat) && (!solo || modificadas[f.id]);
        });
        pintaLista();
    }
    function pintaLista() {
        var ul = $('fi-ul'); ul.textContent = '';
        visibles.forEach(function (f) {
            var li = el('li'), b = el('button'), meta;
            b.type = 'button';
            b.appendChild(el('span', 'fi-l-id', f.id));
            b.appendChild(document.createTextNode(f.nombre));
            if (modificadas[f.id]) b.appendChild(el('span', 'fi-l-mod', '● modificada'));
            meta = el('span', 'fi-l-meta', (f.edades || []).join(' ') + ' · ' + f.categoria + ' · ' + f.duracion_min + ' min');
            b.appendChild(meta);
            if (actual && actual.id === f.id) b.setAttribute('aria-current', 'true');
            b.addEventListener('click', function () { abre(f.id); });
            li.appendChild(b); ul.appendChild(li);
        });
        ul.setAttribute('aria-busy', 'false');
        $('fi-cuenta').textContent = visibles.length + ' de ' + fichas.length + ' fichas';
        posicion();
    }
    function posicion() {
        var i = actual ? visibles.findIndex(function (f) { return f.id === actual.id; }) : -1;
        $('fi-pos').textContent = i >= 0 ? (i + 1) + ' / ' + visibles.length : '';
        $('fi-ant').disabled = i <= 0;
        $('fi-sig').disabled = i < 0 || i >= visibles.length - 1;
    }

    // ── Formulario ───────────────────────────────────────────────────────────
    function campo(titulo, ayuda, control, nombre, lector) {
        var d = el('div', 'fi-campo'), l = el('label', null, titulo);
        if (control.id) l.setAttribute('for', control.id);
        if (ayuda) l.appendChild(el('span', 'fi-ayuda', ayuda));
        d.appendChild(l); d.appendChild(control);
        campos[nombre] = lector;
        return d;
    }
    function texto(id, valor) { var i = el('input'); i.type = 'text'; i.id = id; i.value = valor == null ? '' : valor; return i; }
    function numero(id, valor) { var i = el('input'); i.type = 'number'; i.id = id; i.step = '1'; i.value = valor == null ? '' : valor; return i; }
    function area(id, valor, alta) { var t = el('textarea', alta ? 'fi-alto' : ''); t.id = id; t.value = valor == null ? '' : valor; return t; }
    function selector(id, opciones, valor) {
        var s = el('select'); s.id = id;
        var lista = opciones.indexOf(valor) < 0 && valor ? opciones.concat([valor]) : opciones;
        lista.forEach(function (o) { var op = el('option', null, o); op.value = o; s.appendChild(op); });
        s.value = valor; return s;
    }
    function lineas(t) { return t.value.split('\n').map(function (x) { return x.trim(); }).filter(Boolean); }
    function entero(i) { var v = i.value.trim(); return v === '' ? '' : (/^-?\d+$/.test(v) ? parseInt(v, 10) : v); }

    function construye(f) {
        var cont = $('fi-campos'); cont.textContent = ''; campos = {};
        var o = f.objetivos || {}, p = f.progresion || {};
        var c;
        cont.appendChild(campo('Nombre', '', c = texto('c-nombre', f.nombre), 'nombre', function () { return c.value; }));
        var fila = el('div', 'fi-fila'), cat, esp, sub;
        fila.appendChild(campo('Categoría', '', cat = selector('c-categoria', CATEGORIAS, f.categoria), 'categoria', function () { return cat.value; }));
        fila.appendChild(campo('Subcategoría', '', sub = texto('c-subcategoria', f.subcategoria), 'subcategoria', function () { return sub.value.trim(); }));
        fila.appendChild(campo('Espacio', '', esp = selector('c-espacio', ESPACIOS, f.espacio), 'espacio', function () { return esp.value; }));
        cont.appendChild(fila);

        var ed = el('div', 'fi-campo'), edL = el('span', 'fi-et', 'Edades'), caja = el('div', 'fi-edades'), marcas = [];
        EDADES.forEach(function (e) {
            var l = el('label'), i = el('input'); i.type = 'checkbox'; i.value = e; i.checked = (f.edades || []).indexOf(e) >= 0;
            l.appendChild(i); l.appendChild(document.createTextNode(e)); caja.appendChild(l); marcas.push(i);
        });
        ed.appendChild(edL); ed.appendChild(caja); cont.appendChild(ed);
        campos.edades = function () { return marcas.filter(function (i) { return i.checked; }).map(function (i) { return i.value; }); };

        var nums = el('div', 'fi-fila'), d, it, cg, jm;
        nums.appendChild(campo('Duración (min)', '5–30', d = numero('c-dur', f.duracion_min), 'duracion_min', function () { return entero(d); }));
        nums.appendChild(campo('Intensidad', '1–5', it = numero('c-int', f.intensidad), 'intensidad', function () { return entero(it); }));
        nums.appendChild(campo('Carga cognitiva', '1–5', cg = numero('c-carga', f.carga_cognitiva), 'carga_cognitiva', function () { return entero(cg); }));
        nums.appendChild(campo('Jugadores mínimos', '', jm = numero('c-jug', f.jugadores_minimos), 'jugadores_minimos', function () { return entero(jm); }));
        cont.appendChild(nums);

        var ob = el('div', 'fi-fila'), ta, te, fi;
        ob.appendChild(campo('Objetivos tácticos', 'uno por línea', ta = area('c-tac', (o.tacticos || []).join('\n')), 'o_tacticos', function () { return lineas(ta); }));
        ob.appendChild(campo('Objetivos técnicos', 'uno por línea', te = area('c-tec', (o.tecnicos || []).join('\n')), 'o_tecnicos', function () { return lineas(te); }));
        ob.appendChild(campo('Objetivos físicos', 'uno por línea', fi = area('c-fis', (o.fisicos || []).join('\n')), 'o_fisicos', function () { return lineas(fi); }));
        cont.appendChild(ob);

        var de, pc, ma, co, er, qo, pf, pd;
        cont.appendChild(campo('Descripción', 'organización, secuencia, rotación, progresión', de = area('c-desc', f.descripcion, true), 'descripcion', function () { return de.value.trim(); }));
        cont.appendChild(campo('Puntos clave', 'uno por línea (2–7)', pc = area('c-pc', (f.puntos_clave || []).join('\n')), 'puntos_clave', function () { return lineas(pc); }));
        cont.appendChild(campo('Material', 'opcional', ma = area('c-mat', f.material), 'material', function () { return ma.value.trim(); }));
        cont.appendChild(campo('Consigna', 'opcional', co = texto('c-cons', f.consigna), 'consigna', function () { return co.value.trim(); }));
        cont.appendChild(campo('Errores frecuentes', 'opcional, uno por línea', er = area('c-err', (f.errores_frecuentes || []).join('\n')), 'errores_frecuentes', function () { return lineas(er); }));
        cont.appendChild(campo('Qué observar', 'opcional, uno por línea', qo = area('c-obs', (f.que_observar || []).join('\n')), 'que_observar', function () { return lineas(qo); }));
        var pr = el('div', 'fi-fila');
        pr.appendChild(campo('Progresión: facilitar', 'opcional', pf = area('c-fac', p.facilitar), 'p_facilitar', function () { return pf.value.trim(); }));
        pr.appendChild(campo('Progresión: complicar', 'opcional', pd = area('c-comp', p.complicar), 'p_complicar', function () { return pd.value.trim(); }));
        cont.appendChild(pr);
        cont.addEventListener('input', cambio); cont.addEventListener('change', cambio);
        if (!editorDiagrama) editorDiagrama = new window.EditorDiagrama($('fi-diagrama'), { api: api, urlVista: URL_VISTA, onCambio: cambio });
        editorDiagrama.cargar(f);
    }

    function lee() {
        var v = {}, g = function (k) { return campos[k](); };
        ['nombre', 'categoria', 'subcategoria', 'espacio', 'edades', 'duracion_min', 'intensidad', 'carga_cognitiva', 'jugadores_minimos',
            'descripcion', 'puntos_clave', 'material', 'consigna', 'errores_frecuentes', 'que_observar'].forEach(function (k) { v[k] = g(k); });
        v.objetivos = { tacticos: g('o_tacticos'), tecnicos: g('o_tecnicos'), fisicos: g('o_fisicos') };
        v.progresion = { facilitar: g('p_facilitar'), complicar: g('p_complicar') };
        if (editorDiagrama) Object.assign(v, editorDiagrama.leer());
        return v;
    }
    function cambio() {
        var sucio = JSON.stringify(lee()) !== instantanea;
        $('fi-guardar').disabled = !sucio; $('fi-descartar').disabled = !sucio;
        if (sucio) estado('Cambios sin guardar');
        else if ($('fi-estado').textContent === 'Cambios sin guardar') estado('');
    }
    function haySinGuardar() { return !$('fi-guardar').disabled; }

    function muestraErrores(lista) {
        var c = $('fi-errores'); c.textContent = '';
        if (!lista || !lista.length) { c.hidden = true; return; }
        c.appendChild(el('strong', null, 'No se ha guardado:'));
        var ul = el('ul'); lista.forEach(function (t) { ul.appendChild(el('li', null, t)); }); c.appendChild(ul);
        c.hidden = false;
    }

    function abre(id, forzar) {
        if (!forzar && haySinGuardar() && actual && actual.id !== id) { estado('Tienes cambios sin guardar: guarda o descarta antes de cambiar de ficha.'); return; }
        var f = fichas.find(function (x) { return x.id === id; });
        if (!f) return;
        actual = f; confirmaRestaurar = false;
        $('fi-vacio').hidden = true; $('fi-form').hidden = false;
        $('fi-id').textContent = f.id;
        $('fi-mod-etq').hidden = !modificadas[f.id];
        $('fi-restaurar').hidden = !modificadas[f.id]; $('fi-restaurar').textContent = 'Restaurar la original';
        construye(f);
        instantanea = JSON.stringify(lee());
        $('fi-guardar').disabled = true; $('fi-descartar').disabled = true;
        muestraErrores(null); estado('');
        pintaLista();
        document.querySelector('#fi-ul [aria-current="true"]') && document.querySelector('#fi-ul [aria-current="true"]').scrollIntoView({ block: 'nearest' });
    }
    function vecina(d) {
        var i = visibles.findIndex(function (f) { return f.id === actual.id; });
        if (visibles[i + d]) abre(visibles[i + d].id);
    }

    // ── Guardar y restaurar ──────────────────────────────────────────────────
    function reemplaza(nueva, esModificada) {
        var i = fichas.findIndex(function (f) { return f.id === nueva.id; });
        if (i >= 0) fichas[i] = nueva;
        if (esModificada) modificadas[nueva.id] = true; else delete modificadas[nueva.id];
    }
    function guarda(ev) {
        if (ev) ev.preventDefault();
        if (!actual || $('fi-guardar').disabled) return;
        var id = actual.id;
        estado('Guardando…'); $('fi-guardar').disabled = true;
        api(URL_FICHA.replace('__ID__', id), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ficha: lee() }) })
            .then(function (r) {
                if (!r.ok) {
                    muestraErrores(r.cuerpo.problemas || [r.cuerpo.error || 'Error al guardar.']);
                    estado(''); $('fi-guardar').disabled = false; return;
                }
                reemplaza(r.cuerpo.ficha, true);
                abre(id, true); filtra();
                estado('Guardada. Ya vale para generar sesiones.');
            }).catch(function () { estado('No se pudo guardar: sin conexión con el servidor.'); $('fi-guardar').disabled = false; });
    }
    function restaura() {
        if (!actual) return;
        if (!confirmaRestaurar) { confirmaRestaurar = true; $('fi-restaurar').textContent = 'Pulsa otra vez para confirmar'; return; }
        var id = actual.id;
        api(URL_FICHA.replace('__ID__', id), { method: 'DELETE' }).then(function (r) {
            if (!r.ok) { muestraErrores([r.cuerpo.error || 'No se pudo restaurar.']); return; }
            reemplaza(r.cuerpo.ficha, false);
            abre(id, true); filtra(); estado('Restaurada la original.');
        }).catch(function () { estado('No se pudo restaurar: sin conexión con el servidor.'); });
    }

    // ── Arranque ─────────────────────────────────────────────────────────────
    function rellenaFiltros() {
        var edades = {}, cats = {};
        fichas.forEach(function (f) { (f.edades || []).forEach(function (e) { edades[e] = 1; }); cats[f.categoria] = 1; });
        EDADES.filter(function (e) { return edades[e]; }).forEach(function (e) { var o = el('option', null, e); o.value = e; $('fi-edad').appendChild(o); });
        Object.keys(cats).sort().forEach(function (c) { var o = el('option', null, c); o.value = c; $('fi-cat').appendChild(o); });
    }
    api(URL_DATOS).then(function (r) {
        if (!r.ok) { $('fi-ul').textContent = r.cuerpo.error || 'No se pudieron cargar las fichas.'; return; }
        fichas = r.cuerpo.fichas || [];
        (r.cuerpo.modificadas || []).forEach(function (id) { modificadas[id] = true; });
        rellenaFiltros(); filtra();
        if (visibles.length) abre(visibles[0].id, true);
    }).catch(function () { $('fi-ul').textContent = 'No se pudieron cargar las fichas.'; });

    ['fi-buscar', 'fi-edad', 'fi-cat', 'fi-mod'].forEach(function (id) { $(id).addEventListener('input', filtra); $(id).addEventListener('change', filtra); });
    $('fi-form').addEventListener('submit', guarda);
    $('fi-descartar').addEventListener('click', function () { if (actual) abre(actual.id, true); });
    $('fi-restaurar').addEventListener('click', restaura);
    $('fi-ant').addEventListener('click', function () { vecina(-1); });
    $('fi-sig').addEventListener('click', function () { vecina(1); });
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); guarda(); }
    });
    window.addEventListener('beforeunload', function (e) { if (haySinGuardar()) { e.preventDefault(); e.returnValue = ''; } });
})();
