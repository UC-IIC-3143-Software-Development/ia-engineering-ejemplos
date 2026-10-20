# LLMs estocásticos: sentimiento libre vs restringido

Este prototipo muestra el punto de partida de toda la clase: **un LLM no es determinista**.
Con el mismo prompt, el mismo modelo y la misma temperatura, cada corrida puede devolver
algo distinto.

## El concepto

En un sistema en producción la varianza suele ser un bug: si el código que consume la
respuesta espera un formato o un conjunto de etiquetas, cualquier variación rompe el
pipeline. Por eso no se diseña para "la respuesta" sino para la **distribución de
respuestas**.

El experimento compara tres estrategias sobre la misma reseña mixta:

1. **A · libre:** se pide el sentimiento y las entidades sin decir cómo responder.
2. **B · JSON en el prompt:** además se *pide* un JSON con `sentimiento`
   (`positivo`, `negativo` o `neutro`) y `entidades`. Es solo una instrucción; nada la
   hace cumplir.
3. **C · `response_schema`:** el prompt de A más un esquema Pydantic con
   `sentimiento: Literal["positivo", "negativo", "neutro"]`. La API restringe la
   decodificación: los tokens que se salen del esquema tienen probabilidad cero.

### ¿Por qué pasa?

El modelo muestrea cada token de una distribución de probabilidad. Si el formato es
abierto, hay muchísimas formas válidas de decir lo mismo y cada corrida elige una
distinta. Restringir la salida achica ese espacio: B lo hace pidiéndolo (desplaza la masa
de probabilidad hacia el formato pedido) y C lo hace a la fuerza (elimina la masa fuera
del esquema). Restringir no elimina el azar; lo concentra en un conjunto pequeño de
respuestas comparables, y por eso **medibles**. `temperature=0` no es la solución:
también cambian los pesos, el batching y la versión del modelo.

## Qué hace el prototipo

- Envía la reseña 20 veces por estrategia (`temperature=0.7` fija en las tres, para que
  la única variable sea la restricción).
- Muestra la primera corrida completa (entrada y respuesta) y un punto verde/rojo con el
  tiempo de cada corrida restante.
- Guarda todas las respuestas en `corridas/` (un Markdown por estrategia; carpeta
  ignorada por git) para revisarlas después.
- Imprime una tabla comparativa y un veredicto calculado desde los datos.

## Setup

1. Python 3.10+.
2. Dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. API key de Gemini: una línea `GEMINI_API_KEY=...` en `<repo>/.env` (el script la
   carga con python-dotenv) o exportada en la terminal:
   ```bash
   export GEMINI_API_KEY='tu_api_key'
   ```

## Cómo correr

```bash
python3 main.py            # 20 corridas por estrategia (~3-4 min)
python3 main.py --runs 5   # versión corta para la clase (~1 min)
```

## Qué observar

La corrida grabada está en `output-1.md` (20 corridas por estrategia):

- **A · libre:** 20 respuestas distintas en 20 corridas (consistencia 5%). Cambian el
  encabezado, el largo, el formato Markdown y hasta el matiz del veredicto: "mixto",
  "mixto con inclinación positiva", "mixto/neutro"... Además la etiqueta natural del
  modelo es "mixto", que no existe en el conjunto que el programa espera. El sentimiento
  queda **no medible** sin otro paso que interprete el texto.
- **B · JSON en el prompt:** 2 respuestas distintas (consistencia 85%) y `positivo` en las
  20 corridas. La variación que queda está en las entidades (`"envío"` vs `"el envío"`).
  Pero 0 de 20 respuestas cumplen el esquema tal cual: todas llegan envueltas en
  <code>```json ... ```</code> y hay que limpiarlas antes de `json.loads`.
- **C · `response_schema`:** 1 respuesta distinta (consistencia 100%), `positivo` 20/20
  y 20/20 JSON válidos sin limpieza.
- **Veredicto:** restringir la salida concentró la masa de probabilidad (5% → 85% → 100%).

Pedir el formato en el prompt ya desplaza la distribución; forzarlo con el esquema además
garantiza que la salida se pueda parsear. Aun así, la restricción no elimina el azar: en
una prueba corta previa (5 corridas) la estrategia C devolvió `neutro` en 2 de 5 y quedó
por debajo de B, porque la reseña es mixta y el enum no tiene `mixto`: la masa se reparte
entre las etiquetas vecinas. Justamente eso es lo que la restricción vuelve medible. Con
otra ejecución los números cambian; lo estable es que A queda muy por debajo de B y C,
mientras que entre B y C el orden depende de cómo se reparta el sentimiento.

El pushback ante preguntas sin sentido ("¿cómo calculo el momento de inercia de nuestro
codebase?") se muestra preguntando en vivo; no es parte de este script.

## Métricas

- **Respuestas únicas:** cuántas respuestas distintas hubo. Dos respuestas cuentan como
  iguales si dicen lo mismo: mismo JSON (ignorando espacios, orden de claves y el bloque
  <code>```json</code>) o mismo texto (ignorando espacios y saltos de línea).
- **Consistencia (%):** porcentaje de corridas que devolvieron la respuesta más frecuente.
- **Sentimiento (conteo):** cuántas veces apareció cada etiqueta en las respuestas JSON;
  "no medible" si ninguna respuesta trae una etiqueta legible. Una etiqueta que no está
  en el enum se marca "(fuera del enum)".
- **Cumple el esquema tal cual:** respuestas que validan contra el esquema de C sin
  ninguna limpieza (lo que obtendría un `json.loads` directo).
- **Corridas exitosas:** llamadas que respondieron tras los reintentos del cliente.
