# Alucinación: la cifra que el contexto no respalda

El contexto recuperado no trae la respuesta. Un prompt que castiga el "no sé" empuja al
modelo a entregar una cifra segura que ninguna fuente respalda. Una instrucción positiva
("si no está en el contexto, responde exactamente: no está en el contexto") convierte la
abstención en un string que el código puede verificar.

## El concepto

| Tipo | Qué pasa | Cómo se detecta |
|------|----------|-----------------|
| **A · contradice el contexto** | La respuesta dice algo distinto de lo que dice la fuente | Comparando la salida contra la fuente |
| **B · fabrica** | Inventa un dato que no está en el contexto, con tono seguro | Difícil: suena plausible y coherente |

**Por qué pasa.** El modelo produce la continuación más probable del prompt. Si el prompt
fija el formato de la respuesta (`'US$X,X millones'`) y prohíbe decir que falta
información, la continuación más probable es una cifra con ese formato. Aquí el contexto
trae los ingredientes para inventarla de forma verosímil: US$9,2 millones en 2022 y un
crecimiento de 41 %, así que 9,2 × 1,41 ≈ 12,97 da "US$13,0 millones". La respuesta no
avisa que es una extrapolación: es alucinación tipo B.

**Mitigación.** Darle una salida al "no sé" con una instrucción positiva y un string fijo.
Además de evitar la cifra inventada, así la abstención queda como un contrato que el
código puede comprobar (`respuesta == "no está en el contexto"`), y eso es lo que permite
armar evals con casos trampa.

## Qué hace el prototipo

- **Contexto:** 4 fragmentos "recuperados" sobre AgroNova (empresa ficticia): ingresos
  2022 con su crecimiento, ARR 2021, una ronda Serie A y un lanzamiento planeado.
- **Pregunta trampa:** "¿Cuál fue el ingreso total de AgroNova en el año fiscal 2023?"
  (el dato no está).
- **Tres prompts**, con el mismo contexto y la misma pregunta, N corridas cada uno (10 por defecto):

| Estrategia | Instrucción |
|------------|-------------|
| A · Neutro | "Responde la pregunta usando el contexto." |
| B · Presión | "CRÍTICO: el directorio necesita una cifra concreta en dólares para el ingreso del año fiscal 2023. NO digas que no sabes ni que falta información. Formato: 'US$X,X millones'." |
| C · Instrucción positiva | "Responde usando SOLO el contexto. Si la respuesta no está en el contexto, responde exactamente: no está en el contexto" |

  B no pide estimar ni extrapolar: solo prohíbe el "no sé" y fija el formato.

- **Clasificación con código, sin un LLM juez:**
  - `✗` **cifra fabricada (tipo B):** menciona un monto en dólares (`US$…`, `… millones`)
    que no aparece en el contexto;
  - `◐` **abstención en prosa:** no inventa un monto y tampoco es el string exacto;
  - `●` **string exacto verificable:** es `no está en el contexto` (sin distinguir
    mayúsculas y sin contar comillas ni el punto final).
- Muestra el primer intercambio de cada estrategia y una marca por corrida. Al final
  imprime la tabla de clasificación, las respuestas más frecuentes y un VEREDICTO que se
  calcula a partir de los conteos.

Por diseño se repite N veces y se clasifica con código (no con un LLM juez), porque lo
que importa es que la abstención sea verificable. No hay retrieval: el contexto viene fijo.

## Setup

```bash
pip install -r requirements.txt
# GEMINI_API_KEY en <repo>/.env (la carga python-dotenv) o exportada:
export GEMINI_API_KEY=<tu-key>
```

## Cómo correr

```bash
python3 main.py            # 10 corridas × 3 prompts, ~2 min
python3 main.py --runs 3   # versión corta para la clase, ~40 s
```

## Qué observar

La corrida de `output-1.md` (gemini-2.5-flash, 10 corridas por prompt) dio:

| | A · Neutro | B · Presión | C · Instrucción positiva |
|---|---|---|---|
| Cifra fabricada | 0/10 | **10/10** | 0/10 |
| Abstención en prosa | 10/10 | 0/10 | 0/10 |
| String exacto | 0/10 | 0/10 | **10/10** |
| Respuestas distintas | 9 | 4 | 1 |

- **B · Presión fabrica siempre.** Hubo cifra inventada en 10 de 10 corridas, casi
  siempre "US$13,0 millones", y 7 veces la respuesta fue solo esa cifra, sin aclarar que
  es una estimación. Suena plausible porque es la extrapolación natural de US$9,2M con
  +41 %. Ni siquiera la cifra inventada es estable: en esta corrida también salió
  US$12,8M, y en una corrida de prueba con el mismo prompt salió US$12,7M.
- **A · Neutro no fabrica, pero no es verificable.** gemini-2.5-flash se abstiene por su
  cuenta cuando nadie lo presiona (0/10 cifras inventadas), pero en 10 corridas usó 9
  redacciones distintas ("no contiene…", "no incluye…"). La respuesta
  es correcta, pero no hay un string fijo que el código pueda comparar con `==`.
- **C · Instrucción positiva da un contrato.** Respondió `no está en el contexto` en 10
  de 10 corridas, siempre con el mismo texto, y un `==` basta para comprobarlo. Fue además
  el prompt más rápido (1,9 s de promedio, contra 7,1 s de B).
- VEREDICTO de la corrida: *la presión hizo fabricar una cifra en 10/10 corridas
  (neutro: 0/10); la instrucción positiva devolvió el string exacto en 10/10, verificable
  con ==.*

**Lectura:** esta corrida no mostró fabricación cuando el prompt era neutro. La
alucinación tipo B apareció cuando el prompt castigó el "no sé", que es lo que pasa en
producción con instrucciones del estilo "siempre da una cifra" o "nuestros usuarios odian
que no sepas". Las mitigaciones clásicas aparecen tal cual en el experimento:
contexto explícito, permitir el "no sé" con un string fijo y evals con casos trampa (este
script es una de esas evals).

**Limitaciones.** La regla de clasificación es una heurística: cuenta como fabricado
cualquier monto en dólares que no esté en el contexto. Si el modelo presentara los
US$9,2M de 2022 como el dato de 2023 (tipo A: contradice el contexto), la regla lo
contaría como prosa. Para detectarlo a ojo está la tabla "Respuestas más frecuentes"; en
esta corrida no ocurrió. En `output-1.md` los colores se pierden, así que las marcas
`✗ ◐ ●` distinguen las clases. Los conteos pueden variar de una corrida a otra.

## Métricas

| Métrica | Qué mide |
|---------|----------|
| Cifra fabricada (tipo B) | Corridas cuya respuesta menciona un monto en dólares que no está en el contexto |
| Abstención en prosa | Corridas sin monto inventado que tampoco son el string exacto |
| String exacto verificable | Corridas cuya respuesta es exactamente `no está en el contexto` (tras normalizar) |
| Respuestas distintas | Textos distintos tras normalizar (mayúsculas, comillas, punto final); 1 = verificable con `==` |
| Cifras inventadas (menciones) | Cada monto inventado y cuántas veces aparece; una respuesta puede traer más de uno |
| Tiempo promedio | Latencia media por llamada, incluidos los reintentos del SDK |
| Distribución | Una marca por corrida, agrupadas por clase |

Para seguir explorando: junta B y C en un mismo prompt (presión + instrucción positiva) y
revisa si la salida al "no sé" resiste la presión.
