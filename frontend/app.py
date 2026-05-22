# frontend/app.py
import html
import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import os
import re
from fpdf import FPDF

API_URL         = os.environ.get("API_URL", "http://mipizarra-api:8090")
INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "")


def api_headers() -> dict:
    """Cabeceras para llamar a la API. Incluye X-Internal-Secret si está configurado."""
    h = {"Content-Type": "application/json"}
    if INTERNAL_SECRET:
        h["X-Internal-Secret"] = INTERNAL_SECRET
    return h


def safe(texto: str) -> str:
    """Escapa HTML del LLM antes de meterlo en un st.markdown(unsafe_allow_html=True).
    El contenido viene de un modelo no confiable y podría incluir <script>...</script>."""
    return html.escape(texto or "")

st.set_page_config(
    page_title="MiPizarra",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────
tema = st.sidebar.selectbox("🎨 Tema", ["Oscuro", "Claro"], index=0)

ACCENT      = "#4f8ef7"
ACCENT_DARK = "#3a7ae0"

CSS_OSCURO = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@700;800&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    background-color: #0d1117;
    color: #e6edf3;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: #161b22; }}
::-webkit-scrollbar-thumb {{ background: #30363d; border-radius: 3px; }}

[data-testid="stSidebar"] {{
    background-color: #0d1117;
    border-right: 1px solid #21262d;
}}

/* Logo */
.logo-wrap {{
    padding: 1.25rem 0 1rem 0;
    border-bottom: 1px solid #21262d;
    margin-bottom: 1.5rem;
}}
.logo-main {{
    font-family: 'Sora', sans-serif;
    font-weight: 800;
    font-size: 1.9rem;
    letter-spacing: -0.03em;
    line-height: 1;
    color: #ffffff;
}}
.logo-main em {{
    font-style: normal;
    color: {ACCENT};
}}
.logo-sub {{
    font-size: 0.72rem;
    color: #7d8590;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 4px;
}}

/* Form labels */
.field-label {{
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #7d8590;
    margin-bottom: 6px;
    margin-top: 14px;
}}

/* Button */
div[data-testid="stButton"] > button {{
    background: {ACCENT} !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.04em !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.65rem 1.5rem !important;
    width: 100% !important;
    transition: background 0.15s !important;
}}
div[data-testid="stButton"] > button:hover {{
    background: {ACCENT_DARK} !important;
}}

/* Session result cards */
.sesion-card {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    font-size: 0.92rem;
    line-height: 1.8;
    white-space: pre-wrap;
    color: #c9d1d9;
    margin-bottom: 0.75rem;
}}
.ejercicio-title {{
    font-family: 'Sora', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    color: #ffffff;
    border-left: 3px solid {ACCENT};
    padding-left: 0.75rem;
    margin-bottom: 0.75rem;
}}
.section-chip {{
    display: inline-block;
    background: #1c2333;
    color: {ACCENT};
    border: 1px solid #2d3748;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}
.badge-teoria {{
    display: inline-block;
    background: #0d2218;
    color: #3fb950;
    border: 1px solid #1a7f37;
    border-radius: 6px;
    padding: 3px 12px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}
.badge-no-teoria {{
    display: inline-block;
    background: #1c1a10;
    color: #d29922;
    border: 1px solid #6e451d;
    border-radius: 6px;
    padding: 3px 12px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}
.diagrama-label {{
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #7d8590;
    margin-bottom: 6px;
}}
.diagrama-wrap {{
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 1.5rem;
}}
.empty-state {{
    margin-top: 5rem;
    text-align: center;
    padding: 2rem;
}}
.empty-icon {{
    font-size: 3.5rem;
    margin-bottom: 1rem;
    filter: grayscale(0.3);
}}
.empty-title {{
    font-family: 'Sora', sans-serif;
    font-weight: 700;
    font-size: 1.3rem;
    color: #e6edf3;
    margin-bottom: 0.4rem;
}}
.empty-sub {{
    font-size: 0.85rem;
    color: #7d8590;
    line-height: 1.6;
}}
hr {{ border-color: #21262d; }}
[data-testid="stExpander"] {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
}}
</style>
"""

CSS_CLARO = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@700;800&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    background-color: #f6f8fa;
    color: #1c1c1e;
}}

[data-testid="stSidebar"] {{
    background-color: #ffffff;
    border-right: 1px solid #d0d7de;
}}

.logo-wrap {{
    padding: 1.25rem 0 1rem 0;
    border-bottom: 1px solid #d0d7de;
    margin-bottom: 1.5rem;
}}
.logo-main {{
    font-family: 'Sora', sans-serif;
    font-weight: 800;
    font-size: 1.9rem;
    letter-spacing: -0.03em;
    line-height: 1;
    color: #1c1c1e;
}}
.logo-main em {{ font-style: normal; color: {ACCENT}; }}
.logo-sub {{
    font-size: 0.72rem;
    color: #6e7781;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 4px;
}}
.field-label {{
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6e7781;
    margin-bottom: 6px;
    margin-top: 14px;
}}
div[data-testid="stButton"] > button {{
    background: {ACCENT} !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.65rem 1.5rem !important;
    width: 100% !important;
}}
div[data-testid="stButton"] > button:hover {{ background: {ACCENT_DARK} !important; }}

.sesion-card {{
    background: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    font-size: 0.92rem;
    line-height: 1.8;
    white-space: pre-wrap;
    color: #24292f;
    margin-bottom: 0.75rem;
}}
.ejercicio-title {{
    font-family: 'Sora', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    color: #1c1c1e;
    border-left: 3px solid {ACCENT};
    padding-left: 0.75rem;
    margin-bottom: 0.75rem;
}}
.section-chip {{
    display: inline-block;
    background: #dbeafe;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}
.badge-teoria {{
    display: inline-block;
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
    border-radius: 6px;
    padding: 3px 12px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}
.badge-no-teoria {{
    display: inline-block;
    background: #fff3cd;
    color: #856404;
    border: 1px solid #ffd576;
    border-radius: 6px;
    padding: 3px 12px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}
.diagrama-label {{
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #6e7781;
    margin-bottom: 6px;
}}
.diagrama-wrap {{
    background: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 1.5rem;
}}
.empty-state {{ margin-top: 5rem; text-align: center; padding: 2rem; }}
.empty-icon {{ font-size: 3.5rem; margin-bottom: 1rem; }}
.empty-title {{
    font-family: 'Sora', sans-serif;
    font-weight: 700;
    font-size: 1.3rem;
    color: #1c1c1e;
    margin-bottom: 0.4rem;
}}
.empty-sub {{ font-size: 0.85rem; color: #6e7781; line-height: 1.6; }}
hr {{ border-color: #d0d7de; }}
[data-testid="stExpander"] {{
    background: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 8px;
}}
</style>
"""

st.markdown(CSS_OSCURO if tema == "Oscuro" else CSS_CLARO, unsafe_allow_html=True)


# ─── PDF ──────────────────────────────────────────────────────────────────
def generar_pdf(sesion_texto: str, edad: str, objetivo: str, duracion: int, diagramas: list) -> bytes:
    import cairosvg
    import tempfile

    BLUE_R, BLUE_G, BLUE_B = 79, 142, 247   # #4f8ef7
    DARK_R, DARK_G, DARK_B = 30, 30, 40

    class PDF_MiPizarra(FPDF):
        def header(self):
            self.set_fill_color(BLUE_R, BLUE_G, BLUE_B)
            self.rect(0, 0, 210, 7, "F")
            self.set_y(11)
            self.set_font("Helvetica", "B", 22)
            self.set_text_color(DARK_R, DARK_G, DARK_B)
            self.cell(0, 9, "MiPizarra", align="C", ln=True)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(130, 130, 140)
            self.cell(0, 4, "Asistente de entrenamiento de baloncesto", align="C", ln=True)
            self.ln(2)

        def footer(self):
            self.set_y(-13)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(160, 160, 170)
            self.cell(0, 8, f"Pág. {self.page_no()}", align="C")

    pdf = PDF_MiPizarra()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(left=20, top=30, right=20)
    pdf.add_page()

    # Caja de metadatos
    duracion_text = f"{duracion} min" if duracion else "Flexible"
    edad_text = edad if edad else "General"
    objetivo_corto = objetivo[:40] + "..." if len(objetivo) > 40 else objetivo

    y_meta = pdf.get_y()
    pdf.set_fill_color(240, 244, 255)
    pdf.set_draw_color(200, 215, 250)
    pdf.rect(20, y_meta, 170, 11, "FD")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(50, 80, 160)
    pdf.set_xy(20, y_meta + 1)
    meta_str = f"Categoría: {edad_text}   ·   Duración: {duracion_text}   ·   Objetivo: {objetivo_corto}"
    pdf.cell(170, 9, meta_str, align="C", ln=True)
    pdf.ln(7)

    def clean(txt):
        return (
            txt.replace("–", "-").replace("—", "-")
               .replace("‘", "'").replace("’", "'")
               .replace("“", '"').replace("”", '"')
               .replace("•", "*")
               .encode("latin-1", errors="ignore").decode("latin-1")
        )

    def add_diagram(ejercicio_num):
        if ejercicio_num < len(diagramas):
            diagrama = diagramas[ejercicio_num]
            svg_content = diagrama.get("svg", "")
            if svg_content:
                try:
                    if pdf.get_y() > 170:
                        pdf.add_page()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        cairosvg.svg2png(
                            bytestring=svg_content.encode("utf-8"),
                            write_to=tmp.name,
                            output_width=900,
                        )
                        pdf.image(tmp.name, x=20, w=170)
                        os.unlink(tmp.name)
                    pdf.set_x(pdf.l_margin)
                    pdf.ln(4)
                except Exception:
                    pass

    ejercicio_actual = -1
    pagina_recien_nueva = False   # False = hay contenido en la página actual
    lineas = sesion_texto.split("\n")

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            pdf.ln(2)
            continue

        linea = clean(linea)

        # Detección de sección principal (**TEXTO**)
        if linea.startswith("**") and linea.endswith("**"):
            titulo = linea.replace("**", "").strip()
            titulo_up = titulo.upper()

            # PARTE PRINCIPAL y VUELTA A LA CALMA arrancan siempre en página nueva
            if "PARTE PRINCIPAL" in titulo_up or "VUELTA A LA CALMA" in titulo_up:
                pdf.add_page()
                pagina_recien_nueva = True
            else:
                pdf.ln(4)
                pagina_recien_nueva = False

            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(BLUE_R, BLUE_G, BLUE_B)
            pdf.set_x(pdf.l_margin)
            pdf.cell(170, 7, titulo[:60], ln=True)
            pdf.set_draw_color(BLUE_R, BLUE_G, BLUE_B)
            pdf.set_line_width(0.5)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)
            pdf.set_font("Helvetica", size=10)
            pdf.set_text_color(40, 40, 50)
            continue

        # Detección de ejercicio
        if re.match(r"Ejercicio \d+", linea):
            if not pagina_recien_nueva:
                pdf.add_page()
            pagina_recien_nueva = False
            ejercicio_actual += 1

            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(DARK_R, DARK_G, DARK_B)
            pdf.set_x(pdf.l_margin)
            pdf.cell(170, 8, linea[:80], ln=True)
            pdf.ln(2)

            add_diagram(ejercicio_actual)

            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", size=10)
            pdf.set_text_color(40, 40, 50)
            continue

        # Subsecciones en negrita
        subsec_keys = ["Juego:", "Reglas:", "Organización:", "Puntos clave:", "Espacio:",
                       "Duración:", "Fundamentos:", "Puntos Clave:"]
        if any(linea.startswith(k) for k in subsec_keys):
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(60, 60, 70)
            pdf.multi_cell(170, 5, linea)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", size=10)
            pdf.set_text_color(40, 40, 50)
            continue

        # Texto normal
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(50, 50, 60)
        pdf.multi_cell(170, 5, linea)

    return bytes(pdf.output())


# ─── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class='logo-wrap'>
        <div class='logo-main'>Mi<em>Pizarra</em></div>
        <div class='logo-sub'>Asistente de entrenamiento</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='field-label'>Categoría</div>", unsafe_allow_html=True)
    edad = st.selectbox(
        "Categoría",
        ["-- No especificar --", "Prebenjamín", "Benjamín", "Alevín", "Infantil", "Cadete", "Junior", "Senior"],
        index=0,
        label_visibility="collapsed",
    )
    edad_map = {
        "Prebenjamín": "U8", "Benjamín": "U10", "Alevín": "U12",
        "Infantil": "U14", "Cadete": "U16", "Junior": "U18", "Senior": "Senior",
    }
    edad_api = edad_map.get(edad) if edad != "-- No especificar --" else None

    st.markdown("<div class='field-label'>Duración</div>", unsafe_allow_html=True)
    usar_duracion = st.checkbox("Especificar duración", value=False)
    duracion = st.slider("minutos", 45, 120, 90, 15, label_visibility="collapsed") if usar_duracion else None

    st.markdown("<div class='field-label'>Descripción del entrenamiento</div>", unsafe_allow_html=True)
    if "objetivo_text" not in st.session_state:
        st.session_state.objetivo_text = ""

    objetivo = st.text_area(
        "Descripción",
        value=st.session_state.objetivo_text,
        placeholder="¿Qué quieres trabajar hoy?\n\nEjemplos:\n• Tiro en suspensión\n• Defensa bloqueo directo\n• Transición rápida",
        height=130,
        label_visibility="collapsed",
        key="objetivo_input",
    )
    st.session_state.objetivo_text = objetivo

    # JavaScript: Enter envía el formulario (Shift+Enter = nueva línea)
    st.markdown("""
    <script>
    (function() {
        function attachEnterListener() {
            var textareas = document.querySelectorAll('textarea');
            textareas.forEach(function(ta) {
                if (ta.dataset.enterBound) return;
                ta.dataset.enterBound = "1";
                ta.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        var btns = document.querySelectorAll('button');
                        for (var i = 0; i < btns.length; i++) {
                            if (btns[i].innerText.toUpperCase().includes('GENERAR')) {
                                btns[i].click();
                                return;
                            }
                        }
                    }
                });
            });
        }
        var obs = new MutationObserver(attachEnterListener);
        obs.observe(document.body, { childList: true, subtree: true });
        attachEnterListener();
    })();
    </script>
    """, unsafe_allow_html=True)

    st.markdown("<div class='field-label'>Opciones</div>", unsafe_allow_html=True)
    generar_diagramas = st.toggle("Generar diagramas", value=True)

    st.markdown("<br>", unsafe_allow_html=True)
    generar = st.button("⚡ Generar sesión", use_container_width=True, type="primary")
    st.markdown(
        "<div style='text-align:center;font-size:0.7rem;color:#7d8590;margin-top:6px;'>"
        "Enter para generar · Shift+Enter para nueva línea</div>",
        unsafe_allow_html=True,
    )


# ─── Estado del resultado ─────────────────────────────────────────────────
if "resultado" not in st.session_state:
    st.session_state.resultado = None


# ─── Llamada API ──────────────────────────────────────────────────────────
if generar:
    if not objetivo.strip():
        st.warning("Describe qué quieres trabajar en el entrenamiento.")
    else:
        with st.spinner("Generando sesión… (puede tardar hasta 2 minutos)"):
            try:
                payload = {"objetivo": objetivo, "generar_diagramas": generar_diagramas}
                if edad_api:
                    payload["edad"] = edad_api
                if duracion:
                    payload["duracion"] = duracion

                resp = requests.post(f"{API_URL}/generar", json=payload, headers=api_headers(), timeout=300)
                resp.raise_for_status()
                st.session_state.resultado = resp.json()
            except Exception as e:
                st.error(f"Error: {e}")


# ─── Resultado ────────────────────────────────────────────────────────────
if st.session_state.resultado:
    r = st.session_state.resultado

    # Badges
    if r.get("teoria_usada"):
        st.markdown("<span class='badge-teoria'>✓ Enriquecido con teoría</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='badge-no-teoria'>⚠ Sin teoría adicional</span>", unsafe_allow_html=True)

    texto = r.get("sesion", r.get("texto", ""))
    texto = re.sub(r'\[ej_\d+\]\s*', '', texto)
    diagramas = r.get("diagramas", [])

    # Parsear en bloques por ejercicio
    bloques = []
    lineas = texto.split("\n")
    bloque_actual = []
    ejercicio_idx = -1

    for linea in lineas:
        if re.match(r'\s*Ejercicio \d+', linea):
            if bloque_actual:
                bloques.append(("texto", "\n".join(bloque_actual)))
                bloque_actual = []
            ejercicio_idx += 1
            bloque_actual.append(linea)
        else:
            bloque_actual.append(linea)

    if bloque_actual:
        bloques.append(("texto", "\n".join(bloque_actual)))

    # Renderizar intercalado
    ejercicio_num = 0
    for _, contenido in bloques:
        es_ejercicio = bool(re.match(r'\s*Ejercicio \d+', contenido[:20]))

        if es_ejercicio:
            primera_linea = contenido.split("\n")[0].strip()
            resto = "\n".join(contenido.split("\n")[1:]).strip()

            st.markdown(f"<div class='ejercicio-title'>{safe(primera_linea)}</div>", unsafe_allow_html=True)

            if ejercicio_num < len(diagramas):
                diagrama = diagramas[ejercicio_num]
                st.markdown(f"<div class='diagrama-label'>{safe(diagrama.get('nombre', ''))}</div>", unsafe_allow_html=True)
                import re as _re
                _vb = _re.search(r'viewBox="0 0 (\d+) (\d+)"', diagrama['svg'])
                _svg_w, _svg_h = (int(_vb.group(1)), int(_vb.group(2))) if _vb else (815, 870)
                _iframe_h = int(_svg_h * 760 / _svg_w) + 10
                html_svg = f"""<!DOCTYPE html>
<html><head><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#faf8f0;overflow:hidden;padding:0 12px}}
svg{{width:100%;height:auto;display:block}}
</style></head>
<body>{diagrama['svg']}</body></html>"""
                components.html(html_svg, height=_iframe_h)

            if resto:
                st.markdown(f"<div class='sesion-card'>{safe(resto)}</div>", unsafe_allow_html=True)

            ejercicio_num += 1
        else:
            contenido_strip = contenido.strip()
            if contenido_strip:
                st.markdown(f"<div class='sesion-card'>{safe(contenido_strip)}</div>", unsafe_allow_html=True)

    # Ejercicios consultados
    ids_usados = r.get("ejercicios_usados", [])
    if ids_usados:
        with st.expander(f"📋 Ejercicios consultados ({len(ids_usados)})"):
            for ej in ids_usados:
                if isinstance(ej, dict):
                    tiene = "📐 " if "diagrama" in ej else ""
                    st.markdown(f"- {tiene}**{ej.get('nombre','?')}** ({ej.get('duracion_min','?')} min)")
                else:
                    st.markdown(f"- {ej}")

    # Descargas
    st.markdown("<br>", unsafe_allow_html=True)
    col_txt, col_pdf = st.columns(2)
    edad_fn = edad.lower().replace(" ", "_") if edad else "general"
    obj_fn = objetivo.replace(" ", "_").replace("\n", "_")[:30]

    with col_txt:
        st.download_button(
            label="⬇ Descargar (.txt)",
            data=texto.encode("utf-8"),
            file_name=f"sesion_{edad_fn}_{obj_fn}.txt",
            mime="text/plain",
        )
    with col_pdf:
        pdf_bytes = generar_pdf(
            texto,
            edad if edad else "General",
            objetivo,
            duracion if duracion else 0,
            r.get("diagramas", []),
        )
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_bytes,
            file_name=f"sesion_{edad_fn}_{obj_fn}.pdf",
            mime="application/pdf",
        )

    # Feedback
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:0.75rem;font-weight:600;letter-spacing:0.08em;"
        "text-transform:uppercase;color:#7d8590;margin-bottom:0.75rem;'>"
        "¿Usaste esta sesión en un entrenamiento real?</div>",
        unsafe_allow_html=True,
    )
    col_fb, col_rt = st.columns([3, 1])
    with col_rt:
        rating = st.selectbox(
            "Valoración",
            ["⭐ 1", "⭐⭐ 2", "⭐⭐⭐ 3", "⭐⭐⭐⭐ 4", "⭐⭐⭐⭐⭐ 5"],
            index=2,
            label_visibility="collapsed",
        )
    with col_fb:
        cambios = st.text_area(
            "Cambios realizados",
            placeholder="Ej: Quité el 3c2 porque solo había 8 jugadores.",
            height=80,
            label_visibility="collapsed",
        )

    if st.button("💾 Guardar sesión usada"):
        if not cambios.strip():
            st.warning("Describe brevemente qué cambiaste.")
        else:
            try:
                import datetime
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                resp_fb = requests.post(
                    f"{API_URL}/guardar_feedback",
                    json={
                        "timestamp": ts,
                        "edad": edad,
                        "duracion": duracion,
                        "objetivo": objetivo,
                        "sesion_generada": texto,
                        "cambios_realizados": cambios,
                        "rating": int(rating[1]),
                        "ejercicios_usados": r.get("ejercicios_usados", []),
                    },
                    headers=api_headers(),
                    timeout=10,
                )
                if resp_fb.status_code == 200:
                    st.success("✓ Sesión guardada. ¡Gracias!")
                else:
                    st.error("Error guardando. Inténtalo de nuevo.")
            except Exception as e:
                st.error(f"Error: {e}")

else:
    # Estado vacío
    st.markdown("""
    <div class='empty-state'>
        <div class='empty-icon'>🏀</div>
        <div class='empty-title'>Diseña tu próximo entrenamiento</div>
        <div class='empty-sub'>
            Selecciona categoría y duración en el panel izquierdo,<br>
            describe el objetivo y pulsa <strong>Generar sesión</strong>.
        </div>
    </div>
    """, unsafe_allow_html=True)
