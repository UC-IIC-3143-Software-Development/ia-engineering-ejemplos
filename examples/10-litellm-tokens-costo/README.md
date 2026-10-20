# LiteLLM: tokens y costo de un prompt

Ejecuta **el mismo prompt** con varios modelos a través de **LiteLLM** y muestra por pantalla cuántos
tokens usó cada ejecución y cuánto costó, más la proyección a 1.000 y 1.000.000 de ejecuciones.

## El concepto

LiteLLM es una interfaz única para cualquier proveedor: `litellm.completion(model="proveedor/modelo",
messages=[...])` funciona igual con Gemini, OpenAI o Anthropic. Además:

- **Normaliza el uso de tokens** (`response.usage`) al formato OpenAI: `prompt_tokens`,
  `completion_tokens` y `completion_tokens_details.reasoning_tokens`.
- **Calcula el costo** con `litellm.completion_cost(response)`, usando su tabla de precios
  `litellm.model_cost`:
  `costo = tokens_entrada × precio_entrada + tokens_salida × precio_salida`.
- **Estandariza los errores** de todos los proveedores como excepciones de OpenAI
  (`NotFoundError`, `RateLimitError`, ...). Por eso el código atrapa `openai.APIError`.

El punto clave: **los tokens de razonamiento se cobran como salida**. Un modelo que "piensa" puede
generar 20 veces más tokens que la respuesta visible.

## Qué hace el prototipo

1. Muestra el prompt y la tabla de precios por millón de tokens que usa LiteLLM.
2. Ejecuta el prompt (clasificar un ticket de e-commerce y redactar una respuesta de 2 frases) en 5
   escenarios: Gemini 3.5 Flash-Lite, 2.5 Flash con razonamiento por defecto, 2.5 Flash con
   razonamiento apagado (`reasoning_effort="disable"`), 3.8 Flash y 3.1 Pro (preview).
3. Tabla: tokens de entrada, tokens de salida, cuántos de ellos son de razonamiento, latencia, costo
   por ejecución, por 1.000 y por 1 millón. Si un modelo falla, lo omite y sigue.
4. Veredicto calculado: cuántas veces más caro es el escenario más caro que el más barato.

Agregar otro proveedor es una fila más en `ESCENARIOS`, p.ej.
`("Claude", "anthropic/claude-sonnet-5", {})` con `ANTHROPIC_API_KEY` definida.

## Setup

```bash
pip install -r requirements.txt
# GEMINI_API_KEY en <repo>/.env (lo carga python-dotenv) o exportada:
export GEMINI_API_KEY=tu_key
```

## Cómo correr

```bash
python3 main.py
python3 main.py --prompt "Resume en una frase qué es PgBouncer"
```

Tarda ~30 s y cuesta unos 2 centavos de dólar. La corrida grabada está en `output-1.md`.

## Qué observar (en `output-1.md`)

- Los 5 escenarios usan los mismos **79 tokens de entrada**. Lo que cambia es la **salida**: de 73
  tokens (2.5 Flash sin razonamiento) a **1.945 tokens (2.5 Flash con razonamiento, 96 % de
  razonamiento)** para una respuesta visible de ~70 tokens.
- Mismo modelo, distinto costo: 2.5 Flash con razonamiento cuesta $0,004886 por ejecución y sin
  razonamiento $0,000206, **~24× menos** y 10× más rápido (1,1 s contra 10,8 s).
- El más caro (3.1 Pro) cuesta **59×** más que el más barato. A 1 millón de ejecuciones son
  ~$12.218 contra ~$206: la elección del modelo es una decisión de diseño con costo medible.
- Para una tarea simple como clasificar y responder en 2 frases, el razonamiento casi no agrega
  calidad y multiplica el costo. Primero se mide y después se decide qué modelo usar.

## Métricas

- **Tokens de entrada / salida / razonamiento:** `response.usage` normalizado por LiteLLM.
- **Costo por ejecución:** `litellm.completion_cost` (USD, tabla `litellm.model_cost`).
- **Proyección:** costo × 1.000 y × 1.000.000 ejecuciones.
