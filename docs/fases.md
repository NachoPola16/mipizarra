# Plan de fases

## Fase 0 — Infraestructura ✅ (en curso)
- [x] Repositorio GitHub
- [x] docker-compose con Ollama
- [ ] Verificar GPU en contenedor
- [ ] Primer `ollama run` funcionando

## Fase 1 — RAG básico
- [ ] Biblioteca con 20+ ejercicios en exercises.json
- [ ] rag_engine.py filtra por edad y objetivos
- [ ] API endpoint `/generar` devuelve texto de sesión

## Fase 2 — Diagramas SVG
- [ ] diagram_renderer.py genera SVG desde bloque diagrama
- [ ] Al menos 10 ejercicios con diagrama completo
- [ ] API devuelve SVGs junto con el texto

## Fase 3 — Frontend Streamlit
- [ ] Formulario: categoría, edad, duración, objetivo
- [ ] Muestra sesión + diagramas inline
- [ ] Exportar a PDF (básico)

## Fase 4 — Fine-tuning
- [ ] Recopilar 50+ sesiones reales (formato JSON)
- [ ] Script de preparación de dataset QLoRA
- [ ] Fine-tune de llama3.2:3b con mis sesiones
- [ ] Evaluar diferencia de calidad vs. modelo base

## Fase 5 — Mejoras
- [ ] Parser NLP para entender lenguaje natural
- [ ] Variantes de ejercicios sugeridas por la IA
- [ ] Integración con Flame (enlace en dashboard)
- [ ] App móvil mínima (PWA con Streamlit)
