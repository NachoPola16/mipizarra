/* Editor de jugadas de MiPizarra. Todo ocurre en el navegador: no llama a la API ni a ningún modelo.
   Modelo: una jugada = fases; cada fase = piezas con posición + flechas (pase, bote, corte, bloqueo).
   Medio campo en unidades de 0.1 m... en realidad en «pies × 10»: ancho 500, largo 470, aro en (250, 52). */
(function () {
'use strict';

var NS = 'http://www.w3.org/2000/svg';
var W = 500, H = 470, ARO = { x: 250, y: 52 };
var R = 16;                                   // radio de una pieza
var MAX_FASES = 12, MAX_FLECHAS = 40, MAX_CONOS = 8, CURVA_MAX = 0.8;
var CLAVE = 'mipizarra.jugadas.v1';
var escalaTrazo = 1;                          // 2 en las miniaturas de la biblioteca: el mismo dibujo, con el trazo más grueso

var TIPOS_FLECHA = {
    pase:    { etiqueta: 'Pase',    verbo: 'pasa' },
    bote:    { etiqueta: 'Bote',    verbo: 'bota' },
    corte:   { etiqueta: 'Corte',   verbo: 'se mueve' },
    bloqueo: { etiqueta: 'Bloqueo', verbo: 'bloquea' }
};
var NOMBRE_PIEZA = { A: 'Atacante', D: 'Defensor', B: 'Balón', C: 'Cono' };

var CLARO = { // tema de pantalla
    fondo: '#2a2118', linea: '#9c9186', ataque: '#e8752c', ataqueTxt: '#15120e', defensa: '#d8d0c4', defensaTxt: '#d8d0c4',
    balon: '#ffc78a', balonTrazo: '#3b2412', cono: '#e8752c', flecha: '#f2ede4', pase: '#f2ede4', sel: '#f2ede4', selFlecha: '#e8752c', fantasma: '#e8752c'
};
var IMPRESION = { // tema para PNG e impresión: tinta sobre blanco
    fondo: '#ffffff', linea: '#666666', ataque: '#e8752c', ataqueTxt: '#15120e', defensa: '#1b1b1f', defensaTxt: '#1b1b1f',
    balon: '#ffd9a8', balonTrazo: '#1b1b1f', cono: '#e8752c', flecha: '#1b1b1f', pase: '#1b1b1f', sel: '#1b1b1f', selFlecha: '#1b1b1f', fantasma: '#1b1b1f'
};

var $ = function (id) { return document.getElementById(id); };
var reducirMovimiento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── Estado ────────────────────────────────────────────────────────────────
var estado, herramienta = 'mover', sel = null, deshacer = [], rehacer = [], reproduccion = null;

function faseVacia() { return { piezas: [], flechas: [] }; }
// etiquetas: 'letra' (A–E, para que no se confundan con las posiciones 1–5) o 'num' (números de posición)
function jugadaNueva() { return { nombre: '', etiquetas: 'letra', fases: [faseVacia()], actual: 0 }; }
function etiquetaAtacante(n) { return estado.etiquetas === 'num' ? String(n) : 'ABCDEFGHI'.charAt(n - 1); }
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
    if (p.tipo === 'A') return estado.etiquetas === 'num' ? 'el ' + p.n : 'el jugador ' + etiquetaAtacante(p.n);
    if (p.tipo === 'D') return 'el defensor ' + p.n;
    return NOMBRE_PIEZA[p.tipo].toLowerCase();
}
function describeFase(f, indice) {
    var partes = [];
    var ataque = f.piezas.filter(function (p) { return p.tipo === 'A'; }).length;
    var defensa = f.piezas.filter(function (p) { return p.tipo === 'D'; }).length;
    partes.push('Fase ' + (indice + 1) + ': ' + ataque + (ataque === 1 ? ' atacante' : ' atacantes') + (defensa ? ' y ' + defensa + (defensa === 1 ? ' defensor' : ' defensores') : '') + '.');
    f.flechas.forEach(function (a, i) {
        var de = pieza(f, a.de); if (!de) return;
        if (haySiguiente(f, i)) return;                    // los tramos intermedios no se repiten en el texto
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
    el('path', { d: 'M170 190 A80 80 0 0 0 330 190' }, g);                          // semicírculo del tiro libre (hacia fuera)
    el('path', { d: 'M170 190 A80 80 0 0 1 330 190', 'stroke-dasharray': '6 6' }, g);   // el de dentro, discontinuo: mismo radio
    el('line', { x1: 220, y1: 40, x2: 280, y2: 40, 'stroke-width': 3 }, g);          // tablero
    el('circle', { cx: ARO.x, cy: ARO.y, r: 9 }, g);                                 // aro
    el('path', { d: 'M210 52 A40 40 0 0 0 290 52' }, g);                             // zona de no carga
    el('line', { x1: 30, y1: 0, x2: 30, y2: 141.5 }, g);                             // triple
    el('line', { x1: 470, y1: 0, x2: 470, y2: 141.5 }, g);
    el('path', { d: 'M30 141.5 A237.5 237.5 0 0 0 470 141.5' }, g);
    el('path', { d: 'M190 470 A60 60 0 0 1 310 470' }, g);                           // círculo central
}

function marcador(svg, id, color, bloqueo) {
    var m = el('marker', { id: id, viewBox: '0 0 10 10', refX: 6.5, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' }, svg);
    if (!bloqueo) el('path', { d: 'M1 1 L9 5 L1 9 z', fill: color }, m);
}

function puntoFinal(f, a) {
    if (a.aId) {
        var p = pieza(f, a.aId);
        if (p && a.tipo === 'pase') {         // pase a un jugador que corre en la misma fase: va hacia donde llega, no hacia donde sale
            f.flechas.some(function (m) {         // solo cuentan los movimientos que van antes del pase en la lista
                if (m === a) return true;
                if (m.de === a.aId && m.tipo !== 'pase' && m.a) p = m.a;
                return false;
            });
            return { x: p.x, y: p.y };
        }
        if (p) return { x: p.x, y: p.y };
    }
    return a.a || null;
}

// Punto de una curva cuadrática (o recta, si no hay punto de control) y su tangente.
function puntoCurva(x1, y1, x2, y2, cx, cy, t) {
    if (typeof cx !== 'number') { cx = (x1 + x2) / 2; cy = (y1 + y2) / 2; }
    var m = 1 - t;
    var x = m * m * x1 + 2 * m * t * cx + t * t * x2, y = m * m * y1 + 2 * m * t * cy + t * t * y2;
    var tx = 2 * m * (cx - x1) + 2 * t * (x2 - cx), ty = 2 * m * (cy - y1) + 2 * t * (y2 - cy), tl = Math.hypot(tx, ty) || 1;
    return { x: x, y: y, tx: tx / tl, ty: ty / tl };
}

// Tramos encadenados: una flecha con `sigue` nace donde acabó la anterior de la misma pieza (un recorrido con varios giros).
function inicioDe(f, i) {
    var a = f.flechas[i], de = pieza(f, a.de);
    if (a.sigue) for (var k = i - 1; k >= 0; k--) { var m = f.flechas[k]; if (m.de === a.de && m.tipo !== 'pase') return puntoFinal(f, m); }
    return de ? { x: de.x, y: de.y } : null;
}
function haySiguiente(f, i) {
    var a = f.flechas[i];
    for (var k = i + 1; k < f.flechas.length; k++) if (f.flechas[k].de === a.de && f.flechas[k].sigue && f.flechas[k].tipo !== 'pase') return true;
    return false;
}

// Trazo de una flecha. (cx, cy) es el punto de control de una curva cuadrática; sin él, la flecha es recta.
// El bote es una onda suave (una curva por cada media onda) que nace y muere sobre el eje para que la punta apunte bien.
function trazoFlecha(tipo, x1, y1, x2, y2, cx, cy) {
    var curva = typeof cx === 'number';
    if (tipo !== 'bote') return curva ? 'M' + x1 + ' ' + y1 + ' Q' + cx + ' ' + cy + ' ' + x2 + ' ' + y2 : 'M' + x1 + ' ' + y1 + ' L' + x2 + ' ' + y2;
    var L = Math.hypot(x2 - x1, y2 - y1) || 1, media = 12 * escalaTrazo, n = Math.max(2, Math.round(L / media)), AMP = 5.5 * escalaTrazo;
    var d = 'M' + redondea(x1) + ' ' + redondea(y1), ant = puntoCurva(x1, y1, x2, y2, cx, cy, 0);
    for (var i = 1; i <= n; i++) {
        var p = puntoCurva(x1, y1, x2, y2, cx, cy, i / n), m = puntoCurva(x1, y1, x2, y2, cx, cy, (i - 0.5) / n);
        // la amplitud crece al empezar y se apaga al acabar; la última media onda queda sobre el eje
        var ventana = Math.min(1, i / 2, (n - i + 0.5) / 1.5), signo = i % 2 ? 1 : -1;
        var amp = i === n ? 0 : AMP * 2 * signo * Math.max(0.3, ventana);
        d += ' Q' + redondea(m.x - m.ty * amp) + ' ' + redondea(m.y + m.tx * amp) + ' ' + redondea(p.x) + ' ' + redondea(p.y);
    }
    return d;
}

// Dibuja las flechas de una fase. `extra` (opcional): { prog: [0..1 por flecha], dim: true } para la reproducción.
var barrasArriba = [];                        // barras de bloqueo de la fase que se está dibujando (se pintan sobre las fichas)

// Defensores automáticos («Mostrar defensores»): uno por atacante, entre él y el aro y un poco hacia el balón.
// Solo si la fase no trae defensores propios. No son piezas de la jugada: se calculan al dibujar.
var mostrarDef = false;
function unit(dx, dy) { var l = Math.hypot(dx, dy) || 1; return { x: dx / l, y: dy / l }; }
function conDefensores(piezas) {
    if (!mostrarDef || piezas.some(function (p) { return p.tipo === 'D'; })) return piezas;
    var b = piezas.filter(function (p) { return p.tipo === 'B'; })[0], salida = piezas.slice(), portador = null, dm = 44;
    if (b) piezas.forEach(function (p) { if (p.tipo !== 'A') return; var d = Math.hypot(p.x - b.x, p.y - b.y); if (d < dm) { dm = d; portador = p.id; } });
    piezas.forEach(function (p) {
        if (p.tipo !== 'A') return;
        var h = unit(ARO.x - p.x, ARO.y - p.y), v = h;
        if (b && p.id !== portador) { var u = unit(b.x - p.x, b.y - p.y); v = unit(h.x * 0.7 + u.x * 0.3, h.y * 0.7 + u.y * 0.3); }
        salida.push({ id: 'D' + p.n, tipo: 'D', n: p.n, x: acotar(p.x + v.x * 38, 0, W), y: acotar(p.y + v.y * 38, 0, H), auto: true });
    });
    return salida;
}

// Dónde acaba cada pieza que se mueve en la fase (primer movimiento y sus tramos encadenados).
function finalesDe(f) {
    var fin = {}, visto = {};
    f.flechas.forEach(function (a) {
        if (a.tipo === 'pase' || (visto[a.de] && !a.sigue)) return;
        visto[a.de] = true;
        var q = puntoFinal(f, a); if (q) fin[a.de] = q;
    });
    return fin;
}
function distSegmento(p, a, b) {
    var dx = b.x - a.x, dy = b.y - a.y, l2 = dx * dx + dy * dy, t = l2 ? acotar(((p.x - a.x) * dx + (p.y - a.y) * dy) / l2, 0, 1) : 0;
    return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

// Centro de la marca (la T) de un bloqueo. Con defensor en la fase, la marca se apoya en el defensor del jugador que usa el
// bloqueo (el atacante cuyo recorrido pasa más cerca). Sin defensor, va un poco más allá de donde queda el bloqueador, en un
// hueco libre: sin pisar otras fichas (donde empiezan o donde acaban) ni otras marcas.
function marcaBloqueo(f, a, s, fin, finales, marcas) {
    var ataq = f.piezas.filter(function (p) { return p.tipo === 'A' && p.id !== a.de; });
    if (a.aId) { var o = pieza(f, a.aId), u0 = o ? unit(o.x - s.x, o.y - s.y) : null; if (o) return { x: o.x - u0.x * (R + 8), y: o.y - u0.y * (R + 8) }; }
    var defs = f.piezas.filter(function (p) { return p.tipo === 'D'; });
    if (defs.length && ataq.length) {
        var uso = null, dm = 1e9;
        ataq.forEach(function (p) { var q = finales[p.id], d = q ? distSegmento(fin, p, q) : Math.hypot(p.x - fin.x, p.y - fin.y); if (d < dm) { dm = d; uso = p; } });
        var dd = null, dn = 1e9;
        defs.forEach(function (q) { var d = Math.hypot(q.x - uso.x, q.y - uso.y); if (d < dn) { dn = d; dd = q; } });
        if (dd && dn < 80 && Math.hypot(dd.x - fin.x, dd.y - fin.y) < 110) {
            var u = unit(dd.x - fin.x, dd.y - fin.y);
            return { x: dd.x - u.x * (R + 8), y: dd.y - u.y * (R + 8) };
        }
    }
    var d0 = Math.hypot(fin.x - s.x, fin.y - s.y) < 1 ? { x: 0, y: 1 } : unit(fin.x - s.x, fin.y - s.y);
    var libre = function (t) {
        if (marcas.some(function (m) { return Math.hypot(m.x - t.x, m.y - t.y) < 30; })) return false;
        return !f.piezas.some(function (p) {
            if (p.tipo === 'B' || p.id === a.de) return false;
            var q = finales[p.id];
            return Math.hypot(p.x - t.x, p.y - t.y) < R + 12 || (q && Math.hypot(q.x - t.x, q.y - t.y) < R + 12);
        });
    };
    var primero = null;
    var giros = [0, 25, -25, 50, -50, 80, -80, 115, -115, 150, -150, 180];
    for (var g = 0; g < giros.length; g++) {
        var an = giros[g] * Math.PI / 180, co = Math.cos(an), si = Math.sin(an);
        var t = { x: acotar(fin.x + (d0.x * co - d0.y * si) * (R + 8), 0, W), y: acotar(fin.y + (d0.x * si + d0.y * co) * (R + 8), 0, H) };
        if (!primero) primero = t;
        if (libre(t)) return t;
    }
    return primero;
}

function dibujaFlechas(svg, f, c, interactivo, extra) {
    extra = extra || {};
    f = { piezas: conDefensores(f.piezas), flechas: f.flechas };
    var balon = pieza(f, 'B');
    var finales = finalesDe(f), marcas = [], centros = {};
    f.flechas.forEach(function (a, i) {            // primero todas las marcas de bloqueo: cada una esquiva a las anteriores
        if (a.tipo !== 'bloqueo') return;
        var s = inicioDe(f, i), fin = puntoFinal(f, a);
        if (!s || !fin) return;
        centros[i] = marcaBloqueo(f, a, s, fin, finales, marcas); marcas.push(centros[i]);
    });
    f.flechas.forEach(function (a, i) {
        var de = inicioDe(f, i), fin = puntoFinal(f, a), pDe = pieza(f, a.de);
        if (!de || !fin) return;
        var k = extra.prog ? extra.prog[i] : 1;
        if (k <= 0) return;
        if (a.tipo === 'bloqueo') { dibujaBloqueo(svg, f, c, interactivo, extra, a, i, de, centros[i], k); return; }
        var dx = fin.x - de.x, dy = fin.y - de.y, L = Math.hypot(dx, dy);
        if (L < 4) return;
        // curva: el punto de control se separa del centro de la cuerda un `curva` por ciento de su largo, hacia la izquierda de la marcha
        var cv = a.curva || 0;
        var cx = (de.x + fin.x) / 2 - dy * cv, cy = (de.y + fin.y) / 2 + dx * cv;
        var t1 = Math.hypot(cx - de.x, cy - de.y) || 1, t2 = Math.hypot(fin.x - cx, fin.y - cy) || 1;
        var u1x = (cx - de.x) / t1, u1y = (cy - de.y) / t1, ux = (fin.x - cx) / t2, uy = (fin.y - cy) / t2;
        // el bote arranca más lejos si el jugador lleva el balón al lado, para no pisarlo
        var conBalon = a.tipo === 'bote' && balon && Math.hypot(balon.x - de.x, balon.y - de.y) < 36;
        var salida = a.sigue ? 0 : (conBalon ? R + 24 : R + 3);
        if (!a.sigue && L < salida + 12) salida = R + 3;
        var x1 = de.x + u1x * salida, y1 = de.y + u1y * salida;
        var corta = a.aId ? R + 8 : 0;
        var x2 = fin.x - ux * corta, y2 = fin.y - uy * corta;
        var ctl = cv ? [cx, cy] : [];
        var color = a.tipo === 'pase' ? c.pase : c.flecha;
        var esSel = interactivo && sel && sel.tipo === 'flecha' && sel.i === i;
        var g = el('g', { 'data-flecha': i }, svg);
        if (extra.dim) g.setAttribute('opacity', '0.35');
        if (interactivo) {
            g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0'); g.style.cursor = 'pointer';
            g.setAttribute('aria-label', TIPOS_FLECHA[a.tipo].etiqueta + ' de ' + nombrePieza(pDe) + (a.aId ? '' : ' hacia ' + zona(fin.x, fin.y)));
            el('path', { d: trazoFlecha('corte', x1, y1, x2, y2, ctl[0], ctl[1]), stroke: 'transparent', 'stroke-width': 22, fill: 'none' }, g);
        }
        var d = trazoFlecha(a.tipo, x1, y1, x2, y2, ctl[0], ctl[1]);
        var comun = { d: d, fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' };
        var dibujando = k < 1;
        if (a.tipo === 'pase') {               // el pase es discontinuo: aparece de golpe con un fundido
            comun['stroke-dasharray'] = (9 * escalaTrazo) + ' ' + (7 * escalaTrazo);
            if (dibujando) g.setAttribute('opacity', String(Math.min(1, k * 3)));
        } else if (dibujando) {                // trazo progresivo: la flecha se dibuja en el momento
            comun.pathLength = 1; comun['stroke-dasharray'] = '1'; comun['stroke-dashoffset'] = String(1 - k);
        }
        // funda del color de la pista debajo: la flecha no se mezcla con las líneas ni con otras flechas que cruza
        var funda = {}; for (var q in comun) funda[q] = comun[q];
        funda.stroke = c.fondo; funda['stroke-width'] = 8 * escalaTrazo; funda.opacity = '.9';
        el('path', funda, g);
        var attrs = {}; for (var w in comun) attrs[w] = comun[w];
        attrs.stroke = esSel ? c.selFlecha : color; attrs['stroke-width'] = (esSel ? 4 : 3) * escalaTrazo;
        if (k >= 0.85 && !haySiguiente(f, i)) attrs['marker-end'] = 'url(#flecha-' + (esSel ? 'sel' : 'n') + ')';
        el('path', attrs, g);
    });
}

// Bloqueo: una línea recta que sale del borde de la ficha (de donde está ahora, no de donde empezó) y acaba en la T.
function dibujaBloqueo(svg, f, c, interactivo, extra, a, i, ini, T, k) {
    if (!T) return;
    var act = extra.act ? pieza(extra.act, a.de) : null, s = act ? { x: act.x, y: act.y } : ini;
    var esSel = interactivo && sel && sel.tipo === 'flecha' && sel.i === i, col = esSel ? c.selFlecha : c.flecha;
    var dist = Math.hypot(T.x - s.x, T.y - s.y), u = unit(T.x - s.x, T.y - s.y);
    var g = el('g', { 'data-flecha': i }, svg);
    if (extra.dim) g.setAttribute('opacity', '0.35');
    if (interactivo) {
        g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0'); g.style.cursor = 'pointer';
        g.setAttribute('aria-label', 'Bloqueo de ' + nombrePieza(pieza(f, a.de)) + (a.aId ? '' : ' hacia ' + zona(T.x, T.y)));
    }
    var largo = dist - (R + 3);
    if (largo > 4) {
        var cola = Math.min(1, k / 0.85), x1 = s.x + u.x * (R + 3), y1 = s.y + u.y * (R + 3);
        var d = 'M' + x1 + ' ' + y1 + ' L' + (x1 + u.x * largo * cola) + ' ' + (y1 + u.y * largo * cola);
        if (interactivo) el('path', { d: d, stroke: 'transparent', 'stroke-width': 22, fill: 'none' }, g);
        el('path', { d: d, fill: 'none', 'stroke-linecap': 'butt', stroke: c.fondo, 'stroke-width': 8 * escalaTrazo, opacity: '.9' }, g);
        el('path', { d: d, fill: 'none', 'stroke-linecap': 'butt', stroke: col, 'stroke-width': (esSel ? 4 : 3) * escalaTrazo }, g);
    }
    if (k >= 0.85) {
        var m = 14 * escalaTrazo;
        barrasArriba.push({ x1: T.x - u.y * m, y1: T.y + u.x * m, x2: T.x + u.y * m, y2: T.y - u.x * m, stroke: col, 'stroke-width': 4 * escalaTrazo, 'stroke-linecap': 'round', 'pointer-events': 'none', opacity: extra.dim ? '0.35' : '1' });
    }
}

function dibujaPieza(svg, p, c, interactivo) {
    var g = el('g', p.auto ? { transform: 'translate(' + p.x + ' ' + p.y + ')', 'pointer-events': 'none' } : { 'data-pieza': p.id, transform: 'translate(' + p.x + ' ' + p.y + ')' }, svg);
    if (p.auto) interactivo = false;
    var esSel = interactivo && sel && sel.tipo === 'pieza' && sel.id === p.id;
    if (interactivo) {
        g.setAttribute('role', 'button'); g.setAttribute('tabindex', '0'); g.style.cursor = herramienta === 'mover' ? 'grab' : 'crosshair';
        g.setAttribute('aria-label', NOMBRE_PIEZA[p.tipo] + (p.n ? ' ' + (p.tipo === 'A' ? etiquetaAtacante(p.n) : p.n) : '') + ', ' + zona(p.x, p.y));
        g.setAttribute('aria-pressed', esSel ? 'true' : 'false');
        el('circle', { r: 30, fill: 'transparent' }, g);
    }
    if (p.tipo === 'A') {
        el('circle', { r: R, fill: c.ataque, stroke: esSel ? c.sel : c.ataqueTxt, 'stroke-width': esSel ? 4 : 2 }, g);
        var t = el('text', { 'text-anchor': 'middle', 'dominant-baseline': 'central', 'font-size': 18, 'font-weight': 700, fill: c.ataqueTxt, 'font-family': 'Inter, sans-serif' }, g);
        t.textContent = etiquetaAtacante(p.n);
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

// capas (opcional, para la reproducción): [{ f, prog, dim }] fases cuyas flechas se pintan antes de las piezas de `f`.
function renderEn(svg, f, c, interactivo, sinFlechas, capas) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = el('defs', {}, svg);
    marcador(defs, 'flecha-n', c.flecha); marcador(defs, 'flecha-sel', c.selFlecha);
    el('rect', { x: -10, y: -10, width: W + 20, height: H + 20, fill: c.fondo }, svg);
    dibujaPista(svg, c);
    barrasArriba = [];
    f = { piezas: conDefensores(f.piezas), flechas: f.flechas };      // con «Mostrar defensores», los de la fase si no trae propios
    if (capas) capas.forEach(function (l) { dibujaFlechas(svg, l.f, c, false, { prog: l.prog, dim: l.dim, act: l.act }); });
    else if (!sinFlechas) dibujaFlechas(svg, f, c, interactivo);
    f.piezas.forEach(function (p) { if (p.tipo === 'C') dibujaPieza(svg, p, c, interactivo); });
    f.piezas.forEach(function (p) { if (p.tipo === 'D') dibujaPieza(svg, p, c, interactivo); });
    f.piezas.forEach(function (p) { if (p.tipo === 'A') dibujaPieza(svg, p, c, interactivo); });
    f.piezas.forEach(function (p) { if (p.tipo === 'B') dibujaPieza(svg, p, c, interactivo); });
    barrasArriba.forEach(function (b) {              // las barras de bloqueo van sobre las fichas
        var at = {}; for (var kk in b) if (kk !== 'de' && kk !== 'cx' && kk !== 'cy') at[kk] = b[kk];
        el('line', at, svg);
    });
}

// Nota con la descripción de la jugada abierta de la biblioteca. Los jugadores van como {1}…{5} y se rotulan según las etiquetas
// elegidas (números o letras), así la descripción siempre coincide con lo que se ve en la pista.
var notaTexto = '';
function pintaNota() {
    var n = $('jugada-nota'); if (!n) return;
    n.textContent = notaTexto.replace(/\{([1-5])\}/g, function (_, d) { return estado.etiquetas === 'num' ? d : 'ABCDE'.charAt(+d - 1); });
    n.hidden = !notaTexto;
}

function pintar() {
    var svg = $('pista');
    pintaNota();
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
    ['btn-curva-a', 'btn-curva-b', 'btn-recta'].forEach(function (id) { $(id).disabled = !(sel && sel.tipo === 'flecha'); });
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
        var etq = document.createElement('button'); etq.type = 'button'; etq.className = 'f-etq';
        etq.textContent = 'Fase ' + (i + 1); etq.disabled = !!reproduccion;
        etq.setAttribute('aria-label', 'Ir a la fase ' + (i + 1));
        etq.addEventListener('click', function () { irA(i); });
        var txt = document.createElement('span'); txt.textContent = describeFase(fs, i).replace(/^Fase \d+: /, '');
        li.appendChild(etq); li.appendChild(txt);
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
    anuncia(NOMBRE_PIEZA[tipo] + (p.n ? ' ' + (tipo === 'A' ? etiquetaAtacante(p.n) : p.n) : '') + ' colocado. ' + zona(p.x, p.y) + '.');
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

function curvar(delta) {
    if (!sel || sel.tipo !== 'flecha') return;
    var a = fase().flechas[sel.i]; if (!a) return;
    guardarPaso();
    a.curva = delta === 0 ? 0 : redondea(acotar((a.curva || 0) + delta, -CURVA_MAX, CURVA_MAX));
    if (!a.curva) delete a.curva;
    pintar();
    anuncia(a.curva ? 'Flecha curvada.' : 'Flecha recta.');
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
        nuevaFlecha(o.tipo, o.de, { x: o.x, y: o.y, aId: (o.tipo === 'pase' || o.tipo === 'bloqueo') ? bajo : null });
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
        else if (/^[1-5a-eA-E]$/.test(k) && destinoTeclado.tipo === 'pase') {
            var num = /\d/.test(k) ? +k : k.toLowerCase().charCodeAt(0) - 96;
            var q = pieza(f, 'A' + num); if (q) { fantasma.x = q.x; fantasma.y = q.y; fantasma.aId = q.id; anuncia('Destino: atacante ' + etiquetaAtacante(num) + '.'); }
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
                anuncia('Elige el destino con las flechas del teclado' + (herramienta === 'pase' ? ' o con las teclas A a E (o 1 a 5) para un atacante' : '') + '. Enter confirma, Escape cancela.');
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

// Reproductor: una línea de tiempo con todas las fases. En cada fase las flechas se dibujan en el momento y las piezas las
// siguen; el pase hace volar el balón. El estado se calcula siempre a partir del tiempo, así la barra y los saltos de fase
// funcionan igual hacia delante que hacia atrás.
var TV = { ENTRADA: 0.5, ESCALON: 0.45, DUR: 1.0, DUR_PASE: 0.75, TRANS: 0.55, PAUSA: 0.45, TIRO: 1.0, PUNTOS: 1.4 };
function suave(t) { t = acotar(t, 0, 1); return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }

// ¿pasa el recorrido de la flecha idx (un corte o un bote) a menos de d del punto q?
function recorridoCerca(f, idx, q, d) {
    var a = f.flechas[idx], ini = inicioDe(f, idx), fn = puntoFinal(f, a);
    if (!ini || !fn || !q) return false;
    var c = controlDe(ini, fn, a.curva);
    for (var u = 0; u <= 10; u++) {
        var p = puntoCurva(ini.x, ini.y, fn.x, fn.y, a.curva ? c.x : undefined, a.curva ? c.y : undefined, u / 10);
        if (Math.hypot(p.x - q.x, p.y - q.y) < d) return true;
    }
    return false;
}
// ¿lo usa en esta fase algún otro jugador (un corte o un bote que pasa junto al bloqueo)?
function bloqueoUsado(f, idx) {
    var a = f.flechas[idx], q = puntoFinal(f, a);
    return f.flechas.some(function (m, k) { return k !== idx && m.de !== a.de && (m.tipo === 'corte' || m.tipo === 'bote') && recorridoCerca(f, k, q, 60); });
}

function construyeLinea() {
    var t = TV.ENTRADA, fases = [];
    estado.fases.forEach(function (f, i) {
        var inicio = t;
        var tt = t, flechas = [];
        var ultimo = {};                      // fin del último movimiento de cada pieza: los tramos encadenados van en fila
        var bloqueos = {};                    // índice de flecha de bloqueo → { t1, fin } una vez programado
        // Los bloqueos que alguien usa en la misma fase se ponen primero (si la pieza no hace antes otro movimiento) y quien pasa por ellos
        // espera a que lleguen. Un bloqueo que nadie usa todavía (se aprovecha en la fase siguiente) sigue el orden de la lista.
        var orden = f.flechas.map(function (a, idx) { return idx; });
        var movio = {}, pasa = {}, antes = [], despues = [], llegada = {}, pasaT0 = {};   // llegada: cuándo recibe el balón cada jugador
        f.flechas.forEach(function (a, idx) {
            if (a.tipo === 'bloqueo' && !movio[a.de] && !pasa[a.de] && bloqueoUsado(f, idx)) antes.push(idx); else despues.push(idx);
            if (a.tipo !== 'pase') movio[a.de] = true; else pasa[a.de] = true;      // quien pasa antes de bloquear pasa primero
        });
        orden = antes.concat(despues);
        orden.forEach(function (idx) {
            var a = f.flechas[idx];
            var cadena = a.sigue && a.tipo !== 'pase' && ultimo[a.de] !== undefined;
            var d = a.tipo === 'pase' ? TV.DUR_PASE : ((cadena || haySiguiente(f, idx)) ? 0.6 : TV.DUR);
            var t0 = cadena ? Math.max(tt, ultimo[a.de]) : tt;
            if (a.tipo === 'corte' || a.tipo === 'bote') {          // espera al bloqueador cuyo bloqueo cruza su recorrido
                Object.keys(bloqueos).forEach(function (k) {
                    if (f.flechas[k].de !== a.de && recorridoCerca(f, idx, bloqueos[k].fin, 60)) t0 = Math.max(t0, bloqueos[k].t1 - 0.15);
                });
            }
            if (a.tipo !== 'pase' && pasaT0[a.de] !== undefined) t0 = Math.max(t0, pasaT0[a.de] + 0.1);                  // quien pasa no se mueve hasta soltar el balón
            if (a.tipo === 'pase' && llegada[a.de] !== undefined) t0 = Math.max(t0, llegada[a.de] + 0.05);              // no pasa el balón quien aún no lo ha recibido
            if (a.tipo === 'pase' && ultimo[a.de] !== undefined) t0 = Math.max(t0, ultimo[a.de]);                         // si el pasador se movió antes, pasa al acabar
            if (a.tipo === 'pase' && a.aId && ultimo[a.aId] !== undefined) t0 = Math.max(t0, ultimo[a.aId] - d + 0.05);   // el pase llega cuando el receptor ya está (solo cuentan sus movimientos anteriores en la lista)
            if (a.tipo === 'pase' && a.aId) llegada[a.aId] = t0 + d;
            if (a.tipo === 'pase' && pasaT0[a.de] === undefined) pasaT0[a.de] = t0;
            flechas.push({ a: a, i: idx, t0: t0, t1: t0 + d });
            if (a.tipo === 'bloqueo' && puntoFinal(f, a)) bloqueos[idx] = { t1: t0 + d, fin: puntoFinal(f, a) };
            if (a.tipo !== 'pase') ultimo[a.de] = t0 + d;
            tt += TV.ESCALON;
        });
        flechas.sort(function (x, y) { return x.i - y.i; });      // el resto del reproductor espera el orden original
        var fin = flechas.length ? Math.max.apply(null, flechas.map(function (x) { return x.t1; })) : inicio + 0.3;
        var P1 = fin + TV.PAUSA, ultima = i === estado.fases.length - 1;
        fases.push({ f: f, P0: i === 0 ? 0 : inicio, P1: P1, P2: ultima ? P1 : P1 + TV.TRANS, flechas: flechas });
        t = ultima ? P1 : P1 + TV.TRANS;
    });
    // el tiempo de cada fase empieza justo después de la transición anterior (la primera arranca en 0 con una entrada)
    fases.forEach(function (F, i) { if (i > 0) { var previa = fases[i - 1]; F.P0 = previa.P2; } });
    fases.forEach(function (F, i) { F.salto = i < fases.length - 1 && hayCorte(F.f, fases[i + 1].f); });
    fases.forEach(function (F, i) { if (i > 0 && fases[i - 1].salto) F.P0 = fases[i - 1].P1 + TV.TRANS / 2; });
    // t = fin de la última fase; después, siempre, el tiro a canasta (salvo en las jugadas de defensa: enseñan rotaciones y no acaban en tiro)
    return { fases: fases, total: estado.defensa ? t : t + TV.TIRO + TV.PUNTOS };
}

// Si al acabar la fase las piezas están lejos de donde empieza la siguiente (las jugadas de la biblioteca vienen de diagramas
// sueltos), no se las hace cruzar la pista: la transición es un fundido y la nueva formación aparece en su sitio.
var UMBRAL_CORTE = 140;
function hayCorte(f, sig) {
    var fin = {};
    f.piezas.forEach(function (p) { fin[p.id] = { x: p.x, y: p.y }; });
    var movida = {};
    f.flechas.forEach(function (a) {
        if (a.tipo === 'pase' || (movida[a.de] && !a.sigue)) return;
        var q = puntoFinal(f, a); movida[a.de] = true;
        if (q && fin[a.de]) fin[a.de] = { x: q.x, y: q.y };
    });
    return sig.piezas.some(function (p) { return p.tipo === 'A' && fin[p.id] && Math.hypot(fin[p.id].x - p.x, fin[p.id].y - p.y) > UMBRAL_CORTE; });
}
function faseEn(L, T) { var k = 0; L.fases.forEach(function (F, i) { if (T >= F.P0 - 1e-6) k = i; }); return k; }
function controlDe(a, b, curva) { return { x: (a.x + b.x) / 2 - (b.y - a.y) * (curva || 0), y: (a.y + b.y) / 2 + (b.x - a.x) * (curva || 0) }; }

function posPieza(L, k, id, T) {
    var F = L.fases[k], p = pieza(F.f, id);
    if (!p) return null;
    var cur = { x: p.x, y: p.y };
    var movs = F.flechas.filter(function (m) { return m.a.de === id && m.a.tipo !== 'pase'; })
        .filter(function (m, idx) { return idx === 0 || m.a.sigue; });      // las alternativas del diagrama no se juegan
    for (var j = 0; j < movs.length; j++) {
        var m = movs[j], fin = puntoFinal(F.f, m.a);
        if (!fin) continue;
        if (T < m.t0) return cur;
        if (T < m.t1) {
            var c = controlDe(cur, fin, m.a.curva), q = puntoCurva(cur.x, cur.y, fin.x, fin.y, m.a.curva ? c.x : undefined, m.a.curva ? c.y : undefined, suave((T - m.t0) / (m.t1 - m.t0)));
            return { x: q.x, y: q.y };
        }
        cur = { x: fin.x, y: fin.y };
    }
    if (k < L.fases.length - 1 && T > F.P1) {
        var sig = pieza(L.fases[k + 1].f, id);
        if (sig) {
            var e = suave((T - F.P1) / TV.TRANS);
            if (F.salto) return cur;
            return { x: cur.x + (sig.x - cur.x) * e, y: cur.y + (sig.y - cur.y) * e };
        }
    }
    return cur;
}

function portadorDe(f) {      // quién lleva el balón al empezar la fase: el atacante más cercano a la pelota
    var b = pieza(f, 'B'), mejor = null, dmin = 44;
    if (!b) return null;
    f.piezas.forEach(function (p) { if (p.tipo !== 'A') return; var d = Math.hypot(p.x - b.x, p.y - b.y); if (d < dmin) { dmin = d; mejor = p.id; } });
    return mejor;
}

function posBalon(L, k, T) {
    var F = L.fases[k], b = pieza(F.f, 'B');
    if (!b) return null;
    var OFS = 15, ahora = portadorDe(F.f), libre = { x: b.x, y: b.y };
    var pases = F.flechas.filter(function (m) { return m.a.tipo === 'pase'; });
    var rebote = 0;
    for (var j = 0; j < pases.length; j++) {
        var m = pases[j];
        if (T < m.t0) break;
        if (ahora && m.a.de !== ahora) continue;          // otra opción desde el mismo jugador (el diagrama las dibuja todas): no se juega
        var origen = ahora ? posPieza(L, k, ahora, m.t0) : libre, fin = puntoFinal(F.f, m.a);
        if (!origen || !fin) continue;
        var recibe = m.a.aId || null;
        if (T < m.t1) {
            var e = suave((T - m.t0) / (m.t1 - m.t0)), destino = recibe ? posPieza(L, k, recibe, m.t1) : fin;
            var oo = { x: origen.x + OFS, y: origen.y + OFS }, dd = recibe ? { x: destino.x + OFS, y: destino.y + OFS } : destino;
            return { x: oo.x + (dd.x - oo.x) * e, y: oo.y + (dd.y - oo.y) * e - Math.sin(Math.PI * e) * 14 };
        }
        if (recibe) { ahora = recibe; } else { ahora = null; libre = { x: fin.x, y: fin.y }; }
    }
    // el balón bota mientras su portador lleva un bote
    F.flechas.forEach(function (m) { if (m.a.tipo === 'bote' && m.a.de === ahora && T >= m.t0 && T <= m.t1) rebote = Math.abs(Math.sin((T - m.t0) * 11)) * 9; });
    var pos;
    if (ahora) { var q = posPieza(L, k, ahora, T); pos = { x: q.x + OFS, y: q.y + OFS - rebote }; } else pos = libre;
    if (!estado.defensa && k === L.fases.length - 1 && T > F.P1) {   // final: tiro a canasta desde donde está el balón
        var e3 = suave(acotar((T - F.P1) / TV.TIRO, 0, 1));
        return { x: pos.x + (ARO.x - pos.x) * e3, y: pos.y + (ARO.y + 6 - pos.y) * e3 - Math.sin(Math.PI * e3) * 70 };
    }
    if (k < L.fases.length - 1 && T > F.P1) {
        var sig = pieza(L.fases[k + 1].f, 'B');
        if (sig) {
            var e2 = suave((T - F.P1) / TV.TRANS);
            if (!F.salto) pos = { x: pos.x + (sig.x - pos.x) * e2, y: pos.y + (sig.y - pos.y) * e2 };
        }
    }
    return pos;
}

// Final de toda reproducción: tira quien acaba con el balón (las opciones alternativas del diagrama no se juegan).
function finalista(L) {
    var F = L.fases[L.fases.length - 1], ahora = portadorDe(F.f), libre = null;
    F.flechas.forEach(function (m) {
        if (m.a.tipo !== 'pase' || (ahora && m.a.de !== ahora)) return;
        if (m.a.aId) { ahora = m.a.aId; libre = null; } else { ahora = null; libre = puntoFinal(F.f, m.a); }
    });
    var fin = function (id) { return posPieza(L, L.fases.length - 1, id, F.P1); };
    if (!ahora && libre) {
        var mejor = null, dmin = 1e9;
        F.f.piezas.forEach(function (p) { if (p.tipo !== 'A') return; var q = fin(p.id), d = Math.hypot(q.x - libre.x, q.y - libre.y); if (d < dmin) { dmin = d; mejor = p.id; } });
        ahora = mejor;
    }
    if (!ahora) return null;
    var q = fin(ahora), d = Math.hypot(q.x - ARO.x, q.y - ARO.y);
    return { id: ahora, pieza: pieza(F.f, ahora), puntos: d > 237 ? 3 : 2, cerca: d < 110 };
}

// destino (opcional): otro <svg> y tema para dibujar el fotograma sin tocar la página (exportar GIF).
function pintaReproduccion(T, destino, tema) {
    var L = reproduccion.L, k = faseEn(L, T), F = L.fases[k], lienzo = destino || $('pista'), c = tema || CLARO;
    var mezcla = { piezas: F.f.piezas.map(function (p) {
        var q = { id: p.id, tipo: p.tipo, n: p.n, x: p.x, y: p.y };
        if (p.tipo !== 'B') { var pos = posPieza(L, k, p.id, T); if (pos) { q.x = pos.x; q.y = pos.y; } }
        return q;
    }), flechas: [] };
    var pb = posBalon(L, k, T);
    if (pb) mezcla.piezas.forEach(function (q) { if (q.tipo === 'B') { q.x = pb.x; q.y = pb.y; } });
    var capas = [];
    var desde = 0;                       // las flechas dejadas solo valen mientras la formación es la misma
    for (var j0 = 0; j0 < k; j0++) if (L.fases[j0].salto) desde = j0 + 1;
    if (reproduccion.mantener) for (var j = desde; j < k; j++) capas.push({ f: L.fases[j].f, prog: null, dim: true });
    capas.push({ f: F.f, prog: F.flechas.reduce(function (acc, m) { acc[m.i] = acotar((T - m.t0) / (m.t1 - m.t0), 0, 1); return acc; }, []), dim: false, act: mezcla });
    renderEn(lienzo, mezcla, c, false, false, capas);
    var op = 1, mitad = TV.TRANS / 2;       // fundido entre formaciones: la vieja se apaga y la nueva aparece
    if (F.salto && T > F.P1) op = acotar(1 - (T - F.P1) / mitad, 0, 1);
    else if (k > 0 && L.fases[k - 1].salto && T < F.P0 + mitad) op = acotar((T - F.P0) / mitad, 0, 1);
    if (op < 1) Array.prototype.forEach.call(lienzo.querySelectorAll('[data-pieza]'), function (g) { g.setAttribute('opacity', String(op)); });
    var ult = L.fases.length - 1, tirando = !estado.defensa && k === ult && T > F.P1;
    if (tirando) {                                                  // balón a canasta y marcador
        var fi = reproduccion.final || (reproduccion.final = finalista(L));
        var e4 = (T - F.P1) / TV.TIRO;
        if (fi && e4 >= 1) {
            var sube = acotar((T - F.P1 - TV.TIRO) / 0.8, 0, 1);
            var tx = el('text', { x: ARO.x, y: ARO.y + 46 - sube * 18, 'text-anchor': 'middle', 'font-size': 34, 'font-weight': 800, fill: c.ataque, opacity: String(1 - Math.max(0, sube - 0.6) / 0.4), 'font-family': 'Sora, Inter, sans-serif' }, lienzo);
            tx.textContent = '+' + fi.puntos;
        }
    }
    if (destino) return;
    reproduccion.T = T;
    $('rep-barra').value = String(Math.round(T / L.total * 1000));
    var texto = describeFase(F.f, k).replace(/^Fase \d+: /, '');
    var marca = tirando ? 'final' : k;
    if (reproduccion.fase !== marca) {
        reproduccion.fase = marca;
        var fi2 = tirando ? (reproduccion.final || (reproduccion.final = finalista(L))) : null;
        $('rep-texto').textContent = tirando
            ? 'Final · ' + (fi2 ? nombrePieza(fi2.pieza).replace(/^el /, 'El ').replace(/^el jugador /, 'El jugador ') + (fi2.cerca ? ' ataca el aro y anota' : ' tira y anota') + ' (' + fi2.puntos + (fi2.puntos === 3 ? ' puntos' : ' puntos') + ').' : 'Canasta.')
            : 'Fase ' + (k + 1) + ' de ' + L.fases.length + ' · ' + texto;
    }
    estado.actual = k;
    $('fase-etq').textContent = 'Fase ' + (k + 1) + ' de ' + estado.fases.length;
}

function bucleReproduccion(ahora) {
    if (!reproduccion || !reproduccion.sonando) return;
    if (reproduccion.ultimo === null) reproduccion.ultimo = ahora;
    var dt = Math.min(0.25, (ahora - reproduccion.ultimo) / 1000) * reproduccion.vel;
    reproduccion.ultimo = ahora;
    var T = reproduccion.T + dt, total = reproduccion.L.total;
    if (T >= total) { T = total; reproduccion.sonando = false; paintaPlay(); }
    pintaReproduccion(T);
    if (reproduccion.sonando) requestAnimationFrame(bucleReproduccion);
}

function paintaPlay() {
    var b = $('rep-play'); if (!b || !reproduccion) return;
    b.textContent = reproduccion.sonando ? 'Pausa' : (reproduccion.T >= reproduccion.L.total - 0.01 ? 'Repetir' : 'Seguir');
    b.setAttribute('aria-label', reproduccion.sonando ? 'Pausar la reproducción' : 'Reproducir');
}

function repPlay() {
    if (!reproduccion) return;
    if (reproduccion.sonando) { reproduccion.sonando = false; paintaPlay(); return; }
    if (reproduccion.T >= reproduccion.L.total - 0.01) { reproduccion.T = 0; reproduccion.fase = -1; }
    reproduccion.sonando = true; reproduccion.ultimo = null; paintaPlay();
    requestAnimationFrame(bucleReproduccion);
}

function repSalta(dir) {                  // salto a la fase anterior o siguiente (con la fase completa dibujada si no hay movimiento)
    if (!reproduccion) return;
    var L = reproduccion.L, k = faseEn(L, reproduccion.T), objetivo;
    reproduccion.sonando = false;
    if (dir > 0) objetivo = k < L.fases.length - 1 ? L.fases[k + 1].P0 + 0.001 : L.total;
    else objetivo = reproduccion.T - L.fases[k].P0 > 0.8 || k === 0 ? L.fases[k].P0 + 0.001 : L.fases[k - 1].P0 + 0.001;
    reproduccion.fase = -1;
    pintaReproduccion(acotar(objetivo, 0, L.total));
    paintaPlay();
}

function reproducir() {
    if (reproduccion) { paraReproduccion(); return; }
    sel = null;
    reproduccion = { L: null, T: 0, fase: -1, sonando: false, ultimo: null, vel: 1, mantener: $('rep-mantener').checked, volver: estado.actual };
    reproduccion.L = construyeLinea();
    $('reproductor').hidden = false;
    $('btn-reproducir').textContent = 'Parar'; $('btn-reproducir').setAttribute('aria-pressed', 'true');
    document.querySelectorAll('.tablero fieldset button:not(#btn-reproducir)').forEach(function (b) { b.disabled = true; });
    if (reducirMovimiento || estado.fases.length < 2 && !estado.fases[0].flechas.length) {
        pintaReproduccion(reproduccion.L.fases[0].P1);       // sin animación: la fase entera, y se avanza con los botones
        paintaPlay();
    } else { repPlay(); }
    anuncia('Reproduciendo la jugada. Usa los botones del reproductor para pausar o cambiar de fase.');
}

function paraReproduccion() {
    if (!reproduccion) return;
    reproduccion.sonando = false;
    var volver = reproduccion.volver; reproduccion = null;
    $('reproductor').hidden = true;
    document.querySelectorAll('.tablero fieldset button').forEach(function (b) { b.disabled = false; });
    estado.actual = volver; pintar();
}

// ── Guardar, abrir, exportar ─────────────────────────────────────────────
// Con sesión iniciada las jugadas viven en el servidor (cuenta); sin ella, en el navegador (localStorage).
var USUARIO = document.body.getAttribute('data-usuario') || '';
function csrf() { var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/); return m ? decodeURIComponent(m[1]) : ''; }
function api(url, opciones) {
    opciones = opciones || {};
    opciones.credentials = 'same-origin';
    opciones.headers = Object.assign({ 'X-CSRFToken': csrf() }, opciones.headers || {});
    return fetch(url, opciones).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (cuerpo) {
            if (!r.ok) { var e = new Error(cuerpo.error || 'Error ' + r.status); e.estado = r.status; throw e; }
            return cuerpo;
        });
    });
}
function almacen() { try { return JSON.parse(localStorage.getItem(CLAVE) || '[]'); } catch (e) { return []; } }
function escribeAlmacen(l) { try { localStorage.setItem(CLAVE, JSON.stringify(l)); return true; } catch (e) { return false; } }

var guardadasCache = [];      // [{ id, nombre }] en modo cuenta; en modo local, el índice hace de id
function pintaGuardadas() {
    var s = $('guardadas'); s.textContent = '';
    var o0 = document.createElement('option'); o0.value = ''; o0.textContent = 'Jugadas guardadas…'; s.appendChild(o0);
    guardadasCache.forEach(function (j) { var o = document.createElement('option'); o.value = String(j.id); o.textContent = j.nombre || 'Sin nombre'; s.appendChild(o); });
}
function cargaGuardadas() {
    if (!USUARIO) { guardadasCache = almacen().map(function (j, i) { return { id: i, nombre: j.nombre }; }); pintaGuardadas(); return Promise.resolve(); }
    return api('/jugadas/guardadas/').then(function (r) { guardadasCache = r.jugadas || []; pintaGuardadas(); })
        .catch(function (e) { anuncia(e.estado === 401 ? 'Tu sesión ha caducado: vuelve a entrar.' : 'No se pudo cargar tu lista de jugadas.'); });
}

function nombreJugada() { return ($('nombre').value || '').trim().slice(0, 80) || 'Mi jugada'; }

function validar(j) { // sanea cualquier JSON de fuera: solo se aceptan tipos y rangos conocidos
    if (!j || typeof j !== 'object' || !Array.isArray(j.fases) || !j.fases.length || j.fases.length > MAX_FASES) return null;
    var num = function (v, a, b) { return typeof v === 'number' && isFinite(v) ? acotar(v, a, b) : null; };
    var salida = { nombre: typeof j.nombre === 'string' ? j.nombre.slice(0, 80) : '', etiquetas: j.etiquetas === 'letra' ? 'letra' : 'num', fases: [], actual: 0 };
    if (j.defensa === true) salida.defensa = true;      // jugada de defensa: la reproducción no acaba en tiro
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
            var cv = num(a.curva, -CURVA_MAX, CURVA_MAX); if (cv) r.curva = redondea(cv);
            if (a.sigue === true && a.tipo !== 'pase') r.sigue = true;   // este tramo continúa desde donde acabó el anterior de la misma pieza
            nf.flechas.push(r);
        });
        salida.fases.push(nf);
    }
    return salida;
}
function cargaJugada(j) {
    paraReproduccion();                      // si se estaba reproduciendo otra jugada, se para antes de cambiar
    estado = j; sel = null; deshacer = []; rehacer = []; notaTexto = '';
    $('nombre').value = j.nombre || '';
    $('etiquetas').value = j.etiquetas;
    pintar();
}

function descarga(blob, nombre) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = nombre;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
}
function nombreArchivo() { return nombreJugada().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'jugada'; }

// Marca de agua de las exportaciones (PNG, impresión y GIF): discreta, abajo a la derecha, dentro de la pista.
function marcaAgua(svg, c) {
    var t = el('text', { x: W - 10, y: H - 10, 'text-anchor': 'end', 'font-size': 15, 'font-weight': 600, fill: c.linea, opacity: '.7', 'font-family': 'Inter, Arial, sans-serif', 'pointer-events': 'none' }, svg);
    t.textContent = 'MiPizarra · Nacho Pola';
}

function pngDeFase(f, ancho, cb) {
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('xmlns', NS); svg.setAttribute('viewBox', '-10 -10 ' + (W + 20) + ' ' + (H + 20));
    var alto = Math.round(ancho * (H + 20) / (W + 20));
    svg.setAttribute('width', ancho); svg.setAttribute('height', alto);
    renderEn(svg, f, IMPRESION, false, false);
    marcaAgua(svg, IMPRESION);
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
        marcaAgua(svg, IMPRESION);
        var cap = document.createElement('figcaption'); cap.textContent = describeFase(f, i);
        fig.appendChild(svg); fig.appendChild(cap); cont.appendChild(fig);
    });
}

// GIF animado: la jugada entera (con el tiro final) en el tema claro y con marca de agua. La librería de GIF se carga solo al pedirlo.
var exportandoGif = false;
function exportaGif() {
    if (exportandoGif) return;
    var boton = $('btn-gif'), url = boton.getAttribute('data-lib');
    exportandoGif = true; boton.disabled = true;
    var guardada = reproduccion;
    var fin = function (msg) { reproduccion = guardada; exportandoGif = false; boton.disabled = false; boton.textContent = 'GIF animado'; if (msg) anuncia(msg); };
    import(new URL(url, document.baseURI).href).then(function (lib) {
        var L = construyeLinea(), fps = L.total > 40 ? 8 : 12, n = Math.ceil(L.total * fps) + 1, ancho = 480, alto = Math.round(ancho * (H + 20) / (W + 20));
        reproduccion = { L: L, mantener: true, final: null, T: 0, fase: -1 };
        var lienzo = document.createElement('canvas'); lienzo.width = ancho; lienzo.height = alto;
        var ctx = lienzo.getContext('2d', { willReadFrequently: true });
        var svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('xmlns', NS); svg.setAttribute('viewBox', '-10 -10 ' + (W + 20) + ' ' + (H + 20)); svg.setAttribute('width', ancho); svg.setAttribute('height', alto);
        function fotograma(i) {                // dibuja el instante i y devuelve sus píxeles
            pintaReproduccion(Math.min(L.total, i / fps), svg, IMPRESION);
            marcaAgua(svg, IMPRESION);
            var u = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml;charset=utf-8' }));
            return new Promise(function (ok, mal) {
                var img = new Image();
                img.onload = function () { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, ancho, alto); ctx.drawImage(img, 0, 0, ancho, alto); URL.revokeObjectURL(u); ok(ctx.getImageData(0, 0, ancho, alto).data); };
                img.onerror = function () { URL.revokeObjectURL(u); mal(new Error('imagen')); };
                img.src = u;
            });
        }
        var gif = lib.GIFEncoder(), paleta = null, i = 0;
        function siguiente() {
            if (i >= n) {
                gif.finish();
                descarga(new Blob([gif.bytes()], { type: 'image/gif' }), nombreArchivo() + '.gif');
                fin('GIF guardado.'); return;
            }
            boton.textContent = 'GIF ' + Math.round(i / n * 100) + ' %';
            fotograma(i).then(function (px) {
                if (paleta) return px;
                // una sola paleta para toda la jugada: el primer fotograma más otro a mitad (con flechas y bloqueos dibujados)
                return fotograma(Math.floor(n * 0.4)).then(function (otro) {
                    var junto = new Uint8ClampedArray(px.length + otro.length); junto.set(px); junto.set(otro, px.length);
                    paleta = lib.quantize(junto, 256);
                    return fotograma(i);
                });
            }).then(function (px) {
                var idx = lib.applyPalette(px, paleta);
                var ultimo = i === n - 1;
                gif.writeFrame(idx, ancho, alto, i === 0 ? { palette: paleta, delay: Math.round(1000 / fps), repeat: 0 } : { delay: ultimo ? 1800 : Math.round(1000 / fps) });
                i++; setTimeout(siguiente, 0);
            }).catch(function () { fin('No se pudo generar el GIF.'); });
        }
        siguiente();
    }).catch(function () { fin('No se pudo cargar el generador de GIF.'); });
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
    $('etiquetas').addEventListener('change', function (e) { guardarPaso(); estado.etiquetas = e.target.value === 'num' ? 'num' : 'letra'; pintar(); anuncia('Etiquetas de los jugadores: ' + (estado.etiquetas === 'num' ? 'números' : 'letras') + '.'); });
    $('btn-curva-a').addEventListener('click', function () { curvar(0.2); });
    $('btn-curva-b').addEventListener('click', function () { curvar(-0.2); });
    $('btn-recta').addEventListener('click', function () { curvar(0); });
    $('btn-fase-ant').addEventListener('click', function () { irA(estado.actual - 1); });
    $('btn-fase-sig').addEventListener('click', function () { irA(estado.actual + 1); });
    $('btn-nueva-fase').addEventListener('click', nuevaFase);
    $('btn-borrar-fase').addEventListener('click', borrarFase);
    $('btn-reproducir').addEventListener('click', reproducir);
    $('rep-play').addEventListener('click', repPlay);
    $('rep-ant').addEventListener('click', function () { repSalta(-1); });
    $('rep-sig').addEventListener('click', function () { repSalta(1); });
    $('rep-barra').addEventListener('input', function () {
        if (!reproduccion) return;
        reproduccion.sonando = false; reproduccion.fase = -1;
        pintaReproduccion($('rep-barra').value / 1000 * reproduccion.L.total); paintaPlay();
    });
    $('rep-mantener').addEventListener('change', function (e) { if (reproduccion) { reproduccion.mantener = e.target.checked; reproduccion.fase = -1; pintaReproduccion(reproduccion.T); } });
    $('mostrar-def').addEventListener('change', function (e) {
        mostrarDef = e.target.checked;
        if (reproduccion) { reproduccion.fase = -1; pintaReproduccion(reproduccion.T); } else pintar();
        anuncia(mostrarDef ? 'Defensores automáticos mostrados.' : 'Defensores automáticos ocultos.');
    });
    $('rep-vel').addEventListener('change', function (e) { if (reproduccion) reproduccion.vel = +e.target.value; });
    $('btn-limpiar').addEventListener('click', function () {
        if (!fase().piezas.length) return;
        guardarPaso(); fase().piezas = []; fase().flechas = []; sel = null; pintar(); anuncia('Fase vaciada. Puedes deshacer.');
    });
    $('plantillas').addEventListener('change', function (e) {
        var v = e.target.value; if (!v) return;
        paraReproduccion(); guardarPaso(); var j = plantilla(v); j.nombre = estado.nombre; j.etiquetas = estado.etiquetas; estado = j; sel = null; e.target.value = ''; pintar(); anuncia('Plantilla colocada.');
    });
    $('btn-guardar').addEventListener('click', function () {
        var j = clon(estado); j.nombre = nombreJugada(); j.actual = 0;
        if (USUARIO) {
            api('/jugadas/guardadas/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre: j.nombre, datos: j }) })
                .then(function (r) { anuncia(r.creada ? 'Jugada guardada en tu cuenta.' : 'Jugada actualizada en tu cuenta.'); return cargaGuardadas(); })
                .catch(function (e) { anuncia(e.estado === 401 ? 'Tu sesión ha caducado: vuelve a entrar.' : 'No se pudo guardar: ' + e.message); });
            return;
        }
        var l = almacen();
        var i = l.map(function (x) { return x.nombre; }).indexOf(j.nombre);
        if (i >= 0) l[i] = j; else { if (l.length >= 50) { anuncia('Hay demasiadas jugadas guardadas; borra alguna.'); return; } l.push(j); }
        anuncia(escribeAlmacen(l) ? 'Jugada guardada en este navegador.' : 'No se pudo guardar: el navegador bloquea el almacenamiento. Usa Exportar.');
        cargaGuardadas();
    });
    $('btn-abrir').addEventListener('click', function () {
        var i = $('guardadas').value; if (i === '') return;
        if (USUARIO) {
            api('/jugadas/guardadas/' + encodeURIComponent(i) + '/').then(function (r) {
                var j = validar(r.datos); if (!j) { anuncia('Esa jugada guardada no es válida.'); return; }
                j.nombre = r.nombre; cargaJugada(j); anuncia('Jugada abierta.');
            }).catch(function (e) { anuncia('No se pudo abrir: ' + e.message); });
            return;
        }
        var j = validar(almacen()[+i]); if (!j) { anuncia('Esa jugada guardada no es válida.'); return; }
        cargaJugada(j); anuncia('Jugada abierta.');
    });
    $('btn-eliminar').addEventListener('click', function () {
        var i = $('guardadas').value; if (i === '') return;
        if (USUARIO) {
            api('/jugadas/guardadas/' + encodeURIComponent(i) + '/', { method: 'DELETE' })
                .then(function () { anuncia('Jugada eliminada de tu cuenta.'); return cargaGuardadas(); })
                .catch(function (e) { anuncia('No se pudo eliminar: ' + e.message); });
            return;
        }
        var l = almacen(); l.splice(+i, 1); escribeAlmacen(l); cargaGuardadas(); anuncia('Jugada guardada eliminada.');
    });
    $('btn-json').addEventListener('click', function () {
        var j = clon(estado); j.nombre = nombreJugada();
        descarga(new Blob([JSON.stringify(j, null, 1)], { type: 'application/json' }), nombreArchivo() + '.json');
    });
    $('btn-importar').addEventListener('click', function () { $('archivo').click(); });
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
    $('btn-gif').addEventListener('click', exportaGif);
    $('btn-imprimir').addEventListener('click', function () { preparaImpresion(); window.print(); });
    $('nombre').addEventListener('input', function () { estado.nombre = nombreJugada(); });
    document.addEventListener('keydown', function (ev) {
        var t = ev.target;
        if (reproduccion && ev.key === 'Escape') { ev.preventDefault(); paraReproduccion(); return; }
        if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return;
        if (reproduccion && ev.key === ' ' && !(t && t.tagName === 'BUTTON')) { ev.preventDefault(); repPlay(); return; }
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'z') { ev.preventDefault(); volverPaso(deshacer, rehacer); }
        else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'y') { ev.preventDefault(); volverPaso(rehacer, deshacer); }
    });
    iniciaBiblioteca();
    cargaGuardadas();
    pintar();
}

// ── Biblioteca de jugadas (catálogo estático del servidor) ────────────────
var biblioteca = [];
// vista previa de la primera fase: una imagen SVG independiente (sin ids repetidos en la página)
function previaDe(j) {
    var v = validar(j.crudo), svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('xmlns', NS); svg.setAttribute('viewBox', '-10 -10 ' + (W + 20) + ' ' + (H + 20));
    var guardado = estado; estado = v;               // etiquetaAtacante lee estado.etiquetas
    escalaTrazo = 2;
    try { renderEn(svg, v.fases[0], CLARO, false, false); } finally { estado = guardado; escalaTrazo = 1; }
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
}
function iniciaBiblioteca() {
    var lista = $('bib-lista'), vacio = $('bib-vacio'), nota = $('jugada-nota'), filtro = '';
    function abre(j) {
        paraReproduccion();                  // si se estaba reproduciendo otra jugada, se para antes de abrir esta
        guardarPaso();
        var v = validar(j.crudo); v.nombre = j.nombre;
        estado = v; sel = null; notaTexto = j.descripcion; $('nombre').value = j.nombre; $('etiquetas').value = v.etiquetas; pintar();
        anuncia('Jugada «' + j.nombre + '» abierta, ' + estado.fases.length + ' fases.');
        $('pista').scrollIntoView({ behavior: reducirMovimiento ? 'auto' : 'smooth', block: 'center' });
    }
    function rellena() {
        lista.textContent = ''; var n = 0;
        biblioteca.forEach(function (j) {
            if (filtro && j.edades.indexOf(filtro) < 0) return;
            n++;
            var b = document.createElement('button'); b.type = 'button'; b.className = 'tarjeta'; b.setAttribute('role', 'listitem');
            b.setAttribute('aria-label', j.nombre + '. ' + j.fases + (j.fases === 1 ? ' fase' : ' fases') + '. Abrir en el editor.');
            var img = document.createElement('img'); img.alt = ''; img.loading = 'lazy'; img.decoding = 'async'; img.src = j.previa || (j.previa = previaDe(j));
            var cuerpo = document.createElement('span'); cuerpo.className = 't-cuerpo';
            var nombre = document.createElement('span'); nombre.className = 't-nombre'; nombre.textContent = j.nombre;
            var meta = document.createElement('span'); meta.className = 't-meta';
            var e = document.createElement('span'); e.className = 't-edad'; e.textContent = j.edades.length ? j.edades[0] + (j.edades.length > 1 ? '+' : '') : '—';
            var f = document.createElement('span'); f.textContent = j.fases + (j.fases === 1 ? ' fase' : ' fases');
            meta.appendChild(e); meta.appendChild(f);
            if (j.conceptos) { var cc = document.createElement('span'); cc.textContent = 'Por conceptos'; cc.title = 'Juego por conceptos: se improvisa en la llegada o tras otra jugada, no es una jugada cerrada'; meta.appendChild(cc); b.setAttribute('aria-label', b.getAttribute('aria-label') + ' Juego por conceptos.'); } cuerpo.appendChild(nombre); cuerpo.appendChild(meta);
            b.appendChild(img); b.appendChild(cuerpo);
            b.addEventListener('click', function () { abre(j); });
            lista.appendChild(b);
        });
        lista.setAttribute('aria-busy', 'false'); vacio.hidden = n > 0;
        // en minibasket no hay jugadas a propósito: se juega con espacios y se aprende a leer el juego, no se memorizan sistemas
        vacio.textContent = filtro === 'U10' || filtro === 'U12'
            ? 'Cero jugadas, y a propósito: a esta edad no se memorizan sistemas, se juega con espacios y se aprende a leer el juego. Para entrenar eso, mira los ejercicios y juegos de la portada.'
            : 'No hay jugadas para esta categoría.';
    }
    document.querySelectorAll('.bib-filtros .chip').forEach(function (c) {
        c.addEventListener('click', function () {
            filtro = c.getAttribute('data-edad') || '';
            document.querySelectorAll('.bib-filtros .chip').forEach(function (o) { o.setAttribute('aria-pressed', o === c ? 'true' : 'false'); });
            rellena();
        });
    });
    fetch(lista.getAttribute('data-url'), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (datos) {
        biblioteca = (Array.isArray(datos) ? datos : []).map(function (c) {
            var v = validar(c);
            return { crudo: c, nombre: String(c.nombre || '').slice(0, 120), descripcion: String(c.descripcion || '').slice(0, 600), edades: Array.isArray(c.edades) ? c.edades.map(String) : [], fases: v ? v.fases.length : 0, conceptos: c.conceptos === true, valida: !!v };
        }).filter(function (j) { return j.valida; });
        rellena();
    }).catch(function () { lista.textContent = 'No se pudo cargar la biblioteca'; lista.setAttribute('aria-busy', 'false'); });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
})();
