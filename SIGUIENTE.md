# MiPizarra — siguiente sesión

> **Léeme al abrir un chat sobre MiPizarra**. Resume estado, próximo paso y decisiones ya tomadas.

## Empieza por aquí (actualizado 2026-08-29)

**Dónde corre ahora mismo:** en local, en el PC de Nacho (RTX 5060 Ti 16GB) vía
Docker Compose — no en el LXC del servidor (eso es un tema aparte, ver "Decisión de
despliegue" en la sección de abajo). El resto de este fichero, más viejo, dice que
corre en el servidor con GTX 1060 6GB — eso describe el diseño original de mayo,
ya no el estado real.

**Estado:** revisión de arquitectura completa (28-29 de agosto) — RAG con
colecciones separadas, diagramas con JSON Schema + validador semántico + reintento,
auditoría 1 a 1 de los 63 ejercicios de `exercises.json`, regla de bloqueo directo
corregida en todo el proyecto, y dos bugs de truncado de sesión arreglados con
reintento automático ante fallo real. Todo probado en vivo contra la app real y
comiteado (ver commits `f911196`..`75530a9`). Nada pendiente de commitear.

**Próximo paso — sin nada más bloqueando antes:** probar `qwen3.5:4b` **en local**
(no en el servidor todavía). Salió el 2026-03-02, mejora generacional limpia sobre
`qwen3:4b-instruct` (256K contexto, tools, visión). Verificar antes de dar nada por
bueno: (a) que el thinking (activo por defecto en 3.5) se desactiba con
`chat_template_kwargs: {"enable_thinking": false}` — mecanismo distinto del
`"think": false` de Ollama que ya falló con qwen3:4b: y (b) que el resultado supera
en calidad a `qwen3:4b-instruct` antes de cambiar el default. Detalle completo:
sección "Revisión de arquitectura (2026-08-29)" más abajo, punto 2 de los pendientes.

**Pendiente, no bloqueante:** revisión visual real de los diagramas de
`ej_060`/`ej_061`/`ej_062` y del arreglo del tiro a pista completa — solo
verificados numéricamente, nunca vistos renderizados de verdad.

## Qué es MiPizarra

Asistente local de entrenamiento de baloncesto. Genera sesiones (texto) y diagramas tácticos
(JSON → SVG via renderer determinista). Corre en LXC Proxmox con GTX 1060 6GB.

### Tres modos de chat previstos (pendiente de implementar)

1. **Modo sesión** — el entrenador describe categoría, duración y objetivo → el modelo genera la sesión completa con ejercicios, tiempos y diagramas.
2. **Modo ejercicio** — el entrenador pide un ejercicio concreto ("dame un 2c1 para alevín con diagrama") → el modelo genera solo ese ejercicio con su JSON y SVG.
3. **Modo reglamento / dudas** — el entrenador pregunta sobre reglas, conceptos técnicos o situaciones de partido ("¿qué es el paso cero?", "¿cuántos tiempos muertos tiene infantil?") → respuesta directa sin generar sesión ni diagrama.

Los tres modos comparten el mismo modelo pero con system prompts distintos. Pendiente: definir los tres SYSTEM prompts diferenciados y actualizar la API para enrutarlos.

- LLM base: **Qwen3-4B** en Ollama (Q4_K_M, ~2.5 GB VRAM). Equivale en calidad a Qwen2.5-7B.
- Fine-tuning: **LoRA puro bf16** en local (RTX 5060 Ti) con Unsloth; **QLoRA 4-bit** en servidor (GTX 1060).
- Modelo "profesor" para destilar dataset sintético: **qwen2.5:7b-instruct-q4_K_M**.
- Carpeta canónica del servicio: **`mipizarra/`** (antes `hoops-coach`).

## Revisión de arquitectura (2026-08-29) — leer esto primero

Revisión completa con Opus tras las pruebas en vivo del 28-29/08 (ver commit
`f911196`). Diagnóstico: los dos síntomas abiertos (diagramas poco fiables en texto
libre, RAG que "no notaba" que estuviera conectado) eran bugs de arquitectura, no
falta de capacidad del modelo. Se arreglaron el mismo día, ya probados en vivo contra
la instancia real (que corre en local, PC con RTX 5060 Ti — no en el LXC del servidor,
pese a lo que dice la sección de abajo, que describe el diseño original de 2026-05).

**Hecho y verificado hoy:**
1. `generar_coordenadas_ejercicio` / `generar_diagrama_desde_texto` / `generar_ejercicio_unico`
   usaban `MODEL` = `qwen3:4b` (con thinking) mientras que `generar_sesion` y
   `responder_duda_reglamento` ya habían migrado a `qwen3:4b-instruct`. El JSON de
   diagramas se generaba con el modelo que sabíamos que fallaba bajo restricción de
   formato. `MODEL` ahora también apunta a `-instruct` por defecto (`api/rag_engine.py`,
   `docker-compose.yml`, `.env.example`).
2. `generar_coordenadas_ejercicio` ahora pasa un **JSON Schema real** en `format`
   (antes `"json"` a secas — solo garantizaba JSON válido, cualquier forma). Ollama
   compila el schema a gramática (XGrammar) y restringe la decodificación.
3. Nuevo `_validar_diagrama()`: valida lo que el schema no puede expresar — que
   `de`/`a`/`portador` referencien jugadores realmente declarados, y que el nº de
   atacantes/defensores cuadre con el `NcM` del nombre (reutiliza el regex de
   `_nivel_oposicion`, factorizado en `_extraer_conteo_nc_m`). Si falla, un reintento
   señalando el error concreto; si sigue fallando, `None` — sin diagrama es mejor que
   un diagrama que contradice el texto. **Confirmado en logs reales**: el validador
   atrapó un `desplazamiento sin a_pos` (la causa exacta de "a veces no genera nada" —
   el renderer descartaba esos movimientos en silencio), se recuperó en 2 de 3 casos
   tras el reintento, y en el que no pudo, devolvió `None` limpio en vez de un dibujo
   roto.
4. `parsear_ejercicios_de_sesion` (`api/main.py`) no capturaba `Qué cambia respecto a
   N.1:` en las variantes (iba antes de `Organización:` en la plantilla) — la sustancia
   de la variante se perdía y su diagrama se generaba a ciegas. Ahora se captura y se
   antepone a la descripción.
5. `construir_contexto_teoria` concatenaba teoria+planificacion+reglamento y el
   resultado se truncaba a **800 caracteres** en `generar_sesion` — con chunks de
   ~530 chars de media, sobrevivían ~1,5 chunks y las colecciones `planificacion` y
   `reglamento` (al ir después en la concatenación) nunca llegaban al prompt. Ahora
   presupuesto de 900 chars **por colección** (no un corte global), sin truncado
   adicional en `generar_sesion`. `num_ctx` subido de 6144 a 8192 para dar margen.
6. `/reglamento` **no hacía retrieval en absoluto** — respondía solo de memoria
   paramétrica pese a tener 1.238 chunks de reglas FIBA/minibasket/normativa aragonesa
   ya indexados sin usar. Ahora consulta la colección `reglamento` (6 chunks, tope
   3000 chars) antes de preguntar al modelo. **Probado en vivo**: pregunta sobre
   tiempos muertos en Juegos Escolares de Aragón infantil → recuperó el fragmento
   correcto de `juegos_escolares_2223.pdf` / `normativa_tecnica_jjee_2324.pdf` (no la
   regla FIBA genérica) y respondió citándolo.

**Hecho (2026-08-29, sesión 2) — colecciones separadas y auditoría de exercises.json:**

- **`teoria_md` separada de `teoria`.** `tools/indexar_colecciones.py` es el script
  canónico (confirmado: coincide con las 3 colecciones reales y `CHUNK_SIZE=256`
  observado; `indexar_pdfs.py` está obsoleto, crea una colección `teoria_baloncesto`
  que no existe en la instancia real). Se cambió a 4 colecciones: `teoria_md` (los 20
  `.md` curados, incluidos los dos de reglamento), `teoria`, `planificacion`,
  `reglamento` — cada una solo PDFs salvo `teoria_md`. Reindexado en local con
  `docker exec mipizarra-api python /app/tools/indexar_colecciones.py` (backup previo
  en `data/chroma_db.bak_20260829/`). `construir_contexto_teoria` y
  `responder_duda_reglamento` ahora consultan `teoria_md` con presupuesto propio y
  prioridad. Verificado en vivo: una pregunta sobre bloqueos directos en infantil trajo
  contenido de `contenidos_por_edad_lineas_rojas.md` en vez de solo PDFs genéricos.
- **Resuelto (2026-08-29): contradicción sobre bloqueo directo en Infantil/U14.**
  `data/teoria/contenidos_por_edad_lineas_rojas.md` decía que el bloqueo directo
  empieza en Cadete/U16 (Infantil/U14 solo bloqueos indirectos); otras 4 fuentes
  decían "esporádico ya en U14". Nacho confirmó que la regla correcta es la del
  `.md`: **bloqueo directo solo desde Cadete/U16, nada de directo en Infantil/U14**
  (bloqueo indirecto sí, desde U14). Corregidas las 4 fuentes que estaban mal:
  `api/prompts.py` (`SYSTEM_SESION` y `SYSTEM_EJERCICIO`), `docs/esquema-ejercicios.md`,
  `docs/coordenadas.md` (tabla y notas — tenía la misma regla vieja, no detectado en
  el primer barrido), `tools/exportar_a_ollama.py` (Modelfile del modelo fine-tuned,
  tampoco detectado antes) y `ej_002` en `exercises.json` (le quitado U14 de
  `edades`; `ej_008` ya estaba bien, U16+). Verificado en vivo: la misma pregunta de
  antes ("¿en infantil se pueden trabajar bloqueos directos?") ahora responde con
  razonamiento coherente con el resto del proyecto en vez de una coincidencia con
  fondo correcto pero justificación inventada.
- **Auditoría 1 a 1 de los 63 ejercicios de `exercises.json`.** Validación estructural
  automatizada (referencias de movimientos, rango de coordenadas, conteo NcM del
  nombre) + lectura manual completa del contenido. Resultado: **corpus sólido** — cero
  IDs duplicados, cero categorías/edades fuera de lista, cero referencias rotas, cero
  coordenadas fuera de rango, ninguna categoría de bloqueo en edades de formación.
  De los 19 avisos iniciales del validador automático, 17 eran falsos positivos por
  dos patrones legítimos y recurrentes en el fichero que el validador (pensado para
  diagramas generados en caliente, no para ejercicios ya curados) no entendía:
  - **Sufijo "+1 recuperando"** (`ej_040`, `ej_042`, `ej_050`): el nombre cita el
    déficit inicial (p.ej. "2c1"), pero el diagrama capta el estado FINAL una vez
    llega el defensor de recuperación (2c2) — correcto tal cual está.
  - **Patrón "pasador/feeder sin defensor + pareja 1c1 real"** (`ej_003`, `ej_005`,
    `ej_007` fase 1, `ej_012`, `ej_033`, `ej_049`, `ej_054` fase 1): el "1c1"/"2c2"
    del nombre describe solo el duelo en vivo; el pasador que nunca ataca no lleva
    defensor asociado — correcto tal cual está.
  Se corrigieron los 2 hallazgos reales que sobrevivieron a esa criba, más 1 de
  completitud, todos verificados de nuevo tras el cambio:
  1. `ej_019` — el nombre decía "2c1" pero la descripción y el diagrama son 1 atacante
     contra 2 defensores. Renombrado a "SSG Finalización 1c2 con superioridad defensiva".
  2. `ej_007` — el propio texto describe "FASE 1 — sin defensa" y "FASE 2 — con
     defensa (D1 real)" pero solo existía diagrama de la Fase 1. Añadida la Fase 2
     (mismo trayecto, con D1 real en vez de cono, `curva: true` al rodearlo) siguiendo
     el patrón ya usado en `ej_004`/`ej_054`.
  3. `ej_063` — `puntos_clave` vacío. Añadidos 3 puntos basados en su propia
     descripción (nada inventado).
**Hecho (2026-08-29, sesión 3) — diagramas de ej_060/061/062 + bug real en el renderer + prueba en vivo:**

- **Bug real encontrado y arreglado**: el movimiento `tiro` en `diagram_renderer.py`
  apuntaba siempre a la coordenada fija `(50,11)` (canasta cercana), sin importar si
  el diagrama era `pista_completa` y el jugador atacaba la canasta lejana. Cualquier
  diagrama a pista completa con un tiro en la mitad lejana habría salido con la
  flecha apuntando al lado equivocado. Arreglado: si `tipo == "pista_completa"` y el
  jugador está en la mitad `y > 50`, el tiro apunta a `(50,89)` (espejo de la canasta
  cercana). Verificado numéricamente (coordenadas de píxel en ambos sentidos) — no
  hay herramienta de renderizado visual en este entorno, así que falta una
  comprobación visual real la próxima vez que se abra la app.
- **Diagramas construidos para `ej_060`, `ej_061`, `ej_062`** (antes sin tocar,
  requerían inventar coordenadas que el texto no fija explícitamente — Nacho pidió
  interpretarlas en vez de preguntar, dado que el texto describe la disposición con
  suficiente detalle):
  - `ej_060` (pista completa, 2 fases): Fase 1 — dos filas corren a conos grandes y
    tiran a su propia canasta; Fase 2 — 1c1 en la canasta contraria.
  - `ej_061` (media pista): pasadores en línea de tiro libre a cada banda (`x=0` y
    `x=100`, borde de la pista — el esquema no admite coordenadas fuera de 0-100, así
    que quedan pegados a la línea en vez de literalmente fuera), doble reinicio con
    pasador distinto, ataque final.
  - `ej_062`: zona marcada con 4 conos, 2 atacantes + 1 defensor, pases dentro de la
    zona (sin tiro — el ejercicio es de posesión/rotación, no de finalización).
  Verificados con `_validar_diagrama` (los mismos falsos positivos ya conocidos por
  "carrera sin oposición"/"pasador sin defensor", nada nuevo) y con el chequeo de
  rango/referencias — estructura limpia en los tres. **`carga_cognitiva` de `ej_060`
  y `ej_061` sigue sin tocar** (sigue pareciendo baja, es criterio de entrenador).
- **Prueba en vivo end-to-end**: sesión real generada (`U12`, 75 min, objetivo
  "1c1") con el código y las colecciones ya arregladas. Resultado: 3 ejercicios con
  variantes N.1/N.2, 6 de 8 diagramas posibles generados con contenido real; los 2
  que no se generaron fallaron la validación semántica dos veces seguidas (referencia
  a jugador no declarado) y devolvieron `None` limpio — exactamente el
  comportamiento diseñado, confirmado con logs reales: el validador atrapó
  problemas reales en 5 de 5 intentos de auto-generación, se recuperó en 3 con el
  reintento y falló seguro (sin diagrama) en 2. Sin errores en logs de la API.
  **Backup `data/chroma_db.bak_20260829/` borrado tras esta confirmación.**

**Hecho (2026-08-29, sesión 4) — bug real de truncado de sesión, encontrado por Nacho
usando la app de verdad (exportó una sesión a PDF y algo no cuadraba):**

- **Síntoma**: sesión Benjamín/U10, 75 min, "Tiro tras bote" exportada a PDF — el PDF
  solo tenía 4 páginas, cortado a mitad del Ejercicio 2.1 (ni siquiera tenía
  `Puntos clave`), sin Ejercicio 2.2/3, sin descanso, sin vuelta a la calma ni
  fundamentos.
- **Causa raíz**: `generar_sesion` tenía `num_predict` fijo en 2500 sin importar
  cuánto contenido pide realmente la plantilla. Para categorías de formación
  (U8/U10/U12, `MAX_BLOQUE_POR_EDAD=10`) con duraciones largas, los 3 ejercicios se
  parten en variantes N.1/N.2 (6 bloques en vez de 3) — mucho más texto que rellenar
  con el mismo presupuesto. Confirmado con Ollama: `done_reason="length"`,
  `eval_count=2500` — agotaba el tope exacto.
- **Primer arreglo** (commit `39b721a`): `num_predict`/`num_ctx` escalan si se
  detecta que los ejercicios se van a partir (`bloques_partidos`).
- **Seguía sin ser suficiente**: probando un caso que NO debería partirse (Cadete/U16,
  90 min, "defensa", 3 bloques) también se cortó, con el presupuesto "normal" que
  hasta entonces parecía sobrado. La verbosidad del modelo varía de una generación a
  otra (temperature=0.4) — ningún número fijo es garantía real.
- **Arreglo bueno** (commit `75530a9`): `generar_sesion` ahora lee `done_reason` de
  la respuesta de Ollama. Si es `"length"` (truncado real), reintenta una vez con
  +2500 `num_predict` / +3000 `num_ctx` antes de devolver el texto — mismo patrón
  que el retry de validación semántica de los diagramas: reaccionar al fallo real,
  no adivinar un número de antemano. Presupuestos base también subidos como margen
  preventivo (2500→3200 sin partir, 4500→5000 partido).
- **Verificado en vivo 4 veces** (2 casos, uno repetido dos veces): todas las
  sesiones completas, con vuelta a la calma y fundamentos, terminando en frase
  completa. Sin más incidencias de truncado en las pruebas.
- **Lección para el futuro**: los bugs más interesantes de esta sesión (este y el
  de la Fase 2 de `ej_007`) los encontró Nacho usando la app de verdad, no ninguna
  prueba automatizada — seguir generando sesiones reales de vez en cuando, no solo
  confiar en los tests dirigidos.

**Pendiente — próximos pasos, en este orden:**

1. **Revisión visual real** de los diagramas de `ej_060`/`ej_061`/`ej_062` y del
   arreglo del tiro a pista completa la próxima vez que se abra la app — solo se
   verificó numéricamente, no se ha visto renderizado de verdad.
2. **Probar `qwen3.5:4b` — en local primero** (Nacho: "de momento no [servidor], de
   momento probamos ese modelo en local", 2026-08-29). Q4_K_M, 3,4 GB, cabe también
   en la GTX 1060 6GB del servidor si más adelante se decide llevarlo allí, pero esa
   decisión es aparte y no urgente. Salió el 2026-03-02, después de elegir esta
   pila. Mejora generacional limpia sobre `qwen3:4b-instruct`: 256K contexto (vs
   32K), tools, visión. Pasos:
   1. `docker exec mipizarra-ollama ollama pull qwen3.5:4b`
   2. Cambiar `OLLAMA_MODEL`/`OLLAMA_MODEL_SESION` a `qwen3.5:4b` (`.env` local o
      `docker-compose.yml`) y reiniciar la API.
   3. Verificar que el thinking (activo por defecto en 3.5) se desactiva de forma
      fiable con `chat_template_kwargs: {"enable_thinking": false}` — mecanismo
      distinto del `"think": false` de Ollama que ya falló con qwen3:4b. Si Ollama no
      expone ese parámetro directamente, puede hacer falta ajustar cómo se llama al
      modelo desde `rag_engine.py`.
   4. Generar varias sesiones/diagramas/reglamento reales y comparar calidad contra
      `qwen3:4b-instruct` antes de cambiar el default — no cambiar solo porque "es
      más nuevo".
   5. Solo si se decide adoptarlo: entonces sí, probar que carga bien en la GTX 1060
      del servidor (Pascal/sm_61, arquitectura MoE dispersa + Gated Delta Networks —
      no hay garantía de que Pascal la soporte) antes de plantear llevarlo allí.
3. **Solo si tras el paso 2 aún falta calidad**: comparar A/B contra `qwen3.5:9b`
   (6,6 GB — no cabe en el servidor, solo PC) para saber si el techo del hardware
   aporta algo o ya se está en meseta. Si se necesita el 9B, el servidor queda
   descartado por tamaño para esta IA y la decisión de dónde vive el día a día se
   resuelve sola.
4. **Plantillas de diagrama para calentamiento/vuelta a la calma.** Muchos juegos de
   calentamiento (rondos, pilla-pilla) no tienen un diagrama de media pista con
   sentido — forzar generación libre garantiza basura. Mejor: ~10-15 plantillas
   parametrizadas (filas en esquinas, circuito de conos, rondo circular, cuatro
   esquinas...) con el schema restringiendo la elección a un enum.
5. **Esquema de diagrama con posiciones canónicas nombradas** (enum sobre las ~16 de
   `docs/coordenadas.md`: codo TL, poste bajo, esquina triple...) en vez de
   coordenadas `x,y` libres. Necesario para el paso 4 y también habilita:
6. **Probar conversor de dibujos a mano (tablet + app Notein) → JSON** con
   `qwen3.5` (multimodal en 4b y 9b, 89,2% OCRBench). No es proyecto aparte: es
   "input no estructurado → JSON de diagrama", el mismo problema de la generación
   automática de diagramas, con input distinto. Decidir con datos, no en abstracto:
   probar 5 dibujos reales: si cada borrador necesita <30s de corrección, compensa
   el VLM; si no, transcripción manual (a mano son 3-5h para el volumen actual de
   esta temporada, asumible).
7. **Aparcado — jugadas de pizarra por filtros.** `data/pdfs/coleccion_jugadas/`
   sigue vacía (0 bytes): sin corpus, generar tácticas de ataque estático es el peor
   caso de alucinación de todos los pendientes. Cuando haya material, empezar por un
   catálogo `jugadas.json` filtrable a mano (mismo schema de diagrama, multifase,
   `render_all_diagrams()` ya lo soporta) — datos primero, generación después o nunca.

**Decisión de despliegue — recomendación dada y aceptada (2026-08-29):** PC bajo
demanda, no servidor siempre encendido ni esperar mejora de hardware. Generar una
sesión es planificación puntual (2-3 veces/semana, un usuario), no justifica un
servicio 24/7; y la GTX 1060 es Pascal, invertir ahí es apostar por una arquitectura
que las librerías de inferencia están dejando atrás. No bloqueante: con `qwen3.5:4b`
el servidor sigue siendo viable si se prefiere más adelante.

## Estado actual (2026-05-30)

### Lo que está hecho y listo

**Código:**
- `api/main.py` — 3 endpoints: `/generar` (sesión), `/ejercicio` (ejercicio único), `/reglamento` (dudas)
- `api/rag_engine.py` — lógica RAG + las 3 funciones de generación
- `api/diagram_renderer.py` — renderer SVG mejorado (bote ondulado, bloqueo con barra perpendicular, curva bezier, semicírculo medio campo correcto, tacos simétricos)
- `tools/generar_dataset.py` — genera 4 tipos de ejemplos: sesion, diagrama, ejercicio, reglamento (48+ preguntas de reglamento/técnica incluidas)
- Tres SYSTEM prompts diferenciados implementados en los 3 ficheros que los necesitan

**Conocimiento (data/teoria/ — 20 documentos):**
- fundamentos_ofensivos.md, fundamentos_defensivos.md, bloqueos.md, transicion_y_contraataque.md
- tiro_a_canasta_tecnica_completa.md, tiro_tecnica_requisitos_y_ejercicios.md
- bote_finalizaciones_cambios_mano.md (paso cero en 2 contextos, cambios de mano progresión, finalizaciones, pase picado)
- contenidos_por_edad_lineas_rojas.md, contenidos_tecnicos_por_categoria.md
- metodologia_entrenamiento_formacion.md, filosofia_competicion_formacion.md
- sistemas_defensivos.md, espaciado_preminibasket.md
- minibasquet_skills_y_decisiones.md, habilidades_motrices_baloncesto.md
- reglamento_fiba_normas_clave.md, reglamento_competicion_formacion_espana.md
- jugadas_tacticas_doble_bloqueo.md, toma_decisiones_drills.md
- ejercicios_propios_coleccion.md (365 ejercicios propios)

**exercises.json:** 58 ejercicios con puntos_clave, descripción y diagrama
- ej_001–ej_025: ejercicios generales (reescritos como drills reales con movimiento, rotación y elemento competitivo)
- ej_026–ej_050: ejercicios del trabajo Cadete de Nacho (contraataque, transición ofensiva/defensiva, ataque posicional, rebote, defensa)
- ej_051–ej_058: extraídos de isportcoach.com (Castillos, Tiro con presión, Winchester, 3/4 pista, 2c2 hándicap, Palomero, Circus, Shell Drill)

**Herramientas de edición de ejercicios:**
- `exercises_editable.txt` — versión legible de exercises.json para editar manualmente DESCRIPCION y PUNTOS_CLAVE; incluye sección de EJERCICIOS NUEVOS al final
- `tools/exportar_editable.py` — regenera el .txt desde exercises.json
- `tools/importar_editable.py` — sincroniza los cambios del .txt de vuelta a exercises.json
- `tools/importar_isportcoach.py` — sustituto del scraper; ejercicios de isportcoach ya importados

**Terminología corregida en todo el proyecto:** "portador" → "jugador con balón" en exercises.json y en los 9 documentos .md de data/teoria/

**PDFs organizados en 4 subcarpetas** en `data/pdfs/` (ya indexables)

**Configuración ya optimizada para la 1060 6GB y aplicada en el repo:**
- num_ctx alineado a 4096/6144 según uso · fp16 activo · bitsandbytes==0.42.0 (Pascal-safe)
- LoRA rank 8 (alpha 16, dropout 0.05) · grad_acc 8 · paged_adamw_8bit · filtrado por longitud
- Wrapper `tools/finetune.sh` que libera Ollama durante el training
- 28 patrones únicos de diagrama, 15 descripciones únicas, `random.sample` sin reemplazo
- `--steps` default 100 (recalibrado para datasets pequeños)
- Script de evaluación base vs fine-tuned: [tools/evaluar_modelo.py](tools/evaluar_modelo.py)

**Bugs críticos corregidos (revisión Opus 4.8, 2026-05-30):**
- ✅ `"think": False` añadido en TODAS las llamadas Ollama (rag_engine.py ×5, generar_dataset.py ×1) — era bloqueante para JSON con Qwen3
- ✅ `generar_diagrama_desde_texto` reescrito: eliminado formato Mistral `[INST]`, usa `/api/chat` + `SYSTEM_DIAGRAMA`
- ✅ System prompts unificados en `api/prompts.py` (fuente única para inferencia y training)
- ✅ `OLLAMA_MODEL` default corregido: `hoops-mistral` → `qwen3:4b`
- ✅ SYSTEM_EJERCICIO actualizado: incluye ahora el formato `diagramas` multifase con `titulo`

**Pendiente — próxima sesión (en este orden):**

1. ~~**Añadir ejercicios del trabajo Cadete a `exercises.json`** — hecho (ej_026–ej_050, 25 ejercicios nuevos).~~

2. **[PRIORIDAD 1 — hacer antes de cualquier entrenamiento] Probar RAG puro con modelo base:**
   ```bash
   curl -X POST http://192.168.1.72:8000/generar \
     -H "Content-Type: application/json" \
     -d '{"edad": "U16", "duracion": 90, "objetivo": "contraataque"}'
   ```
   Si la calidad ya vale → no hay que fine-tunear. Si no → proceder con los pasos siguientes.

3. **Indexar data/teoria/ en ChromaDB** (en el servidor):
   ```bash
   docker exec -it mipizarra-api python /app/tools/indexar_pdfs.py
   ```

3. **Generar dataset** (desde local apuntando al servidor):
   ```bash
   python tools/generar_dataset.py --ollama http://192.168.1.72:11434 --todo
   ```
   Genera: sesiones (60), diagramas (20), ejercicios JSON (15), reglamento/técnica (40) + fuentes adicionales.

4. **Revisar `data/dataset/para_revisar.jsonl`** — borrar ejemplos malos de `train.jsonl`.

5. **Entrenar en local** (RTX 5060 Ti, recomendado):
   ```bash
   python tools/finetune_qwen.py --no-quantize --rank 8 --steps 40
   ```
   ⚠ 150 pasos con ~135 ejemplos son ~9-18 épocas → sobreentrenamiento casi seguro.
   Usar 30-50 pasos máximo (1-2 épocas). Añadir split de validación y early stopping.
   Rank 8 es correcto para < 500 ejemplos.

6. **Pull en el servidor** (si no están descargados):
   ```bash
   docker exec -it mipizarra-ollama ollama pull qwen2.5:7b-instruct-q4_K_M
   docker exec -it mipizarra-ollama ollama pull qwen3:4b
   docker exec -it mipizarra-ollama ollama pull nomic-embed-text
   ```
4. **Rebuild imagen finetune** (si vas a entrenar en el servidor con QLoRA):
   ```bash
   docker compose build finetune
   ```
5. (Recomendado) **Probar el RAG con el modelo base sin fine-tuning** vía `curl` al endpoint
   `/generar`. Si la calidad ya vale, no entrenar.

## Flujo completo cuando todo esté listo

### Opción A — todo en el servidor (GTX 1060, QLoRA 4-bit)

```bash
docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo   # ~15-25 min
# revisar data/dataset/para_revisar.jsonl y borrar ejemplos malos de train.jsonl
./tools/finetune.sh                                                          # ~12-22 min
docker compose run --rm finetune python tools/exportar_a_ollama.py \
  --lora outputs/mipizarra-v1/lora_adapters --nombre mipizarra              # ~15-20 min
docker exec -it mipizarra-api python /app/tools/evaluar_modelo.py \
  --base qwen3:4b --finetuned mipizarra --n 15                              # ~10 min
```

### Opción B — entrenar en local (RTX 5060 Ti 16 GB, LoRA puro bf16, recomendado)

```bash
# 1. Dataset: en el servidor o en local apuntando al Ollama del servidor
docker exec -it mipizarra-api python /app/tools/generar_dataset.py --todo
scp usuario@<SERVER_IP>:~/docker/mipizarra/data/dataset/train.jsonl data/dataset/

# 2. Entrenar en local (conda activate mipizarra, desde carpeta mipizarra/)
python tools/finetune_qwen.py --no-quantize            # ~3-5 min por 100 pasos
# Con más capacidad (16 GB lo permite):
python tools/finetune_qwen.py --no-quantize --rank 16 --steps 150

# 3. Copiar lora_adapters al servidor y exportar allí
scp -r outputs/mipizarra-v1/lora_adapters usuario@<SERVER_IP>:~/docker/mipizarra/outputs/mipizarra-v1/
# En el servidor:
docker compose run --rm finetune python tools/exportar_a_ollama.py \
  --lora outputs/mipizarra-v1/lora_adapters --nombre mipizarra
```

Ver setup del entorno Python local en `ENTRENAMIENTO_MODELO.md → Entrenamiento local`.

Regla: si `evaluar_modelo.py` reporta "⚠ no mejora claramente", **no** activar
`OLLAMA_MODEL=mipizarra`. Iterar sobre el dataset, no sobre `--steps`.

## Decisiones ya tomadas (no re-debatir)

- **Modelo base**: Qwen3-4B (equivale a Qwen2.5-7B en calidad; Q4_K_M ~2.5 GB en la GTX 1060).
- **LoRA rank 8** mientras dataset < 500 ejemplos.
- **Modelo profesor 7B** en lugar de Llama3.2-3B (mejor destilación).
- **Diagramas = JSON → SVG**, no imágenes generativas. El modelo solo aprende coordenadas;
  el renderer (`api/diagram_renderer.py`) ya pinta pista FIBA + minibasket bien.
- **Conflicto GPU**: Ollama y el contenedor `finetune` no pueden tener un modelo cargado a
  la vez. El wrapper `tools/finetune.sh` lo gestiona automáticamente.
- **Entrenamiento local**: RTX 5060 Ti 16 GB, Unsloth + `--no-quantize` (LoRA bf16).
  PyTorch ≥2.6 + CUDA 12.6. ~4× más rápido que el servidor con QLoRA.
  Los `lora_adapters/` se copian al servidor para la exportación GGUF.
- **Unsloth**: framework de fine-tuning 2× más rápido que TRL en GPU local.
  `pip install unsloth`. El script lo detecta automáticamente y lo usa si está disponible.

## Riesgos vivos

- Qwen2.5:7B Q4_K_M ocupa ~4.7 GB; con num_ctx alto puede paginar a CPU. Si `generar_dataset.py`
  va lentísimo, bajar `num_ctx` a 2048 en `llamar_ollama()`.
- Sin PDFs reales en `data/pdfs/`, el dataset es 100% sintético del 7B → calidad limitada.
  Si las sesiones generadas se parecen demasiado entre sí, el problema está en la diversidad
  de la lista de objetivos/edades/duraciones, no en los `--steps`.

## Documentos clave en este orden

1. Este archivo
2. [ENTRENAMIENTO_MODELO.md](ENTRENAMIENTO_MODELO.md) — flujo paso a paso
3. [docs/coordenadas.md](docs/coordenadas.md) — sistema de coordenadas
4. [docs/esquema-ejercicios.md](docs/esquema-ejercicios.md) — schema de `exercises.json`
