# LiteLLM en producción: reintentos, rate limit, cooldown y fallback

Cómo se usa **LiteLLM** en un servicio real: no con una llamada suelta, sino con un `Router` que
reintenta los errores transitorios, respeta una cuota propia de requests por minuto, saca de rotación
un modelo que falla y deriva a un respaldo. La salida es **repetible**: por defecto reproduce
respuestas grabadas, así que cada corrida imprime exactamente lo mismo, sin API key y sin costo.

Ejemplos relacionados: `10-litellm-tokens-costo` (tokens y costo por modelo) y `10-router-litellm`
(estrategias de ruteo).

## El concepto

### La llamada

LiteLLM es **una sola función para cualquier proveedor**: el proveedor va como prefijo del modelo, los
mensajes usan el formato de OpenAI y la respuesta vuelve en formato OpenAI, venga de donde venga.

```python
import litellm
from dotenv import load_dotenv

load_dotenv()  # LiteLLM lee GEMINI_API_KEY del entorno; esto la carga desde .env

resp = litellm.completion(
    model="gemini/gemini-3.5-flash-lite",          # "proveedor/modelo"
    messages=[{"role": "user", "content": "Me cobraron el envío dos veces..."}],
)
resp.choices[0].message.content    # el texto
resp.usage.prompt_tokens           # tokens de entrada
resp.usage.completion_tokens       # tokens de salida (incluye los de razonamiento)
litellm.completion_cost(resp)      # costo en USD, según la tabla de precios de LiteLLM
```

Cambiar de proveedor es cambiar el string (`openai/gpt-5-mini`, `anthropic/claude-haiku-4-5`) y tener
su key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). Los errores de cualquier proveedor heredan de las
excepciones de OpenAI (`RateLimitError`, `AuthenticationError`, ...), así que basta un
`except openai.APIError`. La subclase exacta puede variar: sin API key, Gemini lanza
`APIConnectionError`.

### En producción: el Router

Una llamada suelta no sobrevive a producción: el proveedor responde 429 cuando se supera su cuota,
a veces falla con 5xx o no responde, y un modelo puede caerse por minutos. `litellm.Router` resuelve
eso con configuración, y el código que llama no cambia: `router.acompletion(model="soporte", ...)`
nombra un **grupo**, no un modelo, y el Router decide a qué **deployment** (modelo + key) mandarlo.

```python
router = Router(
    model_list=[
        {"model_name": "soporte", "model_info": {"id": "flash-lite"},
         "litellm_params": {"model": "gemini/gemini-3.5-flash-lite",
                            "api_key": "os.environ/GEMINI_API_KEY", "rpm": 2}},
        {"model_name": "respaldo", "model_info": {"id": "flash"},
         "litellm_params": {"model": "gemini/gemini-3.8-flash",
                            "api_key": "os.environ/GEMINI_API_KEY"}},
    ],
    fallbacks=[{"soporte": ["respaldo"]}],
    num_retries=1,
    allowed_fails=1,
    cooldown_time=60,
    timeout=30,
    optional_pre_call_checks=["enforce_model_rate_limits"],
)
```

| Parámetro | Qué hace |
|-----------|----------|
| `num_retries=1` | Reintenta 429, 5xx, timeouts y errores de conexión con **backoff exponencial**: 0,5 s · 2ⁿ (tope 8 s) más un *jitter* aleatorio de 0 a 0,75 s. Si el proveedor manda `Retry-After` (hasta 60 s), espera eso. No reintenta 400 ni 404: repetir un request inválido no lo arregla. Tampoco el 429 de la cuota propia (fila siguiente). Si no lo defines, son 2. |
| `rpm` + `optional_pre_call_checks=["enforce_model_rate_limits"]` | **Cuota propia**: máximo 2 requests por minuto a ese deployment. El request que sobra ni siquiera sale al proveedor: el Router lo rechaza con un 429 propio y, sin reintentar, lo manda al fallback. Sin el check, `rpm` no se hace cumplir por minuto (queda como peso para repartir carga y, en async, como tope de requests simultáneos). |
| `allowed_fails=1`, `cooldown_time=60` | **Circuit breaker**: con más de 1 falla (429, 401, 404, timeout o 5xx), cada una a menos de 60 s de la anterior, el deployment sale de rotación 60 s y los requests van directo al respaldo, sin esperar a que falle de nuevo. Un 400 o un error de conexión (`APIConnectionError`) no cuentan. |
| `fallbacks` | Si el grupo `soporte` falla o no puede atender, responde `respaldo`. Un fallback no cuenta como reintento. |
| `timeout=30` | Segundos por intento. El default del Router es 6000 (un `litellm.completion` suelto usa 600): sin esto, un proveedor colgado bloquea al cliente 100 minutos por intento. |
| `"api_key": "os.environ/GEMINI_API_KEY"` | El secreto sale del entorno al crear el Router; nunca va en el código. |
| `model_info.id` | Nombre fijo del deployment en la traza y en la grabación (si no, LiteLLM usa un hash de los parámetros). |

Cada respuesta dice qué pasó: `resp._hidden_params["additional_headers"]` trae
`x-litellm-attempted-retries`, `x-litellm-attempted-fallbacks` y `x-litellm-model-group`, y
`resp._hidden_params["response_cost"]` el costo. Si le pasas `metadata={}`, el Router anota ahí
los intentos fallidos en `soporte` (`previous_models`, con el deployment y la excepción). Eso es lo
que imprime el prototipo. Ojo cuando a un reintento le sigue un fallback (no pasa en estos 5
tickets): `x-litellm-attempted-retries` cuenta solo los reintentos del grupo que respondió, la
última falla de `soporte` aparece dos veces y las fallas dentro de `respaldo` no quedan anotadas.

### ¿Cómo se hace repetible?

Un LLM puede responder distinto cada vez con el mismo prompt (ver `01-estocastico`), y un 429 real
no se puede pedir a voluntad. Para que la demo sea repetible:

- **Respuestas grabadas.** Cada corrida en vivo guarda la última respuesta real de cada deployment
  (`resp.model_dump()`) en `grabacion.json`. Las siguientes la ponen en `mock_response` del
  deployment, y LiteLLM la devuelve sin llamar a la API: mismo texto, mismos tokens, mismo costo.
  Solo se reproduce si `MENSAJES` y los modelos coinciden con los grabados; si cambiaste el prompt,
  el script pide regrabar con `--en-vivo`.
- **El 429 lo simula LiteLLM** con `mock_testing_rate_limit_error=True` en el ticket 1, en los dos
  modos. Por eso la traza lo muestra en `soporte/router`: el Router lo lanza antes de elegir
  deployment.
- **Precios fijos**: `LITELLM_LOCAL_MODEL_COST_MAP=True` antes de `import litellm` usa la tabla de
  precios que trae la versión instalada. Sin eso, cada import la descarga de GitHub.

La cuota y el cooldown no se simulan: son reales, del Router, en los dos modos.

## Qué hace el prototipo

Llegan 5 tickets iguales, en orden, al grupo `soporte`:

1. **429 simulado del proveedor**: el Router espera el backoff y reintenta; responde flash-lite.
2. **Llamada normal**: responde flash-lite (2 de 2 de la cuota: el 429 simulado no cuenta, el
   reintento del ticket 1 sí).
3. **Cuota agotada**: el 3er request del minuto supera `rpm=2`; el Router no llama a flash-lite y
   deriva al respaldo.
4. **Segundo rechazo**: otra vez sobre la cuota; con 2 fallas (`allowed_fails=1`) flash-lite entra
   en cooldown.
5. **Cooldown**: el Router ni lo intenta (`RouterRateLimitError`: no hay deployments disponibles en
   `soporte`) y va directo al respaldo.

Por ticket imprime los intentos fallidos (grupo/deployment, excepción y motivo) y quién respondió,
con reintentos, fallbacks, tokens (entrada/salida) y costo. Al final, un veredicto calculado.

Usa `router.acompletion` (async) a propósito: en LiteLLM 1.103, con `router.completion` (sync) un
request sobre la cuota **espera 60 s** y reintenta el mismo deployment en vez de ir al fallback.

## Setup

Python 3.10+ (litellm 1.103 no instala en 3.9, que es el `python3` de macOS).

```bash
pip install -r requirements.txt   # litellm fijado en 1.103.0: la grabación y los precios dependen de esa versión
```

Para correrlo **no hace falta API key**: `grabacion.json` viene en el repo. Solo `--en-vivo` necesita
`GEMINI_API_KEY`, en `<repo>/.env` o exportada:

```bash
export GEMINI_API_KEY=tu_key
```

## Cómo correr

```bash
python3 main.py             # repetible: reproduce grabacion.json (~2-3 s, $0)
python3 main.py --en-vivo   # llama a Gemini y regraba grabacion.json (~15 s, ~$0.006)
git checkout grabacion.json # vuelve a la grabación del repo (la de output-1.md)
```

Los ~2-3 s del modo repetible son reales: 1,3 s en importar LiteLLM y el backoff del ticket 1
(0,5 s más el jitter). La corrida grabada está en `output-1.md`.

## Qué observar

- **Ningún ticket falla para el cliente**, aunque hubo un 429, una cuota agotada y un deployment
  fuera de rotación: 5/5 respondidos, 1 reintento, 3 al respaldo.
- **Ticket 3 y 4: la cuota es tuya, no del proveedor.** El motivo dice
  `Model rate limit exceeded. RPM limit=2`: el request nunca salió a Gemini, y no se reintenta.
- **Ticket 5: el circuit breaker.** El Router ya ni intenta flash-lite:
  `RouterRateLimitError No deployments available ...`. El mensaje completo, que la terminal corta,
  sigue con `All deployments for selected model are in cooldown ... cooldown_list=['flash-lite']`.
  Aquí los rechazos por cuota ya eran instantáneos; el cooldown ahorra tiempo de verdad con 5xx o
  timeouts, donde cada intento fallido puede tardar hasta `timeout=30` s.
- **El respaldo cuesta más.** flash-lite respondió con 37 tokens ($0.000112) y flash con 516
  ($0.001984, ~18×) porque razona antes de responder. Las respuestas grabadas cuestan $0.006175 en
  vivo (cada corrida en vivo varía un poco: flash no razona igual cada vez); en modo repetible, $0.
  Un fallback mantiene el servicio, pero cambia la cuenta: hay que medirlo.
- **Misma salida en cada corrida.** Verificado: corridas seguidas sin API key, salida idéntica
  byte a byte y sin nada en stderr. En vivo el texto cambia, y ~1 de cada 10 corridas también el
  ruteo (ver la ventana de `rpm` abajo).

## Operarlo en producción (más allá del ejemplo)

- **Varias instancias.** Los contadores de `rpm` y los cooldowns viven en la memoria del proceso: con
  3 réplicas, cada una permite 2 rpm. Para compartirlos se pasa `redis_host`, `redis_port` y
  `redis_password` al Router (requiere `pip install redis`).
- **La ventana de `rpm` es el minuto calendario (UTC), no deslizante.** En el cambio de minuto pueden
  pasar hasta 2×rpm. Si una corrida cruza ese borde, flash-lite atiende uno o dos de los tickets 3-5
  (cuáles, depende de dónde caiga el borde) y los títulos de los tickets dejan de calzar con la traza.
  Pasa ~0,05 % de las veces en modo repetible y ~1 de cada 10 en vivo (los tickets 1-4 duran ~5 s).
- **Un Router por proceso**, creado al arrancar y no por request: el check de cuota se registra
  global en `litellm.callbacks` con el primer Router, y los que vengan después comparten su contador.
- **Concurrencia.** Aquí los tickets van en secuencia. Con `asyncio.gather`, en async `rpm` también
  limita los requests simultáneos, y los que sobran pueden quedar esperando 60 s.
- **Observabilidad.** Para mandar cada intento a logs o métricas se registra una subclase de
  `CustomLogger` en `litellm.callbacks` **antes** de crear el Router: asignar `litellm.callbacks`
  después desactiva en silencio la cuota (`enforce_model_rate_limits` vive en esa lista).
- **Gateway.** A escala se suele correr el **LiteLLM Proxy** (`pip install 'litellm[proxy]'`): la
  misma configuración en un servidor central con API compatible con OpenAI. Con una base PostgreSQL
  (`DATABASE_URL`) agrega keys por equipo, con límites y presupuesto por key; las métricas para
  Prometheus requieren además `prometheus-client`.
- **Presupuesto.** `litellm.max_budget` no hace nada con `completion` en 1.103; lleva la suma de
  `response_cost` en tu código o usa el Proxy.

## Trampas de LiteLLM 1.103 que este ejemplo evita

Verificadas con `pip install litellm==1.103.0` (sin extras):

| Trampa | Qué pasa | Aquí |
|--------|----------|------|
| `litellm.completion(..., num_retries=3)` | Necesita `tenacity`, que no se instala con litellm. Si algo falla, lanza un `Exception("tenacity import failed...")` que **reemplaza** al error real. | Reintentos del Router, que no la necesitan. |
| `rpm` sin `enforce_model_rate_limits` | No se hace cumplir por minuto: 5 de 5 requests seguidos pasan con `rpm=2` (queda como peso para repartir carga y, en async, como tope de requests simultáneos). | Check activado. |
| `router.completion` (sync) con cuota | Sobre la cuota, espera 60 s y reintenta el mismo deployment. | `acompletion`. |
| `allowed_fails=3` | Es el valor por defecto y se ignora: en un grupo de un solo deployment, los 429 solo lo sacan de rotación si fallan todos los requests del minuto y son al menos 1000. | `allowed_fails=1`. |
| `Router` sin `timeout` | 6000 s por intento (un `litellm.completion` suelto usa 600 s). | `timeout=30`. |
| `except openai.APIError` | No atrapa `RouterRateLimitError` (todo en cooldown), que es un `ValueError`. | Se atrapan los dos. |
| `import litellm` | Descarga la tabla de precios de GitHub en cada import. | `LITELLM_LOCAL_MODEL_COST_MAP=True`. |
| Cache de LiteLLM | Un acierto de cache importa módulos del proxy (`fastapi`, `orjson`) y falla sin `litellm[proxy]`. | Grabación propia con `mock_response`. |
