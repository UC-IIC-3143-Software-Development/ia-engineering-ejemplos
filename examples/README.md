# Ejemplos por técnica

Cada script es autónomo (`python3 NN_nombre.py`), < 80 líneas, y explica en su docstring
qué técnica muestra y qué observar. Todos usan `llm.py` (`ask` / `ask_json`).

## Cómo correr

| Backend | Requisito | Cómo se activa |
|---------|-----------|----------------|
| Gemini  | `pip install google-genai` + `GEMINI_API_KEY` (exportada o en `.env` en la raíz del repo) | automático si hay `GEMINI_API_KEY` |
| SDK     | `pip install anthropic` + `ANTHROPIC_API_KEY` | automático si no hay Gemini y ambos existen |
| CLI     | `claude` (Claude Code) autenticado | automático si no hay API key; forzar con `LLM_BACKEND=cli` |
| fake    | nada | `LLM_BACKEND=fake python3 01_estocastico.py` (solo demuestra el flujo) |

Credenciales: `cp .env.example .env` en la raíz del repo y completa `GEMINI_API_KEY=...`
(la plantilla documenta también `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` y `LLM_BACKEND`).
`.env` está en `.gitignore` y no se commitea.

Modelo por defecto: `gemini-3.8-flash` con Gemini, `claude-opus-5` con Claude (cambiar con
`model=` en `ask`/`ask_json`).

## Técnica → script → qué muestra

| # | Técnica | Script | Qué observar |
|---|---------|--------|--------------|
| 1 | LLMs estocásticos | `01_estocastico.py` | 5 corridas libres vs 5 restringidas a un enum: la restricción "desplaza la masa de probabilidad" |
| 2 | Directo vs few-shot | `02_directo_vs_fewshot.py` | los ejemplos fijan estructura, tono y largo |
| 3 | CoT + self-consistency | `03_cot_self_consistency.py` | "piensa paso a paso" y votación por mayoría de 5 corridas |
| 4 | Alucinación | `04_alucinacion.py` | sin instrucción el modelo rellena o se abstiene en prosa libre; con "di exactamente 'no está en el contexto'" responde ese string fijo |
| 5 | Prompt injection | `05_prompt_injection.py` | defensa por niveles: regex → delimitadores XML → clasificador LLM |
| 6 | Sicofancia | `06_sicofancia.py` | pushback del usuario; system prompt que prioriza exactitud + confianza 0-100 |
| 7 | Salidas estructuradas | `07_salidas_estructuradas.py` | enum (`Literal`) para clasificar, Pydantic plano para extraer |
| 8 | Prompt como código | `08_prompt_como_codigo.py` | registry versionado + mini eval v1 vs v2 |
| 9 | Agente OTA | `09_agente_ota.py` | loop Observar-Pensar-Actuar hasta que pasan los tests (max 5) |
| 10 | ReAct + Plan-and-Execute | `10_react_plan_execute.py` | planner JSON, executor Thought/Action/Observation, replanner |
| 11 | Reflexion | `11_reflexion.py` | merge_intervals con 2 requisitos ocultos; reflexión verbal reinyectada (max 3) |
| 12 | Ralph loop | `ralph/ralph.sh` | `while :; do cat spec.md \| claude -p; grep COMPLETE && break; done` |
