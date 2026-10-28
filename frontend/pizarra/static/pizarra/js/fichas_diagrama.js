// Editor del diagrama de una ficha (pestaña «Fichas», solo administrador).
// El modelo es el propio JSON del diagrama (coordenadas 0-100). La vista previa la dibuja el servidor (la misma que
// verán en las sesiones) y sobre ella se arrastran jugadores, conos y destinos de movimiento. El único innerHTML es
// el SVG que devuelve la API, generado por el renderizador con ids alfanuméricos.
(function () {
    'use strict';
    var TIPOS_PISTA = ['media_pista', 'pista_completa'];
    var TIPOS_MOV = ['desplazamiento', 'pase', 'bote', 'tiro', 'bloqueo'];
    var GEO = {   // mismo dibujo que api/diagram_renderer.py: píxeles del SVG ↔ coordenadas 0-100
        media_pista: { pad: 30, W: 675, H: 630, SW: 735, SH: 690 },
        pista_completa: { pad: 70, W: 675, H: 1260, SW: 815, SH: 1400 }
    };
    var RADIO_CLIC = 26;

    function el(tag, clase, texto) { var e = document.createElement(tag); if (clase) e.className = clase; if (texto != null) e.textContent = texto; return e; }
    function copia(o) { return JSON.parse(JSON.stringify(o)); }
    function nuevoDiagrama() {
        return { tipo: 'media_pista', jugadores_ataque: [{ id: 'A1', x: 50, y: 65 }], jugadores_defensa: [], balon_inicio: { portador: 'A1' }, movimientos: [], conos: [] };
    }
    function normaliza(d) {
        d = copia(d || nuevoDiagrama());
        d.tipo = TIPOS_PISTA.indexOf(d.tipo) >= 0 ? d.tipo : 'media_pista';
        ['jugadores_ataque', 'jugadores_defensa', 'movimientos', 'conos'].forEach(function (k) { if (!Array.isArray(d[k])) d[k] = []; });
        d.balon_inicio = d.balon_inicio && typeof d.balon_inicio === 'object' ? d.balon_inicio : {};
        d.movimientos.sort(function (a, b) { return (a.orden || 0) - (b.orden || 0); });      // se ejecutan por «orden»
        return d;
    }
    function r1(n) { return Math.round(n * 10) / 10; }
    function num(v) { var n = parseFloat(v); return isFinite(n) ? n : v; }

    window.EditorDiagrama = function (raiz, opciones) {
        var modo = 'ninguno', lista = [], sel = 0, token = 0, temporizador = null, ultimoSvg = '', arrastre = null, avisoReparado = false;
        var refs = {};

        // ── Estructura fija ──────────────────────────────────────────────────
        raiz.textContent = '';
        var tit = el('span', 'fi-et', 'Diagrama');
        var selModo = el('select'); selModo.id = 'dg-modo'; selModo.setAttribute('aria-label', 'Tipo de diagrama');
        [['ninguno', 'Sin diagrama guardado (la IA dibuja uno al generar)'], ['libre', 'Sin diagrama: juego libre'], ['uno', 'Un diagrama'], ['varios', 'Varios diagramas (fases)']]
            .forEach(function (o) { var op = el('option', null, o[1]); op.value = o[0]; selModo.appendChild(op); });
        var cuerpo = el('div', 'dg-cuerpo');
        raiz.appendChild(tit); raiz.appendChild(selModo); raiz.appendChild(cuerpo);
        selModo.addEventListener('change', function () { cambiaModo(selModo.value); });

        function cambiaModo(m) {
            if ((m === 'uno' || m === 'varios') && !lista.length) lista = [nuevoDiagrama()];
            if (m === 'uno') lista = lista.slice(0, 1);
            modo = m; sel = Math.min(sel, Math.max(0, lista.length - 1)); selModo.value = m;
            pintaCuerpo(); opciones.onCambio();
        }
        function actual() { return lista[sel]; }
        function cambio(vista) { opciones.onCambio(); if (vista !== false) pideVista(); }

        // ── Cuerpo del editor ────────────────────────────────────────────────
        function pintaCuerpo() {
            cuerpo.textContent = '';
            if (modo === 'ninguno' || modo === 'libre') {
                cuerpo.appendChild(el('p', 'nota', modo === 'libre' ? 'Ejercicio sin diagrama (juego libre): no se dibuja nada.' : 'Al generar la sesión, la IA intentará dibujar un diagrama a partir del texto.'));
                return;
            }
            if (modo === 'varios') {
                var pest = el('div', 'barra dg-pest'); pest.setAttribute('role', 'group'); pest.setAttribute('aria-label', 'Diagramas de la ficha');
                lista.forEach(function (d, i) {
                    var b = el('button', null, (i + 1) + (d.titulo ? ' · ' + d.titulo.slice(0, 22) : '')); b.type = 'button';
                    b.setAttribute('aria-pressed', i === sel ? 'true' : 'false');
                    b.addEventListener('click', function () { sel = i; pintaCuerpo(); pideVista(); });
                    pest.appendChild(b);
                });
                [['+ Añadir', function () { lista.push(nuevoDiagrama()); sel = lista.length - 1; }],
                    ['Duplicar', function () { lista.splice(sel + 1, 0, copia(actual())); sel++; }],
                    ['Quitar', function () { if (lista.length > 1) { lista.splice(sel, 1); sel = Math.max(0, sel - 1); } }]].forEach(function (a) {
                    var b = el('button', null, a[0]); b.type = 'button';
                    b.addEventListener('click', function () { a[1](); pintaCuerpo(); cambio(); });
                    pest.appendChild(b);
                });
                cuerpo.appendChild(pest);
                var t = el('input'); t.type = 'text'; t.placeholder = 'Título de este diagrama (p. ej. «Fase 1»)'; t.value = actual().titulo || '';
                t.setAttribute('aria-label', 'Título del diagrama');
                t.addEventListener('input', function () { if (t.value.trim()) actual().titulo = t.value; else delete actual().titulo; cambio(false); });
                cuerpo.appendChild(t);
            }
            var rejilla = el('div', 'dg-rejilla');
            var izq = el('div', 'dg-vista');
            refs.vista = el('div', 'dg-svg'); refs.vista.setAttribute('role', 'img');
            refs.vista.setAttribute('aria-label', 'Vista previa del diagrama; arrastra jugadores, conos y destinos para moverlos');
            refs.msg = el('div', 'dg-msg'); refs.msg.setAttribute('role', 'status');
            izq.appendChild(refs.vista); izq.appendChild(refs.msg);
            izq.appendChild(el('p', 'nota', 'Arrastra los jugadores (círculos), los conos y el destino de cada movimiento para moverlos.'));
            var der = el('div', 'dg-tablas'); refs.tablas = der;
            rejilla.appendChild(izq); rejilla.appendChild(der); cuerpo.appendChild(rejilla);
            var det = el('details', 'dg-json'); det.appendChild(el('summary', null, 'JSON avanzado de este diagrama'));
            refs.json = el('textarea'); refs.json.setAttribute('aria-label', 'JSON del diagrama'); refs.json.spellcheck = false;
            var ap = el('button', null, 'Aplicar JSON'); ap.type = 'button';
            refs.jsonMsg = el('span', 'nota');
            ap.addEventListener('click', function () {
                try { lista[sel] = normaliza(JSON.parse(refs.json.value)); refs.jsonMsg.textContent = 'Aplicado.'; pintaTablas(); cambio(); }
                catch (e) { refs.jsonMsg.textContent = 'JSON no válido: ' + e.message; }
            });
            det.appendChild(refs.json); det.appendChild(ap); det.appendChild(refs.jsonMsg); cuerpo.appendChild(det);
            refs.vista.addEventListener('pointerdown', empiezaArrastre);
            pintaTablas();
        }

        // ── Tablas ───────────────────────────────────────────────────────────
        function ids() { var d = actual(); return d.jugadores_ataque.concat(d.jugadores_defensa).map(function (j) { return j.id; }); }
        function entrada(valor, ancho, alAbrir, tipo) {
            var i = el('input'); i.type = tipo || 'text'; i.value = valor == null ? '' : valor; if (ancho) i.style.width = ancho;
            if (tipo === 'number') i.step = '0.1';
            i.addEventListener('input', function () { alAbrir(i.value); }); return i;
        }
        function boton(texto, etiqueta, fn) { var b = el('button', 'dg-mini', texto); b.type = 'button'; b.setAttribute('aria-label', etiqueta); b.addEventListener('click', fn); return b; }
        function seccion(titulo) { var s = el('div', 'dg-sec'); s.appendChild(el('h3', null, titulo)); refs.tablas.appendChild(s); return s; }
        function fila(s) { var f = el('div', 'dg-fila'); s.appendChild(f); return f; }
        function libre(prefijo) {
            var usados = ids(), n = 1; while (usados.indexOf(prefijo + n) >= 0) n++; return prefijo + n;
        }
        function huecoLibre(d) {      // un sitio de la pista a más de 12 unidades de todo lo demás
            var pts = d.jugadores_ataque.concat(d.jugadores_defensa, d.conos);
            for (var y = 50; y <= 90; y += 8) for (var x = 20; x <= 80; x += 10) {
                if (pts.every(function (p) { return Math.hypot(p.x - x, p.y - y) > 12; })) return { x: x, y: y };
            }
            return { x: 50, y: 50 };
        }
        function pintaTablas() {
            var d = actual(); refs.tablas.textContent = '';
            var s = seccion('Pista');
            var tp = el('select'); tp.setAttribute('aria-label', 'Tipo de pista');
            [['media_pista', 'Media pista'], ['pista_completa', 'Pista completa']].forEach(function (o) { var op = el('option', null, o[1]); op.value = o[0]; tp.appendChild(op); });
            tp.value = d.tipo; tp.addEventListener('change', function () { d.tipo = tp.value; cambio(); });
            s.appendChild(tp);

            [['jugadores_ataque', 'Atacantes', 'A'], ['jugadores_defensa', 'Defensores', 'D']].forEach(function (g) {
                var sec = seccion(g[1]);
                d[g[0]].forEach(function (j, i) {
                    var f = fila(sec);
                    f.appendChild(entrada(j.id, '4.2rem', function (v) { renombra(j, v.trim()); cambio(); }));
                    f.appendChild(el('span', 'nota', 'x')); f.appendChild(entrada(j.x, '4.2rem', function (v) { j.x = num(v); cambio(); }, 'number'));
                    f.appendChild(el('span', 'nota', 'y')); f.appendChild(entrada(j.y, '4.2rem', function (v) { j.y = num(v); cambio(); }, 'number'));
                    f.appendChild(boton('✕', 'Quitar ' + j.id, function () { quita(g[0], i); }));
                });
                sec.appendChild(boton('+ ' + g[1].toLowerCase().slice(0, -1), 'Añadir', function () {
                    var h = huecoLibre(d); d[g[0]].push({ id: libre(g[2]), x: h.x, y: h.y }); pintaTablas(); cambio();
                }));
            });

            var sc = seccion('Conos');
            d.conos.forEach(function (c, i) {
                var f = fila(sc);
                f.appendChild(el('span', 'nota', 'x')); f.appendChild(entrada(c.x, '4.2rem', function (v) { c.x = num(v); cambio(); }, 'number'));
                f.appendChild(el('span', 'nota', 'y')); f.appendChild(entrada(c.y, '4.2rem', function (v) { c.y = num(v); cambio(); }, 'number'));
                f.appendChild(boton('✕', 'Quitar cono', function () { d.conos.splice(i, 1); pintaTablas(); cambio(); }));
            });
            sc.appendChild(boton('+ cono', 'Añadir cono', function () { var h = huecoLibre(d); d.conos.push({ x: h.x, y: h.y }); pintaTablas(); cambio(); }));

            var sb = seccion('Balón al empezar'); var pb = selectorJugador(d.balon_inicio.portador, true, function (v) {
                if (v) d.balon_inicio = { portador: v }; else d.balon_inicio = {}; cambio();
            }); sb.appendChild(pb);

            var sm = seccion('Movimientos (en este orden)');
            d.movimientos.forEach(function (m, i) {
                var f = fila(sm);
                f.appendChild(el('span', 'dg-n', String(i + 1)));
                f.appendChild(selectorJugador(m.de, false, function (v) { m.de = v; cambio(); }));
                var st = el('select'); st.setAttribute('aria-label', 'Tipo de movimiento');
                TIPOS_MOV.forEach(function (t) { var op = el('option', null, t); op.value = t; st.appendChild(op); });
                st.value = m.tipo; st.addEventListener('change', function () { cambiaTipoMov(m, st.value); pintaTablas(); cambio(); });
                f.appendChild(st);
                if (m.tipo === 'pase') f.appendChild(selectorJugador(m.a, false, function (v) { m.a = v; cambio(); }));
                else if (m.tipo !== 'tiro') {
                    m.a_pos = m.a_pos || { x: 50, y: 50 };
                    f.appendChild(el('span', 'nota', 'a')); f.appendChild(entrada(m.a_pos.x, '4rem', function (v) { m.a_pos.x = num(v); cambio(); }, 'number'));
                    f.appendChild(entrada(m.a_pos.y, '4rem', function (v) { m.a_pos.y = num(v); cambio(); }, 'number'));
                    var cu = entrada(m.curva === undefined || m.curva === true ? '' : m.curva, '4.6rem', function (v) { if (v === '') delete m.curva; else m.curva = num(v); cambio(); }, 'number');
                    cu.title = 'Curva (−1 a 1; vacío = recta)'; cu.placeholder = 'curva'; f.appendChild(cu);
                }
                f.appendChild(boton('↑', 'Subir', function () { if (i > 0) { d.movimientos.splice(i - 1, 0, d.movimientos.splice(i, 1)[0]); pintaTablas(); cambio(); } }));
                f.appendChild(boton('↓', 'Bajar', function () { if (i < d.movimientos.length - 1) { d.movimientos.splice(i + 1, 0, d.movimientos.splice(i, 1)[0]); pintaTablas(); cambio(); } }));
                f.appendChild(boton('✕', 'Quitar movimiento', function () { d.movimientos.splice(i, 1); pintaTablas(); cambio(); }));
            });
            sm.appendChild(boton('+ movimiento', 'Añadir movimiento', function () {
                var de = (d.balon_inicio.portador) || ids()[0] || '';
                d.movimientos.push({ de: de, tipo: 'desplazamiento', a_pos: { x: 50, y: 50 } }); pintaTablas(); cambio();
            }));
            refs.json.value = JSON.stringify(sinOrden(d), null, 1);
        }
        function selectorJugador(valor, conVacio, alCambiar) {
            var s = el('select'); s.setAttribute('aria-label', 'Jugador');
            var lista_ids = ids(); if (conVacio) lista_ids = [''].concat(lista_ids);
            if (valor && lista_ids.indexOf(valor) < 0) lista_ids.push(valor);
            lista_ids.forEach(function (id) { var op = el('option', null, id || '(nadie)'); op.value = id; s.appendChild(op); });
            s.value = valor || ''; s.addEventListener('change', function () { alCambiar(s.value); }); return s;
        }
        function cambiaTipoMov(m, tipo) {
            m.tipo = tipo;
            if (tipo === 'pase') { delete m.a_pos; delete m.curva; if (!m.a) m.a = ids().filter(function (x) { return x !== m.de; })[0] || ''; }
            else if (tipo === 'tiro') { delete m.a_pos; delete m.a; delete m.curva; }
            else { delete m.a; if (!m.a_pos) m.a_pos = { x: 50, y: 50 }; }
        }
        function renombra(j, nuevo) {
            var d = actual(), viejo = j.id; j.id = nuevo;
            if (d.balon_inicio.portador === viejo) d.balon_inicio.portador = nuevo;
            d.movimientos.forEach(function (m) { if (m.de === viejo) m.de = nuevo; if (m.a === viejo) m.a = nuevo; });
        }
        function quita(clave, i) {
            var d = actual(), id = d[clave][i].id;
            d[clave].splice(i, 1);
            if (d.balon_inicio.portador === id) d.balon_inicio = {};
            d.movimientos = d.movimientos.filter(function (m) { return m.de !== id && m.a !== id; });
            pintaTablas(); cambio();
        }
        function sinOrden(d) {          // el JSON que se guarda: «orden» según la posición en la lista
            var c = copia(d);
            c.movimientos.forEach(function (m, i) { m.orden = i + 1; });
            return c;
        }

        // ── Vista previa ─────────────────────────────────────────────────────
        function pideVista() {
            if (!refs.vista) return;
            clearTimeout(temporizador);
            temporizador = setTimeout(function () {
                var yo = ++token;
                opciones.api(opciones.urlVista, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ diagrama: sinOrden(actual()) }) })
                    .then(function (r) {
                        if (yo !== token || !refs.vista) return;
                        if (r.ok) {
                            ultimoSvg = r.cuerpo.svg; refs.vista.innerHTML = ultimoSvg; refs.vista.style.opacity = '1';
                            var igual = JSON.stringify(r.cuerpo.diagrama.jugadores_ataque.concat(r.cuerpo.diagrama.jugadores_defensa)) ===
                                JSON.stringify(sinOrden(actual()).jugadores_ataque.concat(sinOrden(actual()).jugadores_defensa));
                            refs.msg.textContent = igual ? '' : 'Al guardar se separarán un poco los jugadores que están muy juntos.';
                            refs.msg.className = 'dg-msg';
                            refs.json.value = JSON.stringify(sinOrden(actual()), null, 1);
                        } else {
                            refs.vista.style.opacity = '.45';
                            refs.msg.textContent = (r.cuerpo.problemas || [r.cuerpo.error || 'No se puede dibujar']).join(' · ');
                            refs.msg.className = 'dg-msg dg-mal';
                        }
                    }).catch(function () { if (refs.msg) { refs.msg.textContent = 'Sin conexión con el servidor.'; refs.msg.className = 'dg-msg dg-mal'; } });
            }, 90);
        }

        // ── Arrastre sobre la vista previa ───────────────────────────────────
        function aPx(d, p) { var g = GEO[d.tipo]; return { x: g.pad + p.x / 100 * g.W, y: g.SH - g.pad - p.y / 100 * g.H }; }
        function puntos(d) {
            var out = [];
            d.jugadores_ataque.forEach(function (j) { out.push({ p: j, px: aPx(d, j), prio: 0 }); });
            d.jugadores_defensa.forEach(function (j) { out.push({ p: j, px: aPx(d, j), prio: 0 }); });
            d.conos.forEach(function (c) { out.push({ p: c, px: aPx(d, c), prio: 1 }); });
            d.movimientos.forEach(function (m) { if (m.a_pos) out.push({ p: m.a_pos, px: aPx(d, m.a_pos), prio: 2 }); });
            return out;
        }
        function empiezaArrastre(ev) {
            var svg = refs.vista.querySelector('svg'); if (!svg || ev.button > 0) return;
            var d = actual(), g = GEO[d.tipo], pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
            var q = pt.matrixTransform(svg.getScreenCTM().inverse());
            var mejor = null, md = RADIO_CLIC;
            puntos(d).forEach(function (c) { var dist = Math.hypot(c.px.x - q.x, c.px.y - q.y) + c.prio * 0.01; if (dist < md) { md = dist; mejor = c; } });
            if (!mejor) return;
            ev.preventDefault();
            arrastre = { c: mejor, svg: svg, g: g };
            refs.vista.setPointerCapture(ev.pointerId);
            refs.vista.addEventListener('pointermove', mueve); refs.vista.addEventListener('pointerup', suelta); refs.vista.addEventListener('pointercancel', suelta);
        }
        function mueve(ev) {
            if (!arrastre) return;
            var pt = arrastre.svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
            var q = pt.matrixTransform(arrastre.svg.getScreenCTM().inverse()), g = arrastre.g;
            arrastre.c.p.x = Math.max(0, Math.min(100, r1((q.x - g.pad) / g.W * 100)));
            arrastre.c.p.y = Math.max(0, Math.min(100, r1((g.SH - g.pad - q.y) / g.H * 100)));
            opciones.onCambio(); pideVista();
        }
        function suelta(ev) {
            refs.vista.removeEventListener('pointermove', mueve); refs.vista.removeEventListener('pointerup', suelta); refs.vista.removeEventListener('pointercancel', suelta);
            try { refs.vista.releasePointerCapture(ev.pointerId); } catch (e) { /* ya liberado */ }
            arrastre = null; pintaTablas(); pideVista();
        }

        // ── Interfaz hacia fichas.js ─────────────────────────────────────────
        return {
            cargar: function (f) {
                if (Array.isArray(f.diagramas) && f.diagramas.length) { modo = 'varios'; lista = f.diagramas.map(normaliza); }
                else if (f.diagrama) { modo = 'uno'; lista = [normaliza(f.diagrama)]; }
                else { modo = f.sin_diagrama ? 'libre' : 'ninguno'; lista = []; }
                sel = 0; selModo.value = modo; pintaCuerpo(); pideVista();
            },
            leer: function () {
                if (modo === 'varios') return { sin_diagrama: false, diagramas: lista.map(sinOrden) };
                if (modo === 'uno') return { sin_diagrama: false, diagrama: sinOrden(lista[0]) };
                return { sin_diagrama: modo === 'libre' };
            }
        };
    };
})();
