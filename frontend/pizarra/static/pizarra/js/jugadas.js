/* Editor de jugadas de MiPizarra. Todo ocurre en el navegador: no llama a la API ni a ningún modelo.
   Modelo: una jugada = fases; cada fase = piezas con posición + flechas (pase, bote, corte, bloqueo).
   Medio campo en unidades de 0.1 m... en realidad en «pies × 10»: ancho 500, largo 470, aro en (250, 52). */
(function () {
'use strict';

var NS = 'http://www.w3.org/2000/svg';
var W = 500, H = 470, ARO = { x: 250, y: 52 };
var R = 16;                                   // radio de una pieza
var MAX_FASES = 12, MAX_FLECHAS = 40, MAX_CONOS = 8;
var CLAVE = 'mipizarra.jugadas.v1';

var TIPOS_FLECHA = {
    pase:    { etiqueta: 'Pase',    verbo: 'pasa' },
    bote:    { etiqueta: 'Bote',    verbo: 'bota' },
    corte:   { etiqueta: 'Corte',   verbo: 'se mueve' },
    bloqueo: { etiqueta: 'Bloqueo', verbo: 'bloquea' }
};
var NOMBRE_PIEZA = { A: 'Atacante', D: 'Defensor', B: 'Balón', C: 'Cono' };

var CLARO = { // tema de pantalla
    fondo: '#2a2118', linea: '#9c9186', ataque: '#e8752c', ataqueTxt: '#15120e', defensa: '#d8d0c4', defensaTxt: '#d8d0c4',
    balon: '#ffc78a', balonTrazo: '#3b2412', cono: '#e8752c', flecha: '#f2ede4', pase: '#f2ede4', sel: '#ffd37a', fantasma: '#ffd37a'
};
var IMPRESION = { // tema para PNG e impresión: tinta sobre blanco
    fondo: '#ffffff', linea: '#666666', ataque: '#e8752c', ataqueTxt: '#15120e', defensa: '#1b1b1f', defensaTxt: '#1b1b1f',
    balon: '#ffd9a8', balonTrazo: '#1b1b1f', cono: '#e8752c', flecha: '#1b1b1f', pase: '#1b1b1f', sel: '#1b1b1f', fantasma: '#1b1b1f'
};

var $ = function (id) { return document.getElementById(id); };
var reducirMovimiento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── Estado ────────────────────────────────────────────────────────────────
var estado, herramienta = 'mover', sel = null, deshacer = [], rehacer = [], reproduccion = null;

function faseVacia() { return { piezas: [], flechas: [] }; }
function jugadaNueva() { return { nombre: '', fases: [faseVacia()], actual: 0 }; }
function fase() { return estado.fases[estado.actual]; }
function clon(o) { return JSON.parse(JSON.stringify(o)); }
function acotar(v, a, b) { return Math.max(a, Math.min(b, v)); }
function redondea(v) { return Math.round(v * 10) / 10; }

function guardarPaso() {
    deshacer.push(JSON.stringify(estado));
    if (deshacer.length > 60) deshacer.shift();
    rehacer = [];
}
function volverPaso(desde, hacia) {
    if (!desde.length) return;
    hacia.push(JSON.stringify(estado));
    estado = JSON.parse(desde.pop());
    sel = null;
    pintar();
}

function pieza(f, id) { return f.piezas.filter(function (p) { return p.id === id; })[0]; }
function siguienteNumero(f, tipo) {
    for (var n = 1; n <= 5; n++) if (!pieza(f, tipo + n)) return n;
    return 0;
}
function anuncia(txt) { var l = $('anuncio'); l.textContent = ''; setTimeout(function () { l.textContent = txt; }, 30); }

// ── Zonas en palabras (para la descripción y los lectores de pantalla) ──
function zona(x, y) {
    var lado = x < 180 ? 'a la izquierda del dibujo' : x > 320 ? 'a la derecha del dibujo' : 'en el centro';
    var d = Math.hypot(x - ARO.x, y - ARO.y);
    var prof = d < 120 ? 'la zona del aro' : d < 237 ? 'la media distancia' : 'el perímetro, fuera de la línea de tres';
    return prof + ', ' + lado;
}
function nombrePieza(p) {
    if (p.tipo === 'A') return 'el ' + p.n;
    if (p.tipo === 'D') return 'el defensor ' + p.n;
    return NOMBRE_PIEZA[p.tipo].toLowerCase();
}
function describeFase(f, indice) {
    var partes = [];
    var ataque = f.piezas.filter(function (p) { return p.tipo === 'A'; }).length;
    var defensa = f.piezas.filter(function (p) { return p.tipo === 'D'; }).length;
    partes.push('Fase ' + (indice + 1) + ': ' + ataque + (ataque === 1 ? ' atacante' : ' atacantes') + (defensa ? ' y ' + defensa + (defensa === 1 ? ' defensor' : ' defensores') : '') + '.');
    f.flechas.forEach(function (a) {
        var de = pieza(f, a.de); if (!de) return;
        var dest = a.aId ? pieza(f, a.aId) : null;
        var verbo = TIPOS_FLECHA[a.tipo].verbo;
        var txt = nombrePieza(de);
        txt = txt.charAt(0).toUpperCase() + txt.slice(1) + ' ' + verbo;
        txt += dest ? (' a ' + nombrePieza(dest)).replace(/^ a el /, ' al ') : ' hacia ' + zona(a.a.x, a.a.y);
        partes.push(txt + '.');
    });
    if (partes.length === 1 && !f.piezas.length) partes.push('Fase vacía.');
    return partes.join(' ');
}

// ── Dibujo ────────────────────────────────────────────────────────────────
function el(nombre, attrs, padre) {
    var e = document.createElementNS(NS, nombre);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]);
    if (padre) padre.appendChild(e);
    return e;
}

function dibujaPista(svg, c) {
    var g = el('g', { fill: 'none', stroke: c.linea, 'stroke-width': 2, 'stroke-linecap': 'round' }, svg);
    el('rect', { x: 0, y: 0, width: W, height: H }, g);
    el('rect', { x: 170, y: 0, width: 160, height: 190 }, g);                       // pintura
    el('path', { d: 'M170 190 A60 60 0 0 0 330 190' }, g);                          // semicírculo del tiro libre (hacia fuera)
    el('path', { d: 'M190 190 A60 60 0 0 1 310 190', 'stroke-dasharray': '6 6' }, g);
    el('line', { x1: 220, y1: 40, x2: 280, y2: 40, 'stroke-width': 3 }, g);          // tablero
    el('circle', { cx: ARO.x, cy: ARO.y, r: 9 }, g);                                 // aro
    el('path', { d: 'M210 52 A40 40 0 0 0 290 52' }, g);                             // zona de no carga
    el('line', { x1: 30, y1: 0, x2: 30, y2: 141.5 }, g);                             // triple
    el('line', { x1: 470, y1: 0, x2: 470, y2: 141.5 }, g);
    el('path', { d: 'M30 141.5 A237.5 237.5 0 0 0 470 141.5' }, g);
    el('path', { d: 'M190 470 A60 60 0 0 1 310 470' }, g);                           // círculo central
}

function marcador(svg, id, color, bloqueo) {
    var m = el('marker', { id: id, viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, svg);
    if (!bloqueo) el('path', { d: 'M1 1 L9 5 L1 9 z', fill: color }, m);
}

function puntoFinal(f, a) {
    if (a.aId) { var p = pieza(f, a.aId); if (p) return { x: p.x, y: p.y }; }
    return a.a || null;
}

function trazoFlecha(tipo, x1, y1, x2, y2) {
    var dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L;
    if (tipo !== 'bote') return 'M' + x1 + ' ' + y1 + ' L' + x2 + ' ' + y2;
    var d = 'M' + x1 + ' ' + y1, n = Math.max(2, Math.floor(L / 7));
    for (var i = 1; i <= n; i++) {
        var t = i / n, off = (i % 2 ? 1 : -1) * 5 * (i === n ? 0 : 1);
        d += ' L' + redondea(x1 + dx * t - uy * off) + ' ' + redondea(y1 + dy * t + ux * off);
    }
    return d;
}

function dibujaFlechas(svg, f, c, interactivo) {
    f.flechas.forEach(function (a, i) {
        var de = pieza(f, a.de), fin = puntoFinal(f, a);
        if (!de || !fin) return;
        var dx = fin.x - de.x, dy = fin.y - de.y, L = Math.hypot(dx, dy);
        if (L < 4) return;
        var ux = dx / L, uy = dy / L;
        var x1 = de.x + ux * (R + 2), y1 = de.y + uy * (R + 2);
        var corta = a.aId ? R + 5 : 0;
        var x2 = fin.x - ux * corta, y2 = fin.y - uy * corta;
        var color = a.tipo === 'pase' ? c.pase : c.flecha;
        var esSel = interactivo && sel && sel.tipo === 'flecha' && sel.i === i;
        var g = el('g', { 'data-flecha': i }, svg);
        if (interactivo) {
            g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0'); g.style.cursor = 'pointer';
            g.setAttribute('aria-label', TIPOS_FLECHA[a.tipo].etiqueta + ' de ' + nombrePieza(de) + (a.aId ? '' : ' hacia ' + zona(fin.x, fin.y)));
            el('path', { d: trazoFlecha('corte', x1, y1, x2, y2), stroke: 'transparent', 'stroke-width': 22, fill: 'none' }, g);
        }
        var attrs = { d: trazoFlecha(a.tipo, x1, y1, x2, y2), fill: 'none', stroke: esSel ? c.sel : color, 'stroke-width': esSel ? 4 : 3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' };
        if (a.tipo === 'pase') attrs['stroke-dasharray'] = '9 7';
        if (a.tipo !== 'bloqueo') attrs['marker-end'] = 'url(#flecha-' + (esSel ? 'sel' : 'n') + ')';
        el('path', attrs, g);
        if (a.tipo === 'bloqueo') {
            el('line', { x1: x2 - uy * 14, y1: y2 + ux * 14, x2: x2 + uy * 14, y2: y2 - ux * 14, stroke: esSel ? c.sel : color, 'stroke-width': 4, 'stroke-linecap': 'round' }, g);
        }
    });
}

function dibujaPieza(svg, p, c, interactivo) {
    var g = el('g', { 'data-pieza': p.id, transform: 'translate(' + p.x + ' ' + p.y + ')' }, svg);
    var esSel = interactivo && sel && sel.tipo === 'pieza' && sel.id === p.id;
    if (interactivo) {
        g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0'); g.style.cursor = herramienta === 'mover' ? 'grab' : 'crosshair';
        g.setAttribute('aria-label', NOMBRE_PIEZA[p.tipo] + (p.n ? ' ' + p.n : '') + ', ' + zona(p.x, p.y));
        g.setAttribute('aria-pressed', esSel ? 'true' : 'false');
        el('circle', { r: 30, fill: 'transparent' }, g);
    }
    if (p.tipo === 'A') {
        el('circle', { r: R, fill: c.ataque, stroke: esSel ? c.sel : c.ataqueTxt, 'stroke-width': esSel ? 4 : 2 }, g);
        var t = el('text', { 'text-anchor': 'middle', 'dominant-baseline': 'central', 'font-size': 18, 'font-weight': 700, fill: c.ataqueTxt, 'font-family': 'Inter, sans-serif' }, g);
        t.textContent = String(p.n);
    } else if (p.tipo === 'D') {
        el('circle', { r: R, fill: c.fondo, stroke: esSel ? c.sel : c.defensa, 'stroke-width': esSel ? 4 : 3 }, g);
        var tx = el('text', { 'text-anchor': 'middle', 'dominant-baseline': 'central', 'font-size': 17, 'font-weight': 700, fill: c.defensaTxt, 'font-family': 'Inter, sans-serif' }, g);
        tx.textContent = 'X' + p.n;
    } else if (p.tipo === 'B') {
        el('circle', { r: 13, fill: c.balon, stroke: esSel ? c.sel : c.balonTrazo, 'stroke-width': esSel ? 4 : 2 }, g);
        // costuras: línea vertical, horizontal y dos curvas laterales
        el('path', { d: 'M-13 0 H13 M0 -13 V13 M-9.2 -9.2 Q-4.3 0 -9.2 9.2 M9.2 -9.2 Q4.3 0 9.2 9.2', stroke: c.balonTrazo, 'stroke-width': 1.3, fill: 'none', 'stroke-linecap': 'round' }, g);
    } else {
        el('path', { d: 'M0 -13 L11 10 L-11 10 Z', fill: c.cono, stroke: esSel ? c.sel : c.ataqueTxt, 'stroke-width': esSel ? 4 : 2 }, g);
    }
}

function renderEn(svg, f, c, interactivo, sinFlechas) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = el('defs', {}, svg);
    marcador(defs, 'flecha-n', c.flecha); marcador(defs, 'flecha-sel', c.sel);
    el('rect', { x: -10, y: -10, width: W + 20, height: H + 20, fill: c.fondo }, svg);
    dibujaPista(svg, c);
    if (!sinFlechas) dibujaFlechas(svg, f, c, interactivo);
    f.piezas.forEach(function (p) { if (p.tipo === 'C') dibujaPieza(svg, p, c, interactivo); });
    f.piezas.forEach(function (p) { if (p.tipo === 'D') dibujaPieza(svg, p, c, interactivo); });
    f.piezas.forEach(function (p) { if (p.tipo === 'A') dibujaPieza(svg, p, c, interactivo); });
    f.piezas.forEach(function (p) { if (p.tipo === 'B') dibujaPieza(svg, p, c, interactivo); });
}

function pintar() {
    var svg = $('pista');
    renderEn(svg, fase(), CLARO, true, false);
    if (fantasma) { el('circle', { cx: fantasma.x, cy: fantasma.y, r: 10, fill: 'none', stroke: CLARO.fantasma, 'stroke-width': 3, 'stroke-dasharray': '4 4', 'data-fantasma': '1' }, svg); }
    if (previa) {
        var o = pieza(fase(), previa.de);
        if (o) el('path', { d: trazoFlecha(previa.tipo, o.x, o.y, previa.x, previa.y), fill: 'none', stroke: CLARO.fantasma, 'stroke-width': 3, 'stroke-dasharray': '6 5', 'pointer-events': 'none' }, svg);
    }
    panelEstado();
}

function panelEstado() {
    $('fase-etq').textContent = 'Fase ' + (estado.actual + 1) + ' de ' + estado.fases.length;
    $('btn-fase-ant').disabled = estado.actual === 0 || !!reproduccion;
    $('btn-fase-sig').disabled = estado.actual >= estado.fases.length - 1 || !!reproduccion;
    $('btn-deshacer').disabled = !deshacer.length;
    $('btn-rehacer').disabled = !rehacer.length;
    $('btn-borrar').disabled = !sel;
    $('btn-nueva-fase').disabled = estado.fases.length >= MAX_FASES || !!reproduccion;
    $('btn-borrar-fase').disabled = estado.fases.length < 2 || !!reproduccion;
    $('btn-reproducir').textContent = reproduccion ? 'Parar' : 'Reproducir';
    $('btn-reproducir').setAttribute('aria-pressed', reproduccion ? 'true' : 'false');
    var f = fase();
    var a = f.piezas.filter(function (p) { return p.tipo === 'A'; }).length;
    var d = f.piezas.filter(function (p) { return p.tipo === 'D'; }).length;
    $('cuenta').textContent = a + (a === 1 ? ' atacante' : ' atacantes') + ' · ' + d + (d === 1 ? ' defensor' : ' defensores');
    var lista = $('descripcion'); lista.textContent = '';
    estado.fases.forEach(function (fs, i) {
        var li = document.createElement('li');
        if (i === estado.actual) li.className = 'actual';
        li.textContent = describeFase(fs, i).replace(/^Fase \d+: /, '');
        lista.appendChild(li);
    });
    document.querySelectorAll('[data-herr]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.herr === herramienta ? 'true' : 'false'); });
}

// ── Coordenadas ───────────────────────────────────────────────────────────
function aPista(ev) {
    var svg = $('pista'), pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    var m = svg.getScreenCTM();
    if (!m) return { x: 0, y: 0 };
    var q = pt.matrixTransform(m.inverse());
    return { x: redondea(acotar(q.x, 0, W)), y: redondea(acotar(q.y, 0, H)) };
}
function piezaBajo(ev) {
    var n = ev.target && ev.target.closest ? ev.target.closest('[data-pieza]') : null;
    return n ? n.getAttribute('data-pieza') : null;
}

// ── Añadir y quitar piezas ───────────────────────────────────────────────
function colocar(tipo, pos) {
    var f = fase(), p;
    if (tipo === 'B') {
        if (pieza(f, 'B')) { anuncia('Ya hay un balón en la pista; muévelo con la herramienta Mover.'); return; }
        p = { id: 'B', tipo: 'B', n: 0, x: pos.x, y: pos.y };
    } else if (tipo === 'C') {
        var conos = f.piezas.filter(function (q) { return q.tipo === 'C'; });
        if (conos.length >= MAX_CONOS) { anuncia('Máximo ' + MAX_CONOS + ' conos.'); return; }
        var k = 1; while (pieza(f, 'C' + k)) k++;
        p = { id: 'C' + k, tipo: 'C', n: k, x: pos.x, y: pos.y };
    } else {
        var n = siguienteNumero(f, tipo);
        if (!n) { anuncia('Ya hay cinco ' + (tipo === 'A' ? 'atacantes' : 'defensores') + ' en la pista.'); return; }
        p = { id: tipo + n, tipo: tipo, n: n, x: pos.x, y: pos.y };
    }
    guardarPaso();
    f.piezas.push(p);
    sel = { tipo: 'pieza', id: p.id };
    pintar();
    anuncia(NOMBRE_PIEZA[tipo] + (p.n ? ' ' + p.n : '') + ' colocado. ' + zona(p.x, p.y) + '.');
    var nodo = document.querySelector('[data-pieza="' + p.id + '"]'); if (nodo) nodo.focus();
}

function borrarSeleccion() {
    if (!sel) return;
    guardarPaso();
    var f = fase();
    if (sel.tipo === 'pieza') {
        f.piezas = f.piezas.filter(function (p) { return p.id !== sel.id; });
        f.flechas = f.flechas.filter(function (a) { return a.de !== sel.id && a.aId !== sel.id; });
        anuncia('Pieza borrada.');
    } else {
        f.flechas.splice(sel.i, 1);
        anuncia('Flecha borrada.');
    }
    sel = null;
    pintar();
}

function nuevaFlecha(tipo, de, destino) {
    var f = fase();
    if (f.flechas.length >= MAX_FLECHAS) { anuncia('Demasiadas flechas en esta fase.'); return; }
    var o = pieza(f, de); if (!o) return;
    var a = { tipo: tipo, de: de };
    if (destino.aId && destino.aId !== de) a.aId = destino.aId;
    else if (Math.hypot(destino.x - o.x, destino.y - o.y) > 24) a.a = { x: destino.x, y: destino.y };
    else return;
    guardarPaso();
    f.flechas.push(a);
    sel = { tipo: 'flecha', i: f.flechas.length - 1 };
    pintar();
    anuncia(describeFase({ piezas: f.piezas, flechas: [a] }, 0).replace(/^Fase 1: [^.]*\. /, ''));
}

// ── Ratón, táctil y lápiz ────────────────────────────────────────────────
var arrastre = null, previa = null, fantasma = null, destinoTeclado = null;

function alPulsar(ev) {
    if (reproduccion) return;
    if (ev.button !== undefined && ev.button !== 0) return;
    var id = piezaBajo(ev), pos = aPista(ev);
    var nodoFlecha = ev.target.closest ? ev.target.closest('[data-flecha]') : null;
    if (herramienta === 'mover') {
        if (id) {
            sel = { tipo: 'pieza', id: id };
            guardarPaso();
            arrastre = { id: id, movido: false };
            $('pista').setPointerCapture(ev.pointerId);
            pintar();
        } else if (nodoFlecha) {
            sel = { tipo: 'flecha', i: +nodoFlecha.getAttribute('data-flecha') };
            pintar();
        } else { sel = null; pintar(); }
        ev.preventDefault();
    } else if (herramienta === 'A' || herramienta === 'D' || herramienta === 'B' || herramienta === 'C') {
        if (id) { sel = { tipo: 'pieza', id: id }; pintar(); } else colocar(herramienta, pos);
        ev.preventDefault();
    } else if (TIPOS_FLECHA[herramienta]) {
        if (id) {
            previa = { tipo: herramienta, de: id, x: pos.x, y: pos.y };
            sel = { tipo: 'pieza', id: id };
            $('pista').setPointerCapture(ev.pointerId);
            pintar();
        } else anuncia('Empieza la flecha pulsando sobre una pieza.');
        ev.preventDefault();
    }
}
function alMover(ev) {
    var pos = aPista(ev);
    if (arrastre) {
        var p = pieza(fase(), arrastre.id);
        if (p) { p.x = pos.x; p.y = pos.y; arrastre.movido = true; pintar(); }
    } else if (previa) {
        previa.x = pos.x; previa.y = pos.y; pintar();
    }
}
function alSoltar(ev) {
    if (arrastre) {
        if (!arrastre.movido) deshacer.pop();
        else { var p = pieza(fase(), arrastre.id); if (p) anuncia(NOMBRE_PIEZA[p.tipo] + (p.n ? ' ' + p.n : '') + ': ' + zona(p.x, p.y) + '.'); }
        arrastre = null;
    } else if (previa) {
        var o = previa; previa = null;
        var bajo = null;
        var nodo = document.elementFromPoint(ev.clientX, ev.clientY);
        var g = nodo && nodo.closest ? nodo.closest('[data-pieza]') : null;
        if (g) bajo = g.getAttribute('data-pieza');
        nuevaFlecha(o.tipo, o.de, { x: o.x, y: o.y, aId: o.tipo === 'pase' ? bajo : null });
        pintar();
    }
}

// ── Teclado ──────────────────────────────────────────────────────────────
function alTeclear(ev) {
    var nodoP = ev.target.closest ? ev.target.closest('[data-pieza]') : null;
    var nodoF = ev.target.closest ? ev.target.closest('[data-flecha]') : null;
    var f = fase(), k = ev.key;
    if (destinoTeclado) {
        var paso = ev.shiftKey ? 40 : 10;
        if (k === 'ArrowLeft') fantasma.x = acotar(fantasma.x - paso, 0, W);
        else if (k === 'ArrowRight') fantasma.x = acotar(fantasma.x + paso, 0, W);
        else if (k === 'ArrowUp') fantasma.y = acotar(fantasma.y - paso, 0, H);
        else if (k === 'ArrowDown') fantasma.y = acotar(fantasma.y + paso, 0, H);
        else if (/^[1-5]$/.test(k) && destinoTeclado.tipo === 'pase') {
            var q = pieza(f, 'A' + k); if (q) { fantasma.x = q.x; fantasma.y = q.y; fantasma.aId = q.id; anuncia('Destino: atacante ' + k + '.'); }
        } else if (k === 'Enter') {
            var d = destinoTeclado; destinoTeclado = null;
            var f2 = fantasma; fantasma = null;
            nuevaFlecha(d.tipo, d.de, { x: f2.x, y: f2.y, aId: f2.aId || null });
            pintar(); ev.preventDefault(); return;
        } else if (k === 'Escape') { destinoTeclado = null; fantasma = null; anuncia('Flecha cancelada.'); pintar(); ev.preventDefault(); return; }
        else return;
        if (k.indexOf('Arrow') === 0) { delete fantasma.aId; anuncia(zona(fantasma.x, fantasma.y) + '.'); }
        pintar(); ev.preventDefault(); return;
    }
    if (nodoP) {
        var id = nodoP.getAttribute('data-pieza'), p = pieza(f, id);
        if (!p) return;
        if (k === 'Enter' || k === ' ') {
            ev.preventDefault();
            sel = { tipo: 'pieza', id: id };
            if (TIPOS_FLECHA[herramienta]) {
                destinoTeclado = { tipo: herramienta, de: id };
                fantasma = { x: p.x, y: p.y };
                anuncia('Elige el destino con las flechas del teclado' + (herramienta === 'pase' ? ' o con las teclas 1 a 5 para un atacante' : '') + '. Enter confirma, Escape cancela.');
            } else anuncia(NOMBRE_PIEZA[p.tipo] + (p.n ? ' ' + p.n : '') + ' seleccionado.');
            pintar(); refocalizar(id); return;
        }
        var dx = 0, dy = 0, paso2 = ev.shiftKey ? 40 : 10;
        if (k === 'ArrowLeft') dx = -paso2; else if (k === 'ArrowRight') dx = paso2;
        else if (k === 'ArrowUp') dy = -paso2; else if (k === 'ArrowDown') dy = paso2;
        if (dx || dy) {
            ev.preventDefault();
            guardarPaso();
            p.x = acotar(p.x + dx, 0, W); p.y = acotar(p.y + dy, 0, H);
            sel = { tipo: 'pieza', id: id };
            pintar(); refocalizar(id); anuncia(zona(p.x, p.y) + '.'); return;
        }
        if (k === 'Delete' || k === 'Backspace') { ev.preventDefault(); sel = { tipo: 'pieza', id: id }; borrarSeleccion(); $('pista').focus(); return; }
    } else if (nodoF && (k === 'Enter' || k === ' ')) {
        ev.preventDefault(); sel = { tipo: 'flecha', i: +nodoF.getAttribute('data-flecha') }; pintar(); anuncia('Flecha seleccionada. Suprimir la borra.');
    } else if (nodoF && (k === 'Delete' || k === 'Backspace')) {
        ev.preventDefault(); sel = { tipo: 'flecha', i: +nodoF.getAttribute('data-flecha') }; borrarSeleccion();
    }
}
function refocalizar(id) { var n = document.querySelector('[data-pieza="' + id + '"]'); if (n) n.focus(); }

// ── Fases y reproducción ─────────────────────────────────────────────────
function nuevaFase() {
    if (estado.fases.length >= MAX_FASES) return;
    guardarPaso();
    var f = fase(), nf = faseVacia();
    nf.piezas = clon(f.piezas);
    f.flechas.forEach(function (a) {
        var p = pieza(nf, a.de); if (!p) return;
        if (a.tipo === 'pase') {
            var r = a.aId ? pieza(nf, a.aId) : null, b = pieza(nf, 'B');
            if (r && b) { b.x = redondea(r.x + 14); b.y = redondea(r.y + 14); }
        } else {
            var fin = puntoFinal(f, a);
            if (fin) { p.x = fin.x; p.y = fin.y; }
        }
    });
    estado.fases.splice(estado.actual + 1, 0, nf);
    estado.actual++; sel = null;
    pintar();
    anuncia('Fase ' + (estado.actual + 1) + ' creada con las piezas donde terminaron los movimientos.');
}
function irA(i) { estado.actual = acotar(i, 0, estado.fases.length - 1); sel = null; pintar(); anuncia('Fase ' + (estado.actual + 1) + ' de ' + estado.fases.length + '. ' + describeFase(fase(), estado.actual)); }
function borrarFase() {
    if (estado.fases.length < 2) return;
    guardarPaso();
    estado.fases.splice(estado.actual, 1);
    estado.actual = acotar(estado.actual, 0, estado.fases.length - 1); sel = null;
    pintar();
}

function reproducir() {
    if (reproduccion) { paraReproduccion(); return; }
    if (estado.fases.length < 2) { anuncia('Crea al menos dos fases para reproducir.'); return; }
    sel = null;
    reproduccion = { t0: null, fase: 0, temporizador: null, copia: estado.actual };
    estado.actual = 0;
    pintar();
    if (reducirMovimiento) { pasoSinAnimacion(); return; }
    requestAnimationFrame(animar);
}
function paraReproduccion() {
    if (!reproduccion) return;
    clearTimeout(reproduccion.temporizador);
    var volver = reproduccion.copia; reproduccion = null;
    estado.actual = volver; pintar();
}
function pasoSinAnimacion() {
    reproduccion.temporizador = setTimeout(function () {
        if (!reproduccion) return;
        if (reproduccion.fase + 1 >= estado.fases.length) { paraReproduccion(); return; }
        reproduccion.fase++; estado.actual = reproduccion.fase; pintar(); pasoSinAnimacion();
    }, 1500);
}
function animar(t) {
    if (!reproduccion) return;
    if (reproduccion.t0 === null) reproduccion.t0 = t;
    var i = reproduccion.fase, A = estado.fases[i], B = estado.fases[i + 1];
    if (!B) { setTimeout(paraReproduccion, 700); return; }
    var k = acotar((t - reproduccion.t0) / 1100, 0, 1), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    var mezcla = { piezas: B.piezas.map(function (pb) {
        var pa = pieza(A, pb.id), q = clon(pb);
        if (pa) { q.x = pa.x + (pb.x - pa.x) * e; q.y = pa.y + (pb.y - pa.y) * e; }
        return q;
    }), flechas: [] };
    renderEn($('pista'), mezcla, CLARO, false, true);
    if (k >= 1) {
        reproduccion.fase++; reproduccion.t0 = null; estado.actual = reproduccion.fase;
        if (!estado.fases[reproduccion.fase + 1]) { pintar(); setTimeout(paraReproduccion, 900); return; }
        pintar(); setTimeout(function () { requestAnimationFrame(animar); }, 450); return;
    }
    requestAnimationFrame(animar);
}

// ── Guardar, abrir, exportar ─────────────────────────────────────────────
function almacen() { try { return JSON.parse(localStorage.getItem(CLAVE) || '[]'); } catch (e) { return []; } }
function escribeAlmacen(l) { try { localStorage.setItem(CLAVE, JSON.stringify(l)); return true; } catch (e) { return false; } }

function pintaGuardadas() {
    var s = $('guardadas'); s.textContent = '';
    var o0 = document.createElement('option'); o0.value = ''; o0.textContent = 'Jugadas guardadas…'; s.appendChild(o0);
    almacen().forEach(function (j, i) { var o = document.createElement('option'); o.value = String(i); o.textContent = j.nombre || 'Sin nombre'; s.appendChild(o); });
}

function nombreJugada() { return ($('nombre').value || '').trim().slice(0, 80) || 'Mi jugada'; }

function validar(j) { // sanea cualquier JSON de fuera: solo se aceptan tipos y rangos conocidos
    if (!j || typeof j !== 'object' || !Array.isArray(j.fases) || !j.fases.length || j.fases.length > MAX_FASES) return null;
    var num = function (v, a, b) { return typeof v === 'number' && isFinite(v) ? acotar(v, a, b) : null; };
    var salida = { nombre: typeof j.nombre === 'string' ? j.nombre.slice(0, 80) : '', fases: [], actual: 0 };
    for (var i = 0; i < j.fases.length; i++) {
        var fs = j.fases[i], nf = faseVacia();
        if (!fs || !Array.isArray(fs.piezas) || fs.piezas.length > 30) return null;
        var vistos = {};
        for (var k = 0; k < fs.piezas.length; k++) {
            var p = fs.piezas[k]; if (!p || ['A', 'D', 'B', 'C'].indexOf(p.tipo) < 0) return null;
            var n = p.tipo === 'B' ? 0 : Math.round(num(p.n, 1, 9) || 0);
            var id = p.tipo === 'B' ? 'B' : p.tipo + n, x = num(p.x, 0, W), y = num(p.y, 0, H);
            if (x === null || y === null || vistos[id] || (p.tipo !== 'B' && !n)) return null;
            vistos[id] = 1; nf.piezas.push({ id: id, tipo: p.tipo, n: n, x: x, y: y });
        }
        var fl = Array.isArray(fs.flechas) ? fs.flechas.slice(0, MAX_FLECHAS) : [];
        fl.forEach(function (a) {
            if (!a || !TIPOS_FLECHA[a.tipo] || !vistos[a.de]) return;
            var r = { tipo: a.tipo, de: a.de };
            if (typeof a.aId === 'string' && vistos[a.aId]) r.aId = a.aId;
            else if (a.a && num(a.a.x, 0, W) !== null && num(a.a.y, 0, H) !== null) r.a = { x: num(a.a.x, 0, W), y: num(a.a.y, 0, H) };
            else return;
            nf.flechas.push(r);
        });
        salida.fases.push(nf);
    }
    return salida;
}
function cargaJugada(j) {
    estado = j; sel = null; deshacer = []; rehacer = [];
    $('nombre').value = j.nombre || '';
    pintar();
}

function descarga(blob, nombre) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = nombre;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
}
function nombreArchivo() { return nombreJugada().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'jugada'; }

function pngDeFase(f, ancho, cb) {
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('xmlns', NS); svg.setAttribute('viewBox', '-10 -10 ' + (W + 20) + ' ' + (H + 20));
    var alto = Math.round(ancho * (H + 20) / (W + 20));
    svg.setAttribute('width', ancho); svg.setAttribute('height', alto);
    renderEn(svg, f, IMPRESION, false, false);
    var url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml;charset=utf-8' }));
    var img = new Image();
    img.onload = function () {
        var c = document.createElement('canvas'); c.width = ancho; c.height = alto;
        var ctx = c.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, ancho, alto); ctx.drawImage(img, 0, 0, ancho, alto);
        URL.revokeObjectURL(url);
        c.toBlob(cb, 'image/png');
    };
    img.onerror = function () { URL.revokeObjectURL(url); anuncia('No se pudo generar la imagen.'); };
    img.src = url;
}

function preparaImpresion() {
    var cont = $('impresion'); cont.textContent = '';
    var t = document.createElement('h1'); t.textContent = nombreJugada(); cont.appendChild(t);
    estado.fases.forEach(function (f, i) {
        var fig = document.createElement('figure');
        var svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('viewBox', '-10 -10 ' + (W + 20) + ' ' + (H + 20)); svg.setAttribute('role', 'img');
        svg.setAttribute('aria-label', describeFase(f, i));
        renderEn(svg, f, IMPRESION, false, false);
        var cap = document.createElement('figcaption'); cap.textContent = describeFase(f, i);
        fig.appendChild(svg); fig.appendChild(cap); cont.appendChild(fig);
    });
}

// ── Arranque ─────────────────────────────────────────────────────────────
function plantilla(nombre) {
    var P = function (t, n, x, y) { return { id: t === 'B' ? 'B' : t + n, tipo: t, n: n, x: x, y: y }; };
    var f = faseVacia();
    if (nombre === 'cinco-fuera') {
        f.piezas = [P('A', 1, 250, 380), P('A', 2, 90, 250), P('A', 3, 410, 250), P('A', 4, 130, 140), P('A', 5, 370, 140), P('B', 0, 270, 395)];
    } else if (nombre === '4-1') {
        f.piezas = [P('A', 1, 250, 330), P('A', 2, 60, 200), P('A', 3, 440, 200), P('A', 4, 160, 150), P('A', 5, 340, 150), P('B', 0, 270, 345)];
    } else if (nombre === '2c1') {
        f.piezas = [P('A', 1, 150, 350), P('A', 2, 350, 350), P('D', 1, 250, 220), P('B', 0, 170, 365)];
    }
    var j = jugadaNueva(); j.fases = [f]; return j;
}

function iniciar() {
    estado = jugadaNueva();
    var svg = $('pista');
    svg.addEventListener('pointerdown', alPulsar);
    svg.addEventListener('pointermove', alMover);
    svg.addEventListener('pointerup', alSoltar);
    svg.addEventListener('pointercancel', function () { arrastre = null; previa = null; pintar(); });
    svg.addEventListener('keydown', alTeclear);

    document.querySelectorAll('[data-herr]').forEach(function (b) {
        b.addEventListener('click', function () {
            herramienta = b.dataset.herr; destinoTeclado = null; fantasma = null; previa = null;
            var texto = b.getAttribute('data-ayuda') || b.textContent.trim();
            $('ayuda-herr').textContent = texto;
            panelEstado(); pintar();
            anuncia('Herramienta: ' + b.textContent.trim() + '.');
        });
    });
    $('btn-deshacer').addEventListener('click', function () { volverPaso(deshacer, rehacer); });
    $('btn-rehacer').addEventListener('click', function () { volverPaso(rehacer, deshacer); });
    $('btn-borrar').addEventListener('click', borrarSeleccion);
    $('btn-fase-ant').addEventListener('click', function () { irA(estado.actual - 1); });
    $('btn-fase-sig').addEventListener('click', function () { irA(estado.actual + 1); });
    $('btn-nueva-fase').addEventListener('click', nuevaFase);
    $('btn-borrar-fase').addEventListener('click', borrarFase);
    $('btn-reproducir').addEventListener('click', reproducir);
    $('btn-limpiar').addEventListener('click', function () {
        if (!fase().piezas.length) return;
        guardarPaso(); fase().piezas = []; fase().flechas = []; sel = null; pintar(); anuncia('Fase vaciada. Puedes deshacer.');
    });
    $('plantillas').addEventListener('change', function (e) {
        var v = e.target.value; if (!v) return;
        guardarPaso(); var j = plantilla(v); j.nombre = estado.nombre; estado = j; sel = null; e.target.value = ''; pintar(); anuncia('Plantilla colocada.');
    });
    $('btn-guardar').addEventListener('click', function () {
        var l = almacen(), j = clon(estado); j.nombre = nombreJugada(); j.actual = 0;
        var i = l.map(function (x) { return x.nombre; }).indexOf(j.nombre);
        if (i >= 0) l[i] = j; else { if (l.length >= 50) { anuncia('Hay demasiadas jugadas guardadas; borra alguna.'); return; } l.push(j); }
        anuncia(escribeAlmacen(l) ? 'Jugada guardada en este navegador.' : 'No se pudo guardar: el navegador bloquea el almacenamiento. Usa Exportar.');
        pintaGuardadas();
    });
    $('btn-abrir').addEventListener('click', function () {
        var i = $('guardadas').value; if (i === '') return;
        var j = validar(almacen()[+i]); if (!j) { anuncia('Esa jugada guardada no es válida.'); return; }
        cargaJugada(j); anuncia('Jugada abierta.');
    });
    $('btn-eliminar').addEventListener('click', function () {
        var i = $('guardadas').value; if (i === '') return;
        var l = almacen(); l.splice(+i, 1); escribeAlmacen(l); pintaGuardadas(); anuncia('Jugada guardada eliminada.');
    });
    $('btn-json').addEventListener('click', function () {
        var j = clon(estado); j.nombre = nombreJugada();
        descarga(new Blob([JSON.stringify(j, null, 1)], { type: 'application/json' }), nombreArchivo() + '.json');
    });
    $('archivo').addEventListener('change', function (e) {
        var fch = e.target.files[0]; if (!fch) return;
        if (fch.size > 300000) { anuncia('El archivo es demasiado grande.'); e.target.value = ''; return; }
        var lector = new FileReader();
        lector.onload = function () {
            var j = null; try { j = validar(JSON.parse(lector.result)); } catch (err) { j = null; }
            if (!j) anuncia('El archivo no es una jugada válida.'); else { cargaJugada(j); anuncia('Jugada importada.'); }
        };
        lector.readAsText(fch); e.target.value = '';
    });
    $('btn-png').addEventListener('click', function () {
        pngDeFase(fase(), 1200, function (b) { if (b) descarga(b, nombreArchivo() + '-fase-' + (estado.actual + 1) + '.png'); });
    });
    $('btn-imprimir').addEventListener('click', function () { preparaImpresion(); window.print(); });
    $('nombre').addEventListener('input', function () { estado.nombre = nombreJugada(); });
    document.addEventListener('keydown', function (ev) {
        var t = ev.target;
        if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return;
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'z') { ev.preventDefault(); volverPaso(deshacer, rehacer); }
        else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'y') { ev.preventDefault(); volverPaso(rehacer, deshacer); }
    });
    iniciaBiblioteca();
    pintaGuardadas();
    pintar();
}

// ── Biblioteca de jugadas (catálogo estático del servidor) ────────────────
var biblioteca = [];
function iniciaBiblioteca() {
    var lista = $('bib-lista'), edad = $('bib-edad'), desc = $('bib-desc');
    function rellena() {
        lista.textContent = '';
        var o0 = document.createElement('option'); o0.value = ''; o0.textContent = 'Elegir…'; lista.appendChild(o0);
        biblioteca.forEach(function (j, i) {
            if (edad.value && j.edades.indexOf(edad.value) < 0) return;
            var o = document.createElement('option'); o.value = String(i); o.textContent = j.nombre; lista.appendChild(o);
        });
        desc.textContent = lista.options.length > 1 ? '' : 'No hay jugadas para esta categoría.';
    }
    edad.addEventListener('change', rellena);
    lista.addEventListener('change', function () { desc.textContent = lista.value === '' ? '' : biblioteca[+lista.value].descripcion; });
    $('btn-bib-abrir').addEventListener('click', function () {
        if (lista.value === '') { anuncia('Elige primero una jugada de la biblioteca.'); return; }
        var j = biblioteca[+lista.value]; guardarPaso();
        var v = validar(j.crudo); v.nombre = j.nombre;
        estado = v; sel = null; $('nombre').value = j.nombre; pintar(); anuncia('Jugada «' + j.nombre + '» abierta, ' + estado.fases.length + ' fases.');
    });
    fetch($('bib-lista').getAttribute('data-url'), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (datos) {
        biblioteca = (Array.isArray(datos) ? datos : []).map(function (c) {
            return { crudo: c, nombre: String(c.nombre || '').slice(0, 120), descripcion: String(c.descripcion || '').slice(0, 600), edades: Array.isArray(c.edades) ? c.edades.map(String) : [] };
        }).filter(function (j) { return validar(j.crudo); });
        rellena();
    }).catch(function () { lista.firstChild.textContent = 'No se pudo cargar la biblioteca'; });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
})();
