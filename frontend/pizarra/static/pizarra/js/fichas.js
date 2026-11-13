// Pestaña «Fichas» (solo administrador): lista, filtros y editor de una ficha cada vez. Todo el texto entra con
// textContent / value: nada de innerHTML (el diagrama lo gestiona fichas_diagrama.js).
(function () {
    'use strict';
    var $ = function (id) { return document.getElementById(id); };
    var URL_DATOS = document.body.getAttribute('data-url-datos');
    var URL_FICHA = document.body.getAttribute('data-url-ficha');
    var URL_VISTA = document.body.getAttribute('data-url-vista');
    var URL_AVISOS = document.body.getAttribute('data-url-avisos');
    var URL_REEMPLAZAR = document.body.getAttribute('data-url-reemplazar');
    var editorDiagrama = null;   // se crea la primera vez que se abre una ficha
    var CATEGORIAS = ['juego_equipo', '1c1', 'ventaja_numerica', 'calentamiento', 'tiro', 'fisico', 'bloqueo_directo', 'bloqueo_indirecto'];
    var ESPACIOS = ['media_pista', 'pista_completa', 'flexible'];
    var EDADES = ['U8', 'U10', 'U12', 'U14', 'U16', 'U18', 'Senior'];

    var fichas = [];          // todas, con los cambios aplicados
    var modificadas = {};     // id → true
    var desfasadas = {};      // id → true: el español cambió después de la última revisión del inglés
    var inglesRevisado = false;   // «el inglés está al día» pulsado en la ficha abierta (se guarda con ella)
    var visibles = [];        // las que pasan el filtro
    var actual = null;        // ficha abierta
    var instantanea = '';     // estado del formulario al abrir/guardar, para saber si hay cambios
    var campos = {};          // nombre de campo → función que lee su valor
    var confirmaRestaurar = false;
    var pilaDeshacer = [], pilaRehacer = [], ultimoEstado = '', temporizadorRegistro = null, aplicando = false;   // deshacer/rehacer
    var MAX_PASOS = 100;

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
        var q = norm($('fi-buscar').value.trim()), edad = $('fi-edad').value, cat = $('fi-cat').value, solo = $('fi-mod').checked, soloDesf = $('fi-desf').checked;
        visibles = fichas.filter(function (f) {
            return (!q || textoDe(f).indexOf(q) >= 0) && (!edad || (f.edades || []).indexOf(edad) >= 0) &&
                (!cat || f.categoria === cat) && (!solo || modificadas[f.id]) && (!soloDesf || desfasadas[f.id]);
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
            if (desfasadas[f.id]) b.appendChild(el('span', 'fi-l-mod', '● inglés desfasado'));
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
        construyeIngles(f);
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
        var en = leeIngles();
        if (Object.keys(en).length) v.i18n = { en: en };
        if (inglesRevisado) v.ingles_revisado = true;
        return v;
    }

    // ── Inglés (pestaña English) ─────────────────────────────────────────────
    // Los mismos campos que en español, con el texto español de referencia encima de cada uno. Se guarda en
    // ficha.i18n.en; las listas deben tener los mismos elementos que en español (la API lo comprueba).
    var camposEn = {}, refsEn = [], contadoresEn = [], esAlAbrir = '';
    var ORDEN_EN = ['nombre', 'descripcion', 'material', 'consigna', 'puntos_clave', 'errores_frecuentes', 'que_observar', 'progresion', 'titulos_diagramas'];
    function campoEn(titulo, ayuda, control, nombre, lector, leerEs, esLista) {
        var d = el('div', 'fi-campo'), l = el('label', null, titulo);
        if (control.id) l.setAttribute('for', control.id);
        if (ayuda) l.appendChild(el('span', 'fi-ayuda', ayuda));
        if (esLista) { var n = el('span', 'fi-ayuda fi-cuenta-en'); l.appendChild(n); contadoresEn.push({ nodo: n, esN: function () { return leerEs().split('\n').filter(Boolean).length; }, enN: function () { return lector().length; } }); }
        d.appendChild(l);
        if (leerEs) {
            var r = el('div', 'fi-ref'), t = el('span', 'fi-ref-txt');
            r.appendChild(el('span', 'fi-ref-et', 'Español')); r.appendChild(t); d.appendChild(r);
            refsEn.push({ nodo: t, leer: leerEs });
        }
        d.appendChild(control);
        camposEn[nombre] = lector;
        return d;
    }
    function construyeIngles(f) {
        var cont = $('fi-ingles'); cont.textContent = ''; camposEn = {}; refsEn = []; contadoresEn = [];
        var en = ((f.i18n || {}).en) || {}, p = en.progresion || {}, c;
        var aviso = el('div', 'fi-aviso-es'); aviso.id = 'fi-en-aviso'; aviso.hidden = true;
        aviso.appendChild(el('span', null, '')); aviso.firstChild.id = 'fi-en-aviso-txt';
        var alDia = el('button', null, 'El inglés está al día'); alDia.type = 'button'; alDia.id = 'fi-en-aldia'; alDia.hidden = true;
        alDia.title = 'Marca el inglés como revisado contra el español actual (se guarda con la ficha)';
        alDia.addEventListener('click', function () { inglesRevisado = true; cambio(); refrescaIngles(); });
        aviso.appendChild(alDia); cont.appendChild(aviso);
        cont.appendChild(el('p', 'nota', 'La versión inglesa que ve quien use la web en inglés. Los números, los ids y el diagrama son los mismos en los dos idiomas; las listas deben tener los mismos elementos que en español.'));
        var lector = function (ctl) { return function () { return ctl.value.trim(); }; };
        var lectorLineas = function (ctl) { return function () { return lineas(ctl); }; };
        var es = function (k) { return function () { var v = campos[k] ? campos[k]() : ''; return Array.isArray(v) ? v.join('\n') : v; }; };
        cont.appendChild(campoEn('Name', '', c = texto('e-nombre', en.nombre), 'nombre', lector(c), es('nombre')));
        cont.appendChild(campoEn('Description', '', c = area('e-desc', en.descripcion, true), 'descripcion', lector(c), es('descripcion')));
        if (f.material || en.material) cont.appendChild(campoEn('Material', '', c = area('e-mat', en.material), 'material', lector(c), es('material')));
        if (f.consigna || en.consigna) cont.appendChild(campoEn('Cue', '', c = texto('e-cons', en.consigna), 'consigna', lector(c), es('consigna')));
        cont.appendChild(campoEn('Key points', 'one per line', c = area('e-pc', (en.puntos_clave || []).join('\n')), 'puntos_clave', lectorLineas(c), es('puntos_clave'), true));
        if ((f.errores_frecuentes || []).length || en.errores_frecuentes) cont.appendChild(campoEn('Common mistakes', 'one per line', c = area('e-err', (en.errores_frecuentes || []).join('\n')), 'errores_frecuentes', lectorLineas(c), es('errores_frecuentes'), true));
        if ((f.que_observar || []).length || en.que_observar) cont.appendChild(campoEn('What to look for', 'one per line', c = area('e-obs', (en.que_observar || []).join('\n')), 'que_observar', lectorLineas(c), es('que_observar'), true));
        if ((f.progresion || {}).facilitar || p.facilitar) cont.appendChild(campoEn('Progression: easier', '', c = area('e-fac', p.facilitar), 'p_facilitar', lector(c), es('p_facilitar')));
        if ((f.progresion || {}).complicar || p.complicar) cont.appendChild(campoEn('Progression: harder', '', c = area('e-comp', p.complicar), 'p_complicar', lector(c), es('p_complicar')));
        var titulosEs = (f.diagramas || []).map(function (d) { return d.titulo || ''; });
        if (titulosEs.some(Boolean) || en.titulos_diagramas) cont.appendChild(campoEn('Diagram titles', 'one per line, one per diagram', c = area('e-tit', (en.titulos_diagramas || []).join('\n')), 'titulos_diagramas', lectorLineas(c), function () { return titulosEs.join('\n'); }, true));
    }
    function leeIngles() {
        var o = {}, g = function (k) { return camposEn[k] ? camposEn[k]() : undefined; }, pf = g('p_facilitar'), pc = g('p_complicar');
        ORDEN_EN.forEach(function (k) {
            if (k === 'progresion') {
                if (pf || pc) { o.progresion = {}; if (pf) o.progresion.facilitar = pf; if (pc) o.progresion.complicar = pc; }
                return;
            }
            var v = g(k);
            if (v && (!Array.isArray(v) || v.length)) o[k] = v;
        });
        return o;
    }
    function textosEs() {
        var o = {};
        ['nombre', 'descripcion', 'puntos_clave', 'material', 'consigna', 'errores_frecuentes', 'que_observar', 'p_facilitar', 'p_complicar'].forEach(function (k) { if (campos[k]) o[k] = campos[k](); });
        return JSON.stringify(o);
    }
    function refrescaIngles() {
        refsEn.forEach(function (r) { r.nodo.textContent = r.leer(); });
        contadoresEn.forEach(function (c) {
            var a = c.esN(), b = c.enN();
            c.nodo.textContent = ' · ES ' + a + ' / EN ' + b;
            c.nodo.classList.toggle('fi-cuenta-mal', a !== b);
        });
        var av = $('fi-en-aviso');
        if (av) {
            var cambiado = textosEs() !== esAlAbrir, guardado = actual && desfasadas[actual.id], t = '';
            if (inglesRevisado) t = 'Marcado como revisado: se guardará con la ficha.';
            else if (cambiado) t = 'Has cambiado el español en esta sesión: comprueba que el inglés sigue diciendo lo mismo.';
            else if (guardado) t = 'El español de esta ficha cambió después de la última revisión del inglés.';
            av.hidden = !t;
            $('fi-en-aviso-txt').textContent = t + ' ';
            $('fi-en-aldia').hidden = inglesRevisado || !(cambiado || guardado);
        }
    }
    function muestraPestana(ingles) {
        $('fi-tab-es').setAttribute('aria-selected', ingles ? 'false' : 'true');
        $('fi-tab-en').setAttribute('aria-selected', ingles ? 'true' : 'false');
        $('fi-pane-es').hidden = ingles; $('fi-ingles').hidden = !ingles;
        if (ingles) refrescaIngles();
    }

    // ── Avisos automáticos (los mismos de tools/revisar_diagramas.py) ───────────
    var temporizadorAvisos = null, numeroAviso = 0;
    var ETIQUETAS_AVISO = { BALL: 'Balón', LABEL: 'Jugador citado', DEF: 'Defensores', RANGE: 'Fuera de pista', ORDER: 'Orden de movimientos', CONES: 'Conos', VALIDADOR: 'Validación', SIN: 'Diagrama' };
    function programaAvisos() { clearTimeout(temporizadorAvisos); temporizadorAvisos = setTimeout(pideAvisos, 900); }
    function pideAvisos() {
        clearTimeout(temporizadorAvisos);
        if (!actual) return;
        var mio = ++numeroAviso, id = actual.id;
        api(URL_AVISOS.replace('__ID__', id), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ficha: lee() }) })
            .then(function (r) { if (mio === numeroAviso && actual && actual.id === id) pintaAvisos(r.ok ? (r.cuerpo.avisos || []) : []); })
            .catch(function () {});
    }
    function pintaAvisos(lista) {
        var c = $('fi-avisos'); c.textContent = '';
        if (!lista.length) { c.hidden = true; return; }
        c.appendChild(el('strong', null, 'Avisos automáticos (' + lista.length + '): son pistas, no impiden guardar'));
        var ul = el('ul');
        lista.forEach(function (a) {
            var li = el('li');
            li.appendChild(el('span', 'fi-av-tipo', ETIQUETAS_AVISO[a.tipo] || a.tipo));
            li.appendChild(document.createTextNode(' ' + a.texto));
            ul.appendChild(li);
        });
        c.appendChild(ul); c.hidden = false;
    }
    function cambio() {
        programaAvisos();
        if (!$('fi-ingles').hidden) refrescaIngles();
        if (!aplicando) programaRegistro();
        var sucio = JSON.stringify(lee()) !== instantanea;
        $('fi-guardar').disabled = !sucio; $('fi-descartar').disabled = !sucio;
        if (sucio) estado('Cambios sin guardar');
        else if ($('fi-estado').textContent === 'Cambios sin guardar') estado('');
    }
    // ── Deshacer / rehacer ───────────────────────────────────────────────────
    // Cada «paso» es una foto del formulario entero (campos y diagrama). Lo que se escribe o arrastra seguido cuenta
    // como un solo paso: se registra cuando uno deja de tocar medio segundo.
    function botonesPasos() { $('fi-deshacer').disabled = !pilaDeshacer.length; $('fi-rehacer').disabled = !pilaRehacer.length; }
    function programaRegistro() { clearTimeout(temporizadorRegistro); temporizadorRegistro = setTimeout(registra, 500); }
    function registra() {
        clearTimeout(temporizadorRegistro); temporizadorRegistro = null;
        if (!actual || aplicando) return;
        var ahora = JSON.stringify(lee());
        if (ahora === ultimoEstado) return;
        pilaDeshacer.push(ultimoEstado); if (pilaDeshacer.length > MAX_PASOS) pilaDeshacer.shift();
        pilaRehacer = []; ultimoEstado = ahora; botonesPasos();
    }
    function vuelveA(estado) {
        aplicando = true;
        try { var f = JSON.parse(estado); inglesRevisado = !!f.ingles_revisado; construye(f); } finally { aplicando = false; }
        ultimoEstado = estado; cambio(); botonesPasos();
    }
    function deshacer() {
        if (!actual) return;
        registra();
        if (!pilaDeshacer.length) return;
        pilaRehacer.push(ultimoEstado); vuelveA(pilaDeshacer.pop());
    }
    function rehacer() {
        if (!actual) return;
        registra();
        if (!pilaRehacer.length) return;
        pilaDeshacer.push(ultimoEstado); vuelveA(pilaRehacer.pop());
    }
    function reiniciaPasos() { clearTimeout(temporizadorRegistro); temporizadorRegistro = null; pilaDeshacer = []; pilaRehacer = []; ultimoEstado = instantanea; botonesPasos(); }

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
        actual = f; confirmaRestaurar = false; inglesRevisado = false;
        $('fi-vacio').hidden = true; $('fi-form').hidden = false;
        $('fi-id').textContent = f.id;
        $('fi-mod-etq').hidden = !modificadas[f.id];
        $('fi-restaurar').hidden = !modificadas[f.id]; $('fi-restaurar').textContent = 'Volver a la versión guardada anterior';
        construye(f);
        instantanea = JSON.stringify(lee()); reiniciaPasos();
        esAlAbrir = textosEs(); muestraPestana(false); pideAvisos();
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
    function marcaDesfasada(id, valor) { if (valor) desfasadas[id] = true; else delete desfasadas[id]; }
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
                reemplaza(r.cuerpo.ficha, true); marcaDesfasada(id, r.cuerpo.desfasada);
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
            reemplaza(r.cuerpo.ficha, false); marcaDesfasada(id, r.cuerpo.desfasada);
            abre(id, true); filtra(); estado('Ficha devuelta a la versión anterior.');
        }).catch(function () { estado('No se pudo restaurar: sin conexión con el servidor.'); });
    }

    // ── Buscar y reemplazar en toda la biblioteca ────────────────────────────
    var confirmaAplicar = false;
    function reEstado(t) { $('re-estado').textContent = t || ''; }
    function reiniciaConfirmacion() { confirmaAplicar = false; $('re-aplicar').textContent = 'Aplicar a las marcadas'; }
    function cuerpoReemplazo(aplicar, ids) {
        return { buscar: $('re-buscar').value, reemplazar: $('re-nuevo').value, ambito: $('re-ambito').value,
            palabra: $('re-palabra').checked, mayusculas: $('re-mayus').checked, aplicar: !!aplicar, ids: ids || null };
    }
    function mensajeError(r, porDefecto) {
        var d = r.cuerpo && r.cuerpo.detail;
        return (r.cuerpo && r.cuerpo.error) || (typeof d === 'string' ? d : porDefecto);
    }
    function marcadas() {
        return Array.prototype.slice.call(document.querySelectorAll('#re-resultado input[data-id]:checked')).map(function (i) { return i.getAttribute('data-id'); });
    }
    function pintaReemplazo(cuerpo) {
        var c = $('re-resultado'); c.textContent = ''; reiniciaConfirmacion();
        var lista = cuerpo.fichas || [];
        if (!lista.length) { c.hidden = true; reEstado('No hay coincidencias.'); $('re-aplicar').disabled = true; return; }
        reEstado(lista.length + ' fichas, ' + cuerpo.total_cambios + ' cambios. Desmarca las que no quieras tocar.');
        var todas = el('button', null, 'Marcar / desmarcar todas'); todas.type = 'button';
        todas.addEventListener('click', function () {
            var cajas = c.querySelectorAll('input[data-id]'), hay = Array.prototype.some.call(cajas, function (i) { return i.checked; });
            Array.prototype.forEach.call(cajas, function (i) { i.checked = !hay; }); reiniciaConfirmacion();
        });
        c.appendChild(todas);
        lista.forEach(function (f) {
            var det = el('div', 'fi-reemp-ficha'), lab = el('label'), caja = el('input');
            caja.type = 'checkbox'; caja.checked = true; caja.setAttribute('data-id', f.id);
            caja.addEventListener('change', reiniciaConfirmacion);
            lab.appendChild(caja); lab.appendChild(document.createTextNode(' '));
            lab.appendChild(el('strong', null, f.id)); lab.appendChild(document.createTextNode(' ' + f.nombre + ' (' + f.cambios.length + ')'));
            det.appendChild(lab);
            var ul = el('ul');
            f.cambios.forEach(function (x) {
                var li = el('li');
                li.appendChild(el('span', 'fi-av-tipo', x.campo));
                li.appendChild(el('span', 'fi-antes', x.antes));
                li.appendChild(document.createTextNode(' → '));
                li.appendChild(el('span', 'fi-despues', x.despues));
                ul.appendChild(li);
            });
            det.appendChild(ul); c.appendChild(det);
        });
        c.hidden = false; $('re-aplicar').disabled = false;
    }
    function reemplazoVer() {
        if (!$('re-buscar').value) { reEstado('Escribe qué buscar.'); return; }
        reEstado('Buscando…'); $('re-aplicar').disabled = true;
        api(URL_REEMPLAZAR, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpoReemplazo(false)) })
            .then(function (r) {
                if (!r.ok) { reEstado(mensajeError(r, 'No se pudo buscar.')); return; }
                pintaReemplazo(r.cuerpo);
            }).catch(function () { reEstado('No se pudo buscar: sin conexión con el servidor.'); });
    }
    function reemplazoAplicar() {
        if (haySinGuardar()) { reEstado('Guarda o descarta antes los cambios de la ficha abierta.'); return; }
        var ids = marcadas();
        if (!ids.length) { reEstado('No hay fichas marcadas.'); return; }
        if (!confirmaAplicar) { confirmaAplicar = true; $('re-aplicar').textContent = 'Pulsa otra vez para confirmar (' + ids.length + ' fichas)'; return; }
        reiniciaConfirmacion(); $('re-aplicar').disabled = true; reEstado('Aplicando…');
        api(URL_REEMPLAZAR, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpoReemplazo(true, ids)) })
            .then(function (r) {
                if (!r.ok) { reEstado(mensajeError(r, 'No se pudo aplicar.')); $('re-aplicar').disabled = false; return; }
                var om = r.cuerpo.omitidas || [], txt = 'Cambiadas ' + (r.cuerpo.guardadas || []).length + ' fichas.';
                if (om.length) txt += ' No se han tocado por no quedar válidas: ' + om.map(function (o) { return o.id; }).join(', ') + '.';
                $('re-resultado').textContent = ''; $('re-resultado').hidden = true;
                recarga().then(function () { reEstado(txt); });
            }).catch(function () { reEstado('No se pudo aplicar: sin conexión con el servidor.'); $('re-aplicar').disabled = false; });
    }
    function recarga() {
        return api(URL_DATOS).then(function (r) {
            if (!r.ok) return;
            fichas = r.cuerpo.fichas || []; modificadas = {}; desfasadas = {};
            (r.cuerpo.modificadas || []).forEach(function (id) { modificadas[id] = true; });
            (r.cuerpo.desfasadas || []).forEach(function (id) { desfasadas[id] = true; });
            filtra();
            if (actual) abre(actual.id, true);
        });
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
        (r.cuerpo.desfasadas || []).forEach(function (id) { desfasadas[id] = true; });
        rellenaFiltros(); filtra();
        if (visibles.length) abre(visibles[0].id, true);
    }).catch(function () { $('fi-ul').textContent = 'No se pudieron cargar las fichas.'; });

    ['fi-buscar', 'fi-edad', 'fi-cat', 'fi-mod', 'fi-desf'].forEach(function (id) { $(id).addEventListener('input', filtra); $(id).addEventListener('change', filtra); });
    $('fi-tab-es').addEventListener('click', function () { muestraPestana(false); });
    $('fi-tab-en').addEventListener('click', function () { muestraPestana(true); });
    $('fi-ingles').addEventListener('input', cambio); $('fi-ingles').addEventListener('change', cambio);
    $('re-ver').addEventListener('click', reemplazoVer);
    $('re-aplicar').addEventListener('click', reemplazoAplicar);
    ['re-buscar', 're-nuevo', 're-ambito', 're-palabra', 're-mayus'].forEach(function (id) {
        $(id).addEventListener('input', function () { reiniciaConfirmacion(); $('re-aplicar').disabled = true; });
        $(id).addEventListener('change', function () { reiniciaConfirmacion(); $('re-aplicar').disabled = true; });
    });
    $('re-buscar').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); reemplazoVer(); } });
    $('fi-form').addEventListener('submit', guarda);
    $('fi-descartar').addEventListener('click', function () { if (actual) abre(actual.id, true); });
    $('fi-restaurar').addEventListener('click', restaura);
    $('fi-deshacer').addEventListener('click', deshacer);
    $('fi-rehacer').addEventListener('click', rehacer);
    $('fi-ant').addEventListener('click', function () { vecina(-1); });
    $('fi-sig').addEventListener('click', function () { vecina(1); });
    document.addEventListener('keydown', function (e) {
        if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
        var k = e.key.toLowerCase();
        if (k === 's') { e.preventDefault(); guarda(); }
        else if (k === 'z' && !e.shiftKey) { e.preventDefault(); deshacer(); }
        else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); rehacer(); }
    });
    window.addEventListener('beforeunload', function (e) { if (haySinGuardar()) { e.preventDefault(); e.returnValue = ''; } });
})();
