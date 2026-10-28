const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
let currentResult = null;
let currentObjetivo = '';
let currentEdad = '';
let currentEdadSlug = 'general';
let currentDuracion = 0;
let currentMode = 'sesion';
let currentBloques = [];
let currentEjercicios = [];
let selectedEjercicios = new Set();

// ── Cuenta atrás cuando se alcanza el límite de peticiones ───────────────────────────────────────
// El servidor limita las consultas por minuto/hora para no saturar el modelo; en vez de dejar el botón a ciegas, se
// bloquea y se cuenta cuánto falta (como máximo: la ventana del límite).
let _cuentaAtras = null;
function iniciarCuentaAtras(segundos) {
    detenerCuentaAtras();
    const botones = ['btn-generar', 'btn-reglamento'].map(id => document.getElementById(id));
    const hasta = Date.now() + segundos * 1000;
    const pintar = () => {
        const falta = Math.ceil((hasta - Date.now()) / 1000);
        if (falta <= 0) { detenerCuentaAtras(); clearFormError(); return; }
        const t = falta >= 90 ? `${Math.ceil(falta / 60)} min` : `${falta} s`;
        showFormError(`Has hecho muchas peticiones seguidas. Podrás volver a probar en ${t}.`);
        botones.forEach(b => { b.disabled = true; });
    };
    pintar();
    _cuentaAtras = setInterval(pintar, 1000);
}
function detenerCuentaAtras() {
    if (_cuentaAtras) { clearInterval(_cuentaAtras); _cuentaAtras = null; }
    ['btn-generar', 'btn-reglamento'].forEach(id => { document.getElementById(id).disabled = false; });
}
// Error de una petición: si es el límite (429) con tiempo conocido, cuenta atrás; si no, el mensaje de siempre.
function errorDePeticion(data, status) {
    if (status === 429 && data && data.retry_after) { iniciarCuentaAtras(data.retry_after); return null; }
    return data && data.error ? data.error : `Error del servidor (${status})`;
}

// ── Errores en línea (sin alert() bloqueante) ────────────────────────────────
function showFormError(msg) {
    const el = document.getElementById('form-error');
    el.textContent = msg;
    el.style.display = '';
}
function clearFormError() {
    document.getElementById('form-error').style.display = 'none';
    document.getElementById('form-aviso').textContent = '';
}
// Aviso que no es un error: la sesión o la corrección se hicieron, con una salvedad.
function showFormAviso(msg) {
    document.getElementById('form-aviso').textContent = msg;
}

// ── Mode tabs ──────────────────────────────────────────────────────────────
document.querySelectorAll('.mode-tab:not(.mode-link)').forEach(btn => {
    btn.addEventListener('click', () => {
        currentMode = btn.dataset.mode;
        document.querySelectorAll('.mode-tab:not(.mode-link)').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.mode-tab:not(.mode-link)').forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
        clearFormError();
        showEmpty();
    });
});

// Enlace directo desde otras páginas (p. ej. «Reglamento» en Jugadas).
if (location.hash === '#reglamento') {
    const tabReg = document.querySelector('.mode-tab[data-mode="reglamento"]');
    if (tabReg) tabReg.click();
}

// ── Desplegables a medida (edad, duración) ──────────────────────────────────
document.querySelectorAll('.dd').forEach(dd => {
    const btn    = dd.querySelector('.dd-btn');
    const label  = dd.querySelector('.dd-label');
    const native = dd.querySelector('.dd-native');
    const prefix = dd.dataset.prefix;
    const opts   = Array.from(dd.querySelectorAll('.dd-opt'));

    function closeDd() { dd.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
    function openDd() {
        document.querySelectorAll('.dd.open').forEach(o => { if (o !== dd) o.classList.remove('open'); });
        dd.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
    }
    function selectOpt(opt) {
        opts.forEach(o => { o.classList.remove('selected'); o.setAttribute('aria-selected', 'false'); });
        opt.classList.add('selected');
        opt.setAttribute('aria-selected', 'true');
        native.value = opt.dataset.value;
        native.dispatchEvent(new Event('change'));
        label.textContent = `${prefix}: ${opt.textContent}`;
        closeDd();
    }

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        dd.classList.contains('open') ? closeDd() : openDd();
    });
    btn.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openDd();
            (dd.querySelector('.dd-opt.selected') || opts[0])?.focus();
        }
    });

    opts.forEach((opt, i) => {
        opt.addEventListener('click', () => selectOpt(opt));
        opt.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); (opts[i + 1] || opts[0]).focus(); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); (opts[i - 1] || opts[opts.length - 1]).focus(); }
            else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectOpt(opt); btn.focus(); }
            else if (e.key === 'Escape') { closeDd(); btn.focus(); }
        });
    });
});
document.addEventListener('click', () => document.querySelectorAll('.dd.open').forEach(d => d.classList.remove('open')));
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') document.querySelectorAll('.dd.open').forEach(d => d.classList.remove('open'));
});

// ── Chips de ejemplo ───────────────────────────────────────────────────────
document.querySelectorAll('.chip[data-fill]').forEach(chip => {
    chip.addEventListener('click', () => {
        const ta = document.getElementById('objetivo');
        ta.value = chip.dataset.fill;
        ta.focus();
    });
});
document.querySelectorAll('.chip[data-fill-pregunta]').forEach(chip => {
    chip.addEventListener('click', () => {
        const ta = document.getElementById('pregunta');
        ta.value = chip.dataset.fillPregunta;
        ta.focus();
    });
});

// ── Volver a la entrada desde resultados ────────────────────────────────────
document.getElementById('btn-nueva').addEventListener('click', () => {
    clearFormError();           // el aviso era de la sesión que se deja
    showEmpty();
    document.getElementById(currentMode === 'sesion' ? 'objetivo' : 'pregunta').focus();
});

// ── Enter to submit ────────────────────────────────────────────────────────
document.getElementById('objetivo').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); generar(); }
});
document.getElementById('pregunta').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); consultarReglamento(); }
});

// ── Generar sesión ─────────────────────────────────────────────────────────
document.getElementById('btn-generar').addEventListener('click', generar);

// ── Consultar reglamento ───────────────────────────────────────────────────
document.getElementById('btn-reglamento').addEventListener('click', consultarReglamento);

// ── Reglamento: respuestas apiladas (la última arriba), cada consulta independiente ─────────────
// El formulario se queda siempre a la vista; no se envía contexto previo (cada pregunta se responde sola) y el
// servidor limita a 10 consultas por minuto. Solo una consulta en curso a la vez, porque el modelo atiende de una en una.
const RG_MAX_RESPUESTAS = 8;
const RG_ESPERA_MAX_MS = 215000;        // un poco más que el tiempo de espera del servidor (210 s)
let _rgEnCurso = false;

function rgActualizarCabecera() {
    const n = document.getElementById('rg-lista').children.length;
    document.getElementById('reglamento-hilo').style.display = (currentMode === 'reglamento' && n) ? '' : 'none';
    document.getElementById('rg-hilo-titulo').textContent = n === 1 ? 'Respuesta' : `Respuestas (${n})`;
}

function rgNuevoItem(pregunta, ambitoTxt) {
    const item = document.createElement('article');
    item.className = 'rg-item';
    const cab = document.createElement('div');
    cab.className = 'rg-item-cab';
    const h = document.createElement('h3');
    h.className = 'rg-pregunta';
    h.textContent = pregunta;
    const amb = document.createElement('span');
    amb.className = 'rg-ambito';
    amb.textContent = ambitoTxt;
    cab.append(h, amb);
    const cuerpo = document.createElement('div');
    cuerpo.className = 'rg-cuerpo';
    item.append(cab, cuerpo);
    const lista = document.getElementById('rg-lista');
    lista.prepend(item);
    while (lista.children.length > RG_MAX_RESPUESTAS) lista.lastElementChild.remove();
    rgActualizarCabecera();
    return item;
}

function rgAmbitoTexto(ambito) {
    const opt = Array.from(document.querySelectorAll('#dd-ambito .dd-opt')).find(o => o.dataset.value === ambito);
    const nombre = opt ? opt.textContent.trim() : '';
    return ambito === 'general' || !nombre ? 'Reglamento general' : `${nombre} y reglamento general`;
}

async function consultarReglamento() {
    if (_rgEnCurso) return;
    const caja = document.getElementById('pregunta');
    const pregunta = caja.value.trim();
    if (!pregunta) { showFormError('Escribe una pregunta.'); return; }
    clearFormError();

    const ambito = document.getElementById('ambito').value || 'general';
    const item = rgNuevoItem(pregunta, rgAmbitoTexto(ambito));
    const cuerpo = item.querySelector('.rg-cuerpo');
    const t0 = Date.now();
    cuerpo.innerHTML = `<div class='rg-espera' role='status'><div class='spinner'></div><span class='rg-espera-txt'></span></div>`;
    const txt = cuerpo.querySelector('.rg-espera-txt');
    const pintarEspera = () => {
        const seg = Math.round((Date.now() - t0) / 1000);
        txt.textContent = seg < 8 ? 'Consultando el reglamento…'
            : `Consultando el reglamento… ${seg} s (la primera consulta puede tardar hasta 2 minutos)`;
    };
    pintarEspera();
    const reloj = setInterval(pintarEspera, 1000);
    _rgEnCurso = true;
    document.getElementById('btn-reglamento').disabled = true;
    const reducido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    item.scrollIntoView({ behavior: reducido ? 'auto' : 'smooth', block: 'nearest' });

    const control = new AbortController();
    const corte = setTimeout(() => control.abort(), RG_ESPERA_MAX_MS);
    try {
        const resp = await fetch('/reglamento/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ pregunta, ambito }),
            signal: control.signal,
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            const msg = errorDePeticion(data, resp.status);
            if (msg === null) throw new Error('Demasiadas consultas seguidas: espera a que termine la cuenta atrás.');
            throw new Error(msg);
        }
        const respuesta = data.respuesta || data.texto || '';
        if (!respuesta.trim()) throw new Error('El reglamento no devolvió una respuesta. Prueba a reformular la pregunta.');
        cuerpo.innerHTML = `<div class='reglamento-card'>${reglamentoHtml(respuesta)}</div>`;
        caja.value = '';
    } catch (e) {
        const msg = e.name === 'AbortError' ? 'La consulta tardó demasiado. Inténtalo de nuevo.' : e.message;
        cuerpo.replaceChildren();
        const err = document.createElement('div');
        err.className = 'rg-error';
        err.setAttribute('role', 'alert');
        err.textContent = msg;
        cuerpo.append(err);
    } finally {
        clearInterval(reloj);
        clearTimeout(corte);
        _rgEnCurso = false;
        document.getElementById('btn-reglamento').disabled = _cuentaAtras !== null;
    }
}

document.getElementById('btn-rg-limpiar').addEventListener('click', () => {
    document.getElementById('rg-lista').replaceChildren();
    rgActualizarCabecera();
    document.getElementById('pregunta').focus();
});

async function generar() {
    const objetivo = document.getElementById('objetivo').value.trim();
    if (!objetivo) { showFormError('Describe qué quieres trabajar en el entrenamiento.'); return; }
    clearFormError();

    const edad = document.getElementById('edad').value;
    const genDiagramas = document.getElementById('gen-diagramas').checked;
    const duracion = parseInt(document.getElementById('duracion').value) || null;
    const maxJugadores = parseInt(document.getElementById('max-jugadores').value) || null;

    currentObjetivo = objetivo;
    currentEdad = document.getElementById('edad').options[document.getElementById('edad').selectedIndex].text;
    currentEdadSlug = edad ? edad.toLowerCase() : 'general';
    currentDuracion = duracion || 0;

    showLoading();

    const payload = { objetivo, generar_diagramas: genDiagramas };
    if (edad) payload.edad = edad;
    if (duracion) payload.duracion = duracion;
    if (maxJugadores) payload.max_jugadores = maxJugadores;

    try {
        const resp = await fetch('/generar/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify(payload),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            const msg = errorDePeticion(data, resp.status);
            if (msg === null) { hideLoading(); showEmpty(); return; }       // límite: ya hay cuenta atrás
            throw new Error(msg);
        }
        if (data.duracion) currentDuracion = data.duracion;
        currentResult = data;
        renderResults(data, false);       // se pinta sin mostrarlo: primero el aviso compacto con las dos opciones
        mostrarListo(data);
    } catch (e) {
        hideLoading();
        showEmpty();
        showFormError('Error: ' + e.message);
    }
}

// ── Markdown helper ────────────────────────────────────────────────────────
// Respuesta del reglamento en párrafos: línea en blanco = párrafo nuevo, «* » o «- » al inicio = viñeta.
function reglamentoHtml(texto) {
    return String(texto).trim().split(/\n{2,}/).map(par =>
        '<p>' + par.split('\n').map(l => mdToHtml(l.replace(/^\s*[*-]\s+/, '• '))).join('<br>') + '</p>'
    ).join('');
}

function mdToHtml(s) {
    return escHtml(s)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');
}

// ── Ámbito del reglamento: qué se consulta según lo elegido ────────────────
function actualizarHintAmbito() {
    const sel = document.getElementById('ambito');
    const hint = document.getElementById('ambito-hint');
    if (!sel || !hint) return;
    const nombre = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : '';
    hint.textContent = (sel.value && sel.value !== 'general')
        ? `Se responde con la normativa de ${nombre} y, en todo lo que no regule, con el reglamento general de FIBA y de la federación española.`
        : 'Reglamento de FIBA y de la federación española, válido en todas las comunidades.';
}
document.getElementById('ambito').addEventListener('change', actualizarHintAmbito);
actualizarHintAmbito();

// ── Estructura de las fichas ───────────────────────────────────────────────
// Los diagramas «no disponible» y «juego libre» se marcan con data-placeholder en la API: no se muestran.
function esPlaceholderDiagrama(d) {
    return !d || !d.svg || d.svg.indexOf('data-placeholder') !== -1;
}

// Etiquetas conocidas de una ficha o del calentamiento, o cualquier etiqueta en mayúsculas (SECUENCIA:, ROTACIÓN:...).
const ETIQUETA_CAMPO = /^(?:(Juego|Reglas|Organización|Duración|Espacio|Material|Consigna|Puntos clave|Errores frecuentes|Qué observar|Cómo facilitar|Cómo complicar|Qué cambia respecto a [\d.]+|Fundamentos)|([A-ZÁÉÍÓÚÑ]{4,}(?: [A-ZÁÉÍÓÚÑ]{2,})*))\s*:\s*(.*)$/;

function etiquetaLegible(t) {
    const s = t.toLowerCase();
    return s.charAt(0).toUpperCase() + s.slice(1);
}

// «Etiqueta: texto» y listas «- ítem» → lista de definición (etiqueta | contenido). Lo que no tiene etiqueta
// va como texto libre; los saltos de línea del modelo no se pierden porque cada campo es su propia fila.
function renderCampos(texto) {
    const campos = [];
    let actual = null;
    for (const crudo of String(texto).split('\n')) {
        const linea = crudo.trim();
        if (!linea) continue;
        const sinMd = linea.replace(/\*\*/g, '');
        const m = sinMd.match(ETIQUETA_CAMPO);
        if (m) {
            actual = { etiqueta: etiquetaLegible(m[1] || m[2]), texto: m[3] || '', items: [] };
            campos.push(actual);
        } else if (/^[-•]\s+/.test(linea) && actual) {
            actual.items.push(linea.replace(/^[-•]\s+/, ''));
        } else if (actual && actual.items.length === 0) {
            actual.texto += (actual.texto ? ' ' : '') + linea;
        } else {
            actual = { etiqueta: '', texto: linea, items: [] };
            campos.push(actual);
        }
    }
    const filas = campos.map(c => {
        c.texto = c.texto.charAt(0).toUpperCase() + c.texto.slice(1);      // el texto puede llegar en la línea siguiente
        if (!c.etiqueta) return `<div class='texto-libre'>${mdToHtml(c.texto)}</div>`;
        const clase = c.etiqueta === 'Juego' ? ' destacado' : (c.etiqueta === 'Consigna' ? ' consigna' : '');
        const lista = c.items.length ? `<ul>${c.items.map(i => `<li>${mdToHtml(i)}</li>`).join('')}</ul>` : '';
        const cuerpo = c.texto ? mdToHtml(c.texto) : '';
        return `<div class='campo${clase}'><dt>${escHtml(c.etiqueta)}</dt><dd>${cuerpo}${lista}</dd></div>`;
    });
    return `<dl class='ficha'>${filas.join('')}</dl>`;
}

// Bloque que no es un «Ejercicio N»: títulos **...** (calentamiento, parte principal, descanso) y su contenido.
function renderBloqueSeccion(texto) {
    const contenido = texto.trim();
    if (!contenido) return '';
    let out = '';
    let cuerpo = [];
    const volcar = () => {
        if (cuerpo.join('').trim()) out += `<div class='sesion-card estructurada'>${renderCampos(cuerpo.join('\n'))}</div>`;
        cuerpo = [];
    };
    for (const linea of contenido.split('\n')) {
        const t = linea.trim();
        let m = t.match(/^\*\*(.+?)\*\*\s*:\s*(.+)$/);        // «**Fundamentos**: texto»
        if (m) {
            volcar();
            out += `<h2 class='section-title'>${escHtml(m[1])}</h2>`;
            out += `<div class='sesion-card estructurada'><div class='texto-libre'>${mdToHtml(m[2])}</div></div>`;
            continue;
        }
        m = t.match(/^\*\*(.+?)\*\*$/);                       // «**CALENTAMIENTO (10 min)**»
        if (m) { volcar(); out += `<h2 class='section-title'>${escHtml(m[1])}</h2>`; continue; }
        cuerpo.push(linea);
    }
    volcar();
    return out;
}

// ── Render sesión ──────────────────────────────────────────────────────────
function renderResults(data, mostrar = true) {
    document.getElementById('results-heading').textContent = 'Sesión de entrenamiento generada';
    const texto = (data.sesion || data.texto || '').replace(/\[ej_\d+\]\s*/g, '');
    const diagramas = data.diagramas || [];

    // Agrupar diagramas por nombre de ejercicio (para multifase)
    const diagGroups = [];
    let di = 0;
    while (di < diagramas.length) {
        const nom = diagramas[di].nombre;
        const grp = [];
        while (di < diagramas.length && diagramas[di].nombre === nom) grp.push(diagramas[di++]);
        diagGroups.push(grp);
    }

    let html = '';

    // Parsear texto en bloques (secciones y ejercicios). Se guarda en
    // currentBloques (no solo local) para poder sustituir un único bloque tras
    // un reprompt y reconstruir el texto completo sin tocar el resto.
    const lineas = texto.split('\n');
    let bloques = [], bloque = [], ejIdx = -1;
    for (const linea of lineas) {
        if (/^\s*Ejercicio \d+/.test(linea)) {
            if (bloque.length) bloques.push({ ejIdx, texto: bloque.join('\n') });
            ejIdx++;
            bloque = [linea];
        } else {
            bloque.push(linea);
        }
    }
    if (bloque.length) bloques.push({ ejIdx, texto: bloque.join('\n') });
    currentBloques = bloques;
    currentEjercicios = [];
    selectedEjercicios = new Set();

    let ejercicioNum = 0;
    bloques.forEach((b, bloqueIdx) => {
        if (/^\s*Ejercicio \d+/.test(b.texto)) {
            const ls = b.texto.split('\n');
            const titulo = ls[0].trim();
            const resto  = ls.slice(1).join('\n').trim();
            const headerLine = (titulo.match(/^(Ejercicio \d+(?:\.\d+)?)/) || [null, titulo])[1];
            const nombre = titulo.replace(/^Ejercicio \d+(?:\.\d+)?\s*(?:\([^)]*\))?\s*:\s*/, '').trim();
            const diagNombre = (ejercicioNum < diagGroups.length && diagGroups[ejercicioNum][0])
                ? diagGroups[ejercicioNum][0].nombre : nombre;

            currentEjercicios.push({ bloqueIdx, headerLine, nombre, descripcion: resto, diagNombre });
            const ejN = currentEjercicios.length - 1;

            html += `<div class="ejercicio-block" data-ej-idx="${ejN}">`;
            html += `<label class="ej-select"><input type="checkbox" class="ej-checkbox" data-ej-idx="${ejN}"> Editar este ejercicio</label>`;
            html += `<h3 class='ejercicio-title'>${escHtml(titulo)}</h3>`;

            // Mostrar los diagramas del ejercicio (multifase). Si no hay diagrama (placeholder de «no
            // disponible» o «juego libre») no se pinta nada: el hueco se conserva en la lista, no en la pantalla.
            if (ejercicioNum < diagGroups.length) {
                for (const d of diagGroups[ejercicioNum]) {
                    if (esPlaceholderDiagrama(d)) continue;
                    if (d.titulo) html += `<div class='diagrama-label'>${escHtml(d.titulo)}</div>`;
                    html += `<div class='diagrama-wrap'>${d.svg}</div>`;
                }
            }

            if (resto) html += `<div class='sesion-card estructurada'>${renderCampos(resto)}</div>`;
            html += `</div>`;
            ejercicioNum++;
        } else {
            html += renderBloqueSeccion(b.texto);
        }
    });

    document.getElementById('resultado-contenido').innerHTML = html;
    document.querySelectorAll('.ej-checkbox').forEach(cb => {
        cb.addEventListener('change', () => {
            const idx = parseInt(cb.dataset.ejIdx);
            cb.closest('.ejercicio-block').classList.toggle('selected', cb.checked);
            if (cb.checked) selectedEjercicios.add(idx); else selectedEjercicios.delete(idx);
            actualizarBarraReprompt();
        });
    });
    actualizarBarraReprompt();

    // Restaurar secciones que el modo reglamento puede haber ocultado
    document.querySelector('.downloads').style.display = '';
    document.querySelector('.feedback').style.display = '';

    // Ejercicios consultados
    const ejs = data.ejercicios_usados || [];
    if (ejs.length) {
        document.getElementById('consultados-title').textContent = `Ejercicios consultados (${ejs.length})`;
        document.getElementById('consultados-body').innerHTML = ejs.map(ej => {
            if (typeof ej === 'object') {
                return `<div><strong>${escHtml(ej.nombre || ej.id || '?')}</strong>${ej.duracion_min ? ` (${ej.duracion_min} min)` : ''}</div>`;
            }
            return `<div>${escHtml(String(ej))}</div>`;
        }).join('');
        document.getElementById('consultados-wrap').style.display = '';
    } else {
        document.getElementById('consultados-wrap').style.display = 'none';
    }

    document.getElementById('fb-msg').textContent = '';
    if (mostrar) showResults();
}

// ── Reprompt: corregir uno o varios ejercicios ya generados ─────────────────
function actualizarBarraReprompt() {
    const bar = document.getElementById('reprompt-bar');
    const n = selectedEjercicios.size;
    if (n === 0) {
        bar.style.display = 'none';
        const ta = document.getElementById('reprompt-instruccion');
        ta.value = '';
        ta.style.height = 'auto';
        return;
    }
    bar.style.display = '';
    document.getElementById('reprompt-count').textContent =
        n === 1 ? '1 ejercicio seleccionado' : `${n} ejercicios seleccionados`;
}

function formatEjercicioTexto(headerLine, ej, ejOriginal) {
    const partes = [];
    if (ej.objetivos && typeof ej.objetivos === 'object') {
        ['tacticos', 'tecnicos', 'fisicos'].forEach(k => {
            const v = ej.objetivos[k];
            if (v) partes.push(Array.isArray(v) ? v.join(', ') : String(v));
        });
    }
    // La corrección no siempre rellena los mismos campos que la sesión original
    // (p.ej. "objetivos" u "organización" pueden venir vacíos). En vez de un
    // texto de relleno que sustituya una descripción real por nada útil, se
    // omite esa línea y se conserva la duración original si la corregida no
    // trae una — así no se pierde información ya buena por culpa de un campo
    // que esta vez no vino.
    // Mismo formato que el resto de la sesión (cabecera, Duración, Organización, Puntos clave), que es el que
    // entienden el PDF y el analizador de la API. La descripción corregida es lo principal del cambio: va en
    // «Organización» (si no trae, los objetivos como antes).
    let out = `${headerLine}: ${ej.nombre || 'Ejercicio corregido'}\n`;
    const duracion = ej.duracion_min || (ejOriginal.descripcion.match(/Duración:\s*(\d+)/) || [])[1];
    if (duracion) out += `Duración: ${duracion} min\n`;
    const organizacion = String(ej.descripcion || '').trim() || partes.join(' ');
    if (organizacion) out += `Organización:\n${organizacion}\n`;
    if (Array.isArray(ej.puntos_clave) && ej.puntos_clave.length) {
        out += `Puntos clave:\n${ej.puntos_clave.map(p => `- ${p}`).join('\n')}`;
    }
    return out.trim();
}

// Avisos de la API al corregir un ejercicio (p. ej. «has pedido algo que no es habitual en esta categoría»):
// se hace igualmente y se avisa. Sin avisos no se muestra nada; los repetidos se juntan.
function textoAvisos(avisos) {
    const lista = [...new Set((avisos || []).filter(Boolean))];
    return lista.length ? 'Aviso: ' + lista.join(' ') : '';
}

// Diagramas de la sesión tras corregir un ejercicio: los nuevos ocupan EN SU MISMA POSICIÓN el sitio de los viejos
// (diagGroups se reconstruye por orden de array, así que un filter+push desalinearía los de los ejercicios
// siguientes). Si la corrección no trae diagrama (solo tocó el texto), se conserva el que ya había.
function reemplazarDiagramas(diagramas, diagNombre, nuevoNombre, nuevos) {
    if (!nuevos || nuevos.length === 0) return diagramas.slice();
    const primeraPos = diagramas.findIndex(d => d.nombre === diagNombre);
    const insertarEn = primeraPos === -1 ? diagramas.length : primeraPos;
    const resto = diagramas.filter(d => d.nombre !== diagNombre);
    resto.splice(insertarEn, 0, ...nuevos.map(d => ({ id: diagNombre, nombre: nuevoNombre, titulo: d.titulo || '', svg: d.svg })));
    return resto;
}

const repromptTextarea = document.getElementById('reprompt-instruccion');
repromptTextarea.addEventListener('input', () => {
    repromptTextarea.style.height = 'auto';
    repromptTextarea.style.height = repromptTextarea.scrollHeight + 'px';
});
repromptTextarea.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); aplicarReprompt(); }
});
document.getElementById('btn-reprompt').addEventListener('click', aplicarReprompt);

async function aplicarReprompt() {
    const instruccion = document.getElementById('reprompt-instruccion').value.trim();
    if (!instruccion) { showFormError('Describe qué quieres cambiar.'); return; }
    if (!currentResult || selectedEjercicios.size === 0) return;
    clearFormError();

    const btn = document.getElementById('btn-reprompt');
    const idxs = Array.from(selectedEjercicios);
    const avisosReprompt = [];
    btn.disabled = true;

    for (const idx of idxs) {
        const ej = currentEjercicios[idx];
        btn.textContent = `Corrigiendo ${idxs.indexOf(idx) + 1}/${idxs.length}…`;
        try {
            const resp = await fetch(document.querySelector('[data-reprompt]').dataset.reprompt, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({
                    edad: document.getElementById('edad').value,
                    objetivo: currentObjetivo,
                    nombre: ej.nombre,
                    descripcion: ej.descripcion,
                    instruccion,
                }),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(data.error || `Error del servidor (${resp.status})`);

            const nuevoEjercicio = data.ejercicio || {};
            const nuevasDiagramas = data.diagramas || [];
            avisosReprompt.push(...(nuevoEjercicio.avisos || []));

            // Sustituir el texto del bloque, conservando la numeración "Ejercicio N".
            currentBloques[ej.bloqueIdx].texto = formatEjercicioTexto(ej.headerLine, nuevoEjercicio, ej);

            // Sustituir sus diagramas en su misma posición (ver reemplazarDiagramas).
            const nuevoNombre = nuevoEjercicio.nombre || ej.nombre;
            currentResult.diagramas = reemplazarDiagramas(
                currentResult.diagramas || [], ej.diagNombre, nuevoNombre, nuevasDiagramas);
        } catch (e) {
            showFormError(`Error corrigiendo "${ej.nombre}": ${e.message}`);
        }
    }

    // Reconstruir el texto completo de la sesión a partir de los bloques (solo
    // cambió el/los que se corrigieron) y volver a pintar todo con los datos ya
    // actualizados, para que "Nueva consulta" y las descargas reflejen el cambio.
    currentResult.sesion = currentBloques.map(b => b.texto).join('\n');
    repromptTextarea.value = '';
    repromptTextarea.style.height = 'auto';
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v3.2h-3.2"/></svg> Aplicar cambio';
    renderResults(currentResult);
    const aviso = textoAvisos(avisosReprompt);
    if (aviso) showFormAviso(aviso);
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Downloads ──────────────────────────────────────────────────────────────
document.getElementById('btn-txt').addEventListener('click', () => {
    if (!currentResult) return;
    const texto = currentResult.sesion || currentResult.texto || '';
    const blob = new Blob([texto], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `sesion_${currentEdadSlug}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
});

// Pide el PDF y lo descarga; sirve para el botón de los resultados y para el aviso compacto.
async function descargarPdf(btn) {
    if (!currentResult) return { ok: false, error: 'No hay sesión' };
    const htmlOriginal = btn.innerHTML;       // conserva el icono
    btn.textContent = 'Generando PDF…';
    btn.disabled = true;
    try {
        const resp = await fetch('/pdf/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({
                sesion: currentResult.sesion || currentResult.texto || '',
                edad: currentEdad,
                objetivo: currentResult.objetivo_resumen || currentObjetivo,   // resumen: un objetivo largo llenaría la portada
                duracion: currentDuracion,
                diagramas: currentResult.diagramas || [],
            }),
        });
        if (!resp.ok) throw new Error('Error generando PDF');
        const blob = await resp.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `sesion_${currentEdadSlug}.pdf`;
        a.click();
        URL.revokeObjectURL(a.href);
        return { ok: true };
    } catch (e) {
        return { ok: false, error: e.message };
    } finally {
        btn.innerHTML = htmlOriginal;
        btn.disabled = false;
    }
}

document.getElementById('btn-pdf').addEventListener('click', async () => {
    const r = await descargarPdf(document.getElementById('btn-pdf'));
    if (!r.ok) {
        const msgEl = document.getElementById('fb-msg');
        msgEl.textContent = 'Error generando PDF: ' + r.error;
        msgEl.className = 'feedback-msg err';
    }
});

document.getElementById('btn-txt-top').addEventListener('click', () => document.getElementById('btn-txt').click());
document.getElementById('btn-pdf-top').addEventListener('click', async () => {
    const r = await descargarPdf(document.getElementById('btn-pdf-top'));
    if (!r.ok) showFormError('Error generando PDF: ' + r.error);
});

// Aviso compacto: ver la sesión en la web (con sus avisos) o descargar el PDF sin abrirla.
document.getElementById('listo-ver').addEventListener('click', () => {
    showResults();
    if (_avisoSesion) showFormAviso(_avisoSesion);
});
document.getElementById('listo-pdf').addEventListener('click', async () => {
    const r = await descargarPdf(document.getElementById('listo-pdf'));
    const el = document.getElementById('listo-aviso');
    el.textContent = r.ok ? 'PDF descargado. También puedes ver la sesión en la web.' : 'Error generando PDF: ' + r.error;
});

// ── Feedback ───────────────────────────────────────────────────────────────
document.getElementById('btn-feedback').addEventListener('click', async () => {
    const cambios = document.getElementById('fb-cambios').value.trim();
    const msgEl = document.getElementById('fb-msg');
    if (!cambios) {
        msgEl.textContent = 'Describe brevemente qué cambiaste.';
        msgEl.className = 'feedback-msg err';
        return;
    }
    const rating = parseInt(document.getElementById('fb-rating').value);
    const ts = new Date().toISOString().replace(/[:.]/g,'').slice(0,15);
    try {
        const resp = await fetch('/feedback/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({
                timestamp: ts,
                edad: currentEdad,
                duracion: currentDuracion,
                objetivo: currentObjetivo,
                sesion_generada: currentResult?.sesion || '',
                cambios_realizados: cambios,
                rating,
                ejercicios_usados: currentResult?.ejercicios_usados || [],
            }),
        });
        if (resp.ok) {
            msgEl.textContent = '✓ Sesión guardada. ¡Gracias!';
            msgEl.className = 'feedback-msg ok';
        } else {
            throw new Error();
        }
    } catch {
        msgEl.textContent = 'Error guardando. Inténtalo de nuevo.';
        msgEl.className = 'feedback-msg err';
    }
});

// ── State helpers ──────────────────────────────────────────────────────────
function showEmpty() {
    document.getElementById('form-sesion').style.display = currentMode === 'sesion' ? '' : 'none';
    document.getElementById('form-reglamento').style.display = currentMode === 'reglamento' ? '' : 'none';
    rgActualizarCabecera();
    detenerMensajes();
    document.getElementById('loading').classList.remove('visible');
    document.getElementById('listo').classList.remove('visible');
    document.getElementById('results').classList.remove('visible');
}
// Mensajes mientras se espera: curiosidades reales del baloncesto, alguna broma y mensajes de «pensando».
// Solo datos que se pueden comprobar; la espera puede llegar a 2 minutos y así se nota que sigue trabajando.
const MENSAJES_ESPERA = {
    sesion: [
        'Colocando los conos… que luego nadie recogerá.',
        'Dato: el baloncesto lo inventó James Naismith en 1891, con una cesta de melocotones como canasta.',
        'Revisando que ningún ejercicio deje a nadie en una fila esperando.',
        'Dato: al principio había que sacar el balón de la cesta a mano, porque no tenía el fondo abierto.',
        'Contando los pasos del pívot… y esta vez no hay pasos.',
        'Dato: el tablero se creó para que el público de las gradas no desviara los tiros.',
        'Ajustando la intensidad a la edad de cada grupo.',
        'Dato: el aro mide 45 cm de diámetro y está a 3,05 m del suelo, en todas las categorías de FIBA.',
        'Buscando el balón que siempre falta en la bolsa.',
        'Dato: el minibasket se juega con balón de talla 5, de unos 70 cm de perímetro.',
        'Pensando en las progresiones: de más fácil a más difícil.',
        'Dato: la línea de tres puntos llegó a las competiciones FIBA en 1984.',
    ],
    reglamento: [
        'Hojeando el reglamento…',
        'Buscando el artículo exacto, no uno parecido.',
        'Comprobando si la norma cambia en tu categoría.',
        'Dato: el aro mide 45 cm de diámetro y está a 3,05 m del suelo.',
        'Contrastando la respuesta con el texto del reglamento.',
    ],
};
let _tipTimer = null;
let _tipIdx = 0;

function detenerMensajes() {
    if (_tipTimer) { clearInterval(_tipTimer); _tipTimer = null; }
}
function iniciarMensajes(modo) {
    detenerMensajes();
    const lista = MENSAJES_ESPERA[modo] || [];
    const el = document.getElementById('loading-tip');
    if (!el || !lista.length) return;
    _tipIdx = Math.floor(Math.random() * lista.length);
    el.classList.remove('oculto');
    el.textContent = lista[_tipIdx];
    _tipTimer = setInterval(() => {
        el.classList.add('oculto');
        setTimeout(() => {
            _tipIdx = (_tipIdx + 1) % lista.length;
            el.textContent = lista[_tipIdx];
            el.classList.remove('oculto');
        }, 350);
    }, 6500);
}

function showLoading(modo) {
    modo = modo || currentMode;
    document.getElementById('form-sesion').style.display = 'none';
    document.getElementById('form-reglamento').style.display = 'none';
    document.getElementById('reglamento-hilo').style.display = 'none';
    document.getElementById('results').classList.remove('visible');
    document.getElementById('listo').classList.remove('visible');
    document.getElementById('loading-text').textContent = 'Generando sesión… (puede tardar hasta 2 minutos)';
    document.getElementById('loading').classList.add('visible');
    document.getElementById('btn-generar').disabled = true;
    document.getElementById('btn-reglamento').disabled = true;
    iniciarMensajes(modo);
}
function hideLoading() {
    detenerMensajes();
    document.getElementById('loading').classList.remove('visible');
    document.getElementById('btn-generar').disabled = _cuentaAtras !== null;
    document.getElementById('btn-reglamento').disabled = _cuentaAtras !== null;
}
// Aviso compacto al terminar la sesión: elegir entre verla en la web o bajar el PDF.
let _avisoSesion = '';
function mostrarListo(data) {
    hideLoading();
    const n = (typeof currentEjercicios !== 'undefined') ? currentEjercicios.length : 0;
    const partes = [currentEdadSlug !== 'general' ? currentEdad : '', currentDuracion ? currentDuracion + ' min' : '',
                    n ? n + ' ejercicios' : ''].filter(Boolean);
    document.getElementById('listo-meta').textContent = partes.join(' · ');
    _avisoSesion = textoAvisos(data.avisos);
    document.getElementById('listo-aviso').textContent = _avisoSesion;
    document.getElementById('listo').classList.add('visible');
    document.getElementById('listo-ver').focus();
}
function showResults() {
    document.getElementById('listo').classList.remove('visible');
    hideLoading();
    document.getElementById('form-sesion').style.display = 'none';
    document.getElementById('form-reglamento').style.display = 'none';
    document.getElementById('reglamento-hilo').style.display = 'none';
    document.getElementById('btn-nueva-txt').textContent = currentMode === 'reglamento' ? 'Nueva consulta' : 'Nueva sesión';
    document.getElementById('results').classList.add('visible');
}
