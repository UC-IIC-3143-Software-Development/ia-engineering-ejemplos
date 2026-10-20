> Corrida real del 2026-09-28 · modelo `gemini-2.5-flash` · comando: `COLUMNS=110 python3 main.py` (20 corridas por estrategia, 205 s)

```text
╭──────────────────────────────────────────────────────────────────────────────────────╮
│ LLMs estocásticos: sentimiento libre vs restringido                                  │
│ Misma reseña, mismas corridas: ¿cuánto varía la salida según cuánto la restringimos? │
│ Modelo: gemini-2.5-flash | 20 corridas por estrategia                                │
╰──────────────────────────────────────────────────────────────────────────────────────╯

-- Estrategia A: libre --------------------------------------
Ejecutando 20 corridas...
╭──────────────────────────────────────────── Entrada al modelo ─────────────────────────────────────────────╮
│                                                                                                            │
│  USUARIO: Extrae el sentimiento y las entidades clave de esta reseña de un cliente: 'El                    │
│           envío tardó dos semanas y la caja llegó golpeada, pero el producto                               │
│           funciona perfecto y el soporte respondió rápido.'                                                │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────── Respuesta del modelo ───────────────────────────────────────────╮
│                                                                                                            │
│  MODELO: Aquí tienes el análisis de la reseña:  **Sentimiento General:** El sentimiento                    │
│          general es **mixto**. Aunque hay aspectos negativos importantes                                   │
│          relacionados con la entrega y el empaque, estos son compensados por la                            │
│          satisfacción con el producto en sí y la eficiencia del soporte al cliente.                        │
│          **Entidades Clave y su Sentimiento Asociado:**  *   **Envío:** Negativo                           │
│          (tardó dos semanas) *   **Caja (Empaque):** Negativo (llegó golpeada) *                           │
│          **Producto:** Positivo (funciona perfecto) *   **Soporte (al cliente):**                          │
│          Positivo (respondió rápido)                                                                       │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Recolectando el resto de las respuestas:
  Corrida #02: o  5.2s     Corrida #03: o  5.4s     Corrida #04: o  4.9s   
  Corrida #05: o  5.2s     Corrida #06: o  5.0s     Corrida #07: o  5.1s     Corrida #08: o  5.7s   
  Corrida #09: o  6.1s     Corrida #10: o  5.0s     Corrida #11: o  5.6s     Corrida #12: o  4.6s   
  Corrida #13: o  5.3s     Corrida #14: o  5.0s     Corrida #15: o  4.9s     Corrida #16: o  4.9s   
  Corrida #17: o  4.9s     Corrida #18: o  5.2s     Corrida #19: o  4.6s     Corrida #20: o  4.9s   

-- Estrategia B: JSON en el prompt --------------------------------------
Ejecutando 20 corridas...
╭──────────────────────────────────────────── Entrada al modelo ─────────────────────────────────────────────╮
│                                                                                                            │
│  USUARIO: Extrae el sentimiento y las entidades clave de esta reseña de un cliente: 'El                    │
│           envío tardó dos semanas y la caja llegó golpeada, pero el producto                               │
│           funciona perfecto y el soporte respondió rápido.' Responde solo con un                           │
│           objeto JSON con las claves 'sentimiento' y 'entidades'. 'sentimiento'                            │
│           debe ser un string (positivo, negativo, neutro). 'entidades' debe ser una                        │
│           lista de strings.                                                                                │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────── Respuesta del modelo ───────────────────────────────────────────╮
│                                                                                                            │
│  MODELO: ```json {   "sentimiento": "positivo",   "entidades": ["envío", "caja",                           │
│          "producto", "soporte"] } ```                                                                      │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Recolectando el resto de las respuestas:
  Corrida #02: o  2.4s     Corrida #03: o  3.3s     Corrida #04: o  4.1s   
  Corrida #05: o  3.3s     Corrida #06: o  4.2s     Corrida #07: o  3.4s     Corrida #08: o  2.5s   
  Corrida #09: o  2.5s     Corrida #10: o  3.3s     Corrida #11: o  2.9s     Corrida #12: o  2.4s   
  Corrida #13: o  2.0s     Corrida #14: o  3.6s     Corrida #15: o  3.8s     Corrida #16: o  3.3s   
  Corrida #17: o  2.3s     Corrida #18: o  2.0s     Corrida #19: o  2.4s     Corrida #20: o  4.1s   

-- Estrategia C: response_schema (enum) --------------------------------------
Ejecutando 20 corridas...
╭──────────────────────────────────────────── Entrada al modelo ─────────────────────────────────────────────╮
│                                                                                                            │
│  USUARIO: Extrae el sentimiento y las entidades clave de esta reseña de un cliente: 'El                    │
│           envío tardó dos semanas y la caja llegó golpeada, pero el producto                               │
│           funciona perfecto y el soporte respondió rápido.'                                                │
│                                                                                                            │
│  ESQUEMA: response_schema=AnalisisResena(sentimiento: Literal['positivo', 'negativo',                      │
│           'neutro'], entidades: list[str])                                                                 │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────── Respuesta del modelo ───────────────────────────────────────────╮
│                                                                                                            │
│  MODELO: {"sentimiento": "positivo", "entidades": ["envío", "caja", "producto", "soporte"]}                │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Recolectando el resto de las respuestas:
  Corrida #02: o  2.0s     Corrida #03: o  2.1s     Corrida #04: o  1.9s   
  Corrida #05: o  2.7s     Corrida #06: o  2.1s     Corrida #07: o  2.1s     Corrida #08: o  2.1s   
  Corrida #09: o  2.0s     Corrida #10: o  2.3s     Corrida #11: o  1.6s     Corrida #12: o  2.1s   
  Corrida #13: o  1.7s     Corrida #14: o  1.7s     Corrida #15: o  2.0s     Corrida #16: o  1.7s   
  Corrida #17: o  1.5s     Corrida #18: o  1.8s     Corrida #19: o  2.3s     Corrida #20: o  2.0s   

────────────────────────────────────────────────── Resumen ───────────────────────────────────────────────────

                                  Varianza según la restricción                                  
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Métrica                    ┃   A: libre    ┃ B: JSON en el prompt ┃ C: response_schema (enum) ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Respuestas únicas          │      20       │       2 (-18)        │          1 (-19)          │
├────────────────────────────┼───────────────┼──────────────────────┼───────────────────────────┤
│ Consistencia (%)           │     5.0%      │    85.0% (+80.0%)    │      100.0% (+95.0%)      │
├────────────────────────────┼───────────────┼──────────────────────┼───────────────────────────┤
│ Sentimiento (conteo)       │  no medible   │     positivo 20      │        positivo 20        │
│                            │ (texto libre) │                      │                           │
├────────────────────────────┼───────────────┼──────────────────────┼───────────────────────────┤
│ Cumple el esquema tal cual │     0/20      │         0/20         │           20/20           │
├────────────────────────────┼───────────────┼──────────────────────┼───────────────────────────┤
│ Corridas exitosas          │     20/20     │        20/20         │           20/20           │
└────────────────────────────┴───────────────┴──────────────────────┴───────────────────────────┘

VEREDICTO: restringir la salida concentró la masa de probabilidad (consistencia: libre 5% → JSON en prompt 
85%, response_schema 100%).

Todas las respuestas quedaron en corridas/ (una por estrategia).
```
