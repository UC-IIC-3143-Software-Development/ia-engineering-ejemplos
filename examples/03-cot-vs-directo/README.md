# Chain of Thought vs. Directo (y self-consistency)

Demuestra que **"piensa paso a paso" cambia la exactitud**, no solo el estilo, y que
**votar entre varias corridas (self-consistency)** corrige errores esporádicos, pero no
los sistemáticos. Compara tres estrategias (Directo, Zero-shot CoT y Few-shot CoT) sobre
5 tareas algorítmicas, con 8 corridas por estrategia.

## El concepto: por qué pasa

- **El modelo "calcula" mientras escribe.** Cada token generado es un paso de cómputo de
  tamaño fijo. Si la respuesta exige llevar estado (posición y orientación en una grilla,
  el acarreo de una multiplicación, un reloj que pasa la medianoche), pedir la respuesta
  directa obliga al modelo a sacarla en unos pocos tokens. Con CoT, los resultados
  intermedios quedan escritos en el contexto y cada token siguiente se apoya en ellos.
- **Zero-shot CoT** es una sola instrucción ("piensa paso a paso"). **Few-shot CoT**
  antepone ejemplos resueltos que fijan la estructura del razonamiento, y también su
  largo: el modelo imita los ejemplos.
- **Self-consistency.** El muestreo es estocástico, así que varias corridas CoT pueden
  terminar en respuestas distintas. Votar por mayoría filtra los errores que aparecen de
  vez en cuando. Si el modelo se equivoca casi siempre de la misma forma, la mayoría
  también se equivoca. Además, votar con N corridas cuesta N veces los tokens.
- **Tareas que no se pueden memorizar.** En `cot-vs-direct`, los acertijos clásicos (bate
  y pelota, máquinas y piezas) salen bien sin CoT porque el modelo los memorizó. Por eso
  este prototipo usa tareas algorítmicas con respuestas calculadas con código: última
  letra de cada palabra (el benchmark clásico del paper de CoT), contar letras,
  multiplicar números de 5×4 cifras, navegar una grilla y sumar etapas de un horario que
  cruza la medianoche.
- **Thinking desactivado.** `gemini-2.5-flash` razona internamente ("thinking") antes de
  responder, incluso si el prompt pide la respuesta directa. Para medir solo el efecto del
  prompt, `main.py` usa `THINKING_BUDGET = 0`. Más abajo está la nota con thinking activo.

## Qué hace el prototipo

- 5 preguntas × 3 estrategias × 8 corridas = **120 llamadas**, hasta 8 a la vez, con un
  `ThreadPoolExecutor`. La corrida completa tarda unos 25 s. El SDK reintenta los 429 y 5xx
  hasta 5 veces con backoff.
- Las tres estrategias piden la misma línea final, `Respuesta: <valor>`. Solo cambia
  cuánto razonamiento se pide:
  - **Directo:** "No muestres razonamiento ni pasos intermedios".
  - **Zero-shot CoT:** "Piensa paso a paso y muestra tu razonamiento".
  - **Few-shot CoT:** 3 ejemplos resueltos paso a paso (multiplicación, grilla y horario)
    y después la pregunta.
- El corrector toma la última línea `Respuesta:` y la normaliza (minúsculas, sin tildes,
  sin markdown). Luego la compara con la respuesta esperada.
- Salida:
  - la cabecera;
  - el intercambio completo (prompt y respuesta) de la corrida #1 de la pregunta 1 con
    cada estrategia;
  - por cada pregunta, un punto verde o rojo con la latencia de cada corrida y una tabla
    con aciertos, voto de mayoría, tokens de salida y tiempo;
  - al final, un resumen por pregunta, un resumen por estrategia y un **VEREDICTO**
    calculado a partir de los datos.
- **Self-consistency** se calcula votando por mayoría sobre las 8 corridas ya hechas de
  cada estrategia, sin llamadas extra. Un empate en el primer lugar cuenta como "sin
  respuesta", es decir, como fallo.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`GEMINI_API_KEY` va en `<repo>/.env` (una línea `GEMINI_API_KEY=...`) o exportada en la
terminal. `main.py` la carga con python-dotenv, que busca el `.env` desde la carpeta del
script hacia arriba.

## Cómo correr

```bash
python3 main.py            # 8 corridas por estrategia y pregunta (~25 s)
python3 main.py --runs 3   # versión corta para clase
```

## Qué observar (resultados de `output-1.md`)

| Pregunta | Directo | Zero-shot CoT | Few-shot CoT |
|---|---|---|---|
| Última letra (9 palabras) | 0/8 ✗ | 8/8 ✓ | 6/8 ✓ |
| Contar letras | 0/8 ✗ | 6/8 ✓ | 1/8 ✗ |
| Multiplicación 5×4 cifras | 0/8 ✗ | 8/8 ✓ | 8/8 ✓ |
| Navegación en grilla | 0/8 ✗ | 8/8 ✓ | 8/8 ✓ |
| Horario con pausas | 0/8 ✗ | 8/8 ✓ | 8/8 ✓ |
| **Exactitud por corrida** | **0/40 (0 %)** | **38/40 (95 %)** | **31/40 (78 %)** |
| **Self-consistency (voto de 8)** | 0/5 | 5/5 | 4/5 |
| Tokens entrada / salida por llamada | 76 / 9 | 76 / 455 | 639 / 192 |
| Latencia por llamada | 0.8 s | 2.4 s | 1.3 s |

(✓/✗ indica si la respuesta más votada fue la correcta).

1. **Directo falla todo (0/40), y siempre de la misma forma.** En la grilla responde `6,-2`
   en 6 de 8 corridas y en la multiplicación `404987058` en 4 de 8. Es un error
   sistemático, no ruido.
2. **Una línea de prompt lleva la exactitud de 0 % a 95 %.** Zero-shot CoT usa el mismo
   modelo y la misma pregunta. El costo es visible: unas 50 veces más tokens de salida
   (455 contra 9 por llamada) y unas 3 veces más latencia.
3. **Few-shot CoT no supera a zero-shot en este modelo.** Acierta 8/8 en las tres
   familias que cubren sus ejemplos (multiplicación, grilla y horario). En promedio genera
   menos de la mitad de tokens de salida (192 contra 455) y tarda casi la mitad (1.3 s
   contra 2.4 s). Pero paga 8.4 veces más tokens de entrada (639 contra 76) y baja en las
   dos tareas que ningún ejemplo cubre: 6/8 en "última letra" y 1/8 en "contar letras".
   En esta última copia el estilo compacto de los ejemplos, se salta letras y la
   respuesta más votada es 13 en vez de 14. Los ejemplos transfieren estructura y largo,
   así que la calidad y la cobertura importan más que la cantidad. En modelos modernos,
   zero-shot CoT suele bastar.
4. **El voto filtra ruido, no sesgo.** Votar entre las 8 corridas rescata "contar letras"
   en zero-shot (6/8, y el voto elige `14` ✓) y "última letra" en few-shot (6/8 ✓). No
   corrige few-shot en "contar letras" (1/8: la mayoría vota `13`) ni al directo (0/5).

Los números cambian de una ejecución a otra, porque el modelo es estocástico (ver `01-estocastico`).
En una ejecución anterior del mismo script, zero-shot hizo 8/8 en "contar letras" y
few-shot hizo 0/8. La conclusión fue la misma: Directo ≈ 0 %, zero-shot CoT ≥ 95 % y
few-shot peor en las tareas que sus ejemplos no cubren (7/8 y 0/8).

## Métricas

- **Exactitud por corrida:** corridas correctas sobre el total (5 preguntas × N).
- **Self-consistency (voto de N):** preguntas cuya respuesta más votada entre las N
  corridas es la correcta.
- **Tokens de entrada / salida por llamada:** promedio de
  `usage_metadata.prompt_token_count` y de `candidates_token_count`, más
  `thoughts_token_count` cuando thinking está activo, porque también se factura como
  salida.
- **Latencia por llamada:** tiempo de pared de `generate_content`, con reintentos
  incluidos. Las llamadas corren en paralelo, así que el tiempo total es mucho menor que
  la suma.
- **VEREDICTO:** se calcula a partir de estas métricas. Resume el salto de exactitud de
  CoT y su costo en tokens, la comparación few-shot contra zero-shot y cuántas preguntas
  rescató (o no) el voto.

## Nota: ¿y con thinking activo?

Con `THINKING_BUDGET = None` (thinking dinámico, el default del modelo) hicimos una
verificación con `--runs 4`:

- **Directo:** 17/20 (85 %), pero con 429 tokens de salida por llamada en vez de 9 y
  2.4 s de latencia en vez de 0.8 s. El razonamiento ocurre igual: queda oculto y se
  factura como salida.
- **Zero-shot y few-shot CoT:** 20/20.

Ese es el matiz: CoT requiere un modelo que razone, y los modelos de
razonamiento ya internalizan la cadena. El costo no desaparece: se traslada a tokens que
no se ven.
