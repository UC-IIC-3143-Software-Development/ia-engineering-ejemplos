# Salida capturada — 2026-09-28 · modelo `gemini-2.5-flash` (thinking desactivado) · `COLUMNS=110 python3 main.py` (8 corridas por defecto)

```text
╭────────────────────────────────────────────────────────────────────────────────────────────╮
│ Chain of Thought vs. Directo (y self-consistency)                                          │
│ ¿Pensar paso a paso sube la exactitud? ¿Y votar entre corridas?                            │
│ Modelo: gemini-2.5-flash (thinking desactivado) | 8 corridas × 3 estrategias × 5 preguntas │
╰────────────────────────────────────────────────────────────────────────────────────────────╯

──────────────────────────── Intercambio de muestra: corrida #1 de la pregunta 1 ─────────────────────────────
╭─────────────────────────────────────── Entrada al modelo · Directo ────────────────────────────────────────╮
│                                                                                                            │
│  USUARIO: Toma la última letra de cada una de estas palabras y concaténalas en orden, sin                  │
│           espacios: volcán, reloj, nariz, pared, camión, tenedor, ciudad, arroz,                           │
│           fénix.                                                                                           │
│                                                                                                            │
│           No muestres razonamiento ni pasos intermedios. Responde únicamente con una línea:                │
│           'Respuesta: <valor>'.                                                                            │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────── Respuesta del modelo · Directo ──────────────────────────────────────╮
│                                                                                                            │
│  MODELO: Respuesta: njzdrrddzx                                                                             │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────── Entrada al modelo · Zero-shot CoT ─────────────────────────────────────╮
│                                                                                                            │
│  USUARIO: Toma la última letra de cada una de estas palabras y concaténalas en orden, sin                  │
│           espacios: volcán, reloj, nariz, pared, camión, tenedor, ciudad, arroz,                           │
│           fénix.                                                                                           │
│                                                                                                            │
│           Piensa paso a paso y muestra tu razonamiento. Termina con una última línea:                      │
│           'Respuesta: <valor>'.                                                                            │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────────────── Respuesta del modelo · Zero-shot CoT ───────────────────────────────────╮
│                                                                                                            │
│  MODELO: Vamos a tomar la última letra de cada palabra y concatenarlas en orden:                           │
│                                                                                                            │
│          1.  **volcá**n -> **n**                                                                           │
│          2.  relo**j** -> **j**                                                                            │
│          3.  nari**z** -> **z**                                                                            │
│          4.  pare**d** -> **d**                                                                            │
│          5.  camio**n** -> **n**                                                                           │
│          6.  tenedo**r** -> **r**                                                                          │
│          7.  ciuda**d** -> **d**                                                                           │
│          8.  arro**z** -> **z**                                                                            │
│          9.  féni**x** -> **x**                                                                            │
│                                                                                                            │
│          Ahora, concatenamos estas letras en el orden en que aparecen:                                     │
│          n + j + z + d + n + r + d + z + x                                                                 │
│                                                                                                            │
│          Respuesta: njzdnrdzx                                                                              │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

╭───────────────────────────────────── Entrada al modelo · Few-shot CoT ─────────────────────────────────────╮
│                                                                                                            │
│  USUARIO: Resuelve el problema. Razona paso a paso como en los ejemplos y termina con una                  │
│           última línea: 'Respuesta: <valor>'.                                                              │
│                                                                                                            │
│           Pregunta: ¿Cuánto es 4127 × 358?                                                                 │
│           Razonamiento: Multiplico por cada cifra de 358 y sumo los productos parciales.                   │
│           - 4127 × 8 = 33016                                                                               │
│           - 4127 × 50 = 206350                                                                             │
│           - 4127 × 300 = 1238100                                                                           │
│           - Suma: 33016 + 206350 = 239366; 239366 + 1238100 = 1477466                                      │
│           Respuesta: 1477466                                                                               │
│                                                                                                            │
│           Pregunta: Partes en el origen (0, 0) mirando al norte (+Y). Avanza 2. Gira a la                  │
│           izquierda. Avanza 3. Gira a la izquierda. Retrocede 1. ¿Cuáles son tus                           │
│           coordenadas finales? Formato (X, Y).                                                             │
│           Razonamiento: Anoto posición y orientación después de cada instrucción.                          │
│           - Inicio: (0, 0), mirando al norte.                                                              │
│           - Avanza 2 hacia el norte: (0, 2), mirando al norte.                                             │
│           - Gira a la izquierda: (0, 2), mirando al oeste.                                                 │
│           - Avanza 3 hacia el oeste: (-3, 2), mirando al oeste.                                            │
│           - Gira a la izquierda: (-3, 2), mirando al sur.                                                  │
│           - Retrocede 1 (mirando al sur, retroceder es moverse al norte): (-3, 3), mirando                 │
│           al sur.                                                                                          │
│           Respuesta: (-3, 3)                                                                               │
│                                                                                                            │
│           Pregunta: Una reunión empieza a las 23:20 y tiene dos bloques de 50 y 35 minutos                 │
│           con una pausa de 10 minutos entre ellos. ¿A qué hora termina? Formato                            │
│           HH:MM.                                                                                           │
│           Razonamiento: Avanzo el reloj bloque por bloque.                                                 │
│           - Inicio: 23:20.                                                                                 │
│           - Bloque 1 (50 min): 23:20 + 0:50 = 00:10 (pasa la medianoche).                                  │
│           - Pausa (10 min): 00:10 + 0:10 = 00:20.                                                          │
│           - Bloque 2 (35 min): 00:20 + 0:35 = 00:55.                                                       │
│           Respuesta: 00:55                                                                                 │
│                                                                                                            │
│           Pregunta: Toma la última letra de cada una de estas palabras y concaténalas en                   │
│           orden, sin espacios: volcán, reloj, nariz, pared, camión, tenedor,                               │
│           ciudad, arroz, fénix.                                                                            │
│           Razonamiento:                                                                                    │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────────────── Respuesta del modelo · Few-shot CoT ────────────────────────────────────╮
│                                                                                                            │
│  MODELO: Extraigo la última letra de cada palabra y las uno.                                               │
│          - volcá**n** -> n                                                                                 │
│          - relo**j** -> j                                                                                  │
│          - nari**z** -> z                                                                                  │
│          - pare**d** -> d                                                                                  │
│          - camió**n** -> n                                                                                 │
│          - tenedo**r** -> r                                                                                │
│          - ciuda**d** -> d                                                                                 │
│          - arro**z** -> z                                                                                  │
│          - féni**x** -> x                                                                                  │
│          - Concatenación: njzdnrdzx                                                                        │
│          Respuesta: njzdnrdzx                                                                              │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

────────────────────────────────── Pregunta 1/5: Última letra (9 palabras) ───────────────────────────────────
P: Toma la última letra de cada una de estas palabras y concaténalas en orden, sin espacios: volcán, reloj, 
nariz, pared, camión, tenedor, ciudad, arroz, fénix.
Respuesta correcta: njzdnrdzx
volcán→n, reloj→j, nariz→z, pared→d, camión→n, tenedor→r, ciudad→d, arroz→z, fénix→x.

  Directo       #01 ● 1.6s #02 ● 1.5s #03 ● 1.4s #04 ● 1.5s #05 ● 1.4s #06 ● 1.4s #07 ● 1.1s #08 ● 1.3s
  Zero-shot CoT #01 ● 1.1s #02 ● 1.3s #03 ● 1.2s #04 ● 1.2s #05 ● 1.3s #06 ● 1.3s #07 ● 1.2s #08 ● 1.2s
  Few-shot CoT  #01 ● 1.0s #02 ● 0.8s #03 ● 0.9s #04 ● 0.9s #05 ● 0.9s #06 ● 1.0s #07 ● 1.0s #08 ● 1.0s

  Estrategia     ┃  Aciertos por corrida         ┃  Voto de mayoría     ┃  Tokens salida  ┃  Tiempo prom.  
━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━
  Directo        │  ░░░░░░░░░░░░░░░░ 0/8 (0%)    │  njzdrrddzx (4/8) ✗  │              9  │          1.4s  
  Zero-shot CoT  │  ████████████████ 8/8 (100%)  │  njzdnrdzx (8/8) ✓   │            189  │          1.2s  
  Few-shot CoT   │  ████████████░░░░ 6/8 (75%)   │  njzdnrdzx (6/8) ✓   │             95  │          0.9s  

──────────────────────────────────────── Pregunta 2/5: Contar letras ─────────────────────────────────────────
P: ¿Cuántas veces aparece la letra 'r' en la frase 'el perro de rosa corre rápido por la carretera rural hacia
el barrio'?
Respuesta correcta: 14
perro 2 + rosa 1 + corre 2 + rápido 1 + por 1 + carretera 3 + rural 2 + barrio 2 = 14.

  Directo       #01 ● 0.6s #02 ● 0.6s #03 ● 0.4s #04 ● 0.4s #05 ● 0.5s #06 ● 0.5s #07 ● 0.4s #08 ● 0.4s
  Zero-shot CoT #01 ● 1.5s #02 ● 1.8s #03 ● 1.6s #04 ● 1.9s #05 ● 2.3s #06 ● 2.0s #07 ● 1.9s #08 ● 2.1s
  Few-shot CoT  #01 ● 1.4s #02 ● 1.2s #03 ● 1.3s #04 ● 1.2s #05 ● 0.9s #06 ● 1.0s #07 ● 1.2s #08 ● 1.2s

  Estrategia     ┃  Aciertos por corrida        ┃  Voto de mayoría  ┃  Tokens salida  ┃  Tiempo prom.  
━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━
  Directo        │  ░░░░░░░░░░░░░░░░ 0/8 (0%)   │  10 (5/8) ✗       │              6  │          0.5s  
  Zero-shot CoT  │  ████████████░░░░ 6/8 (75%)  │  14 (6/8) ✓       │            256  │          1.9s  
  Few-shot CoT   │  ██░░░░░░░░░░░░░░ 1/8 (12%)  │  13 (3/8) ✗       │            146  │          1.2s  

────────────────────────────────── Pregunta 3/5: Multiplicación 5×4 cifras ───────────────────────────────────
P: ¿Cuánto es 58374 × 6927?
Respuesta correcta: 404356698
58374×7 = 408618; ×20 = 1167480; ×900 = 52536600; ×6000 = 350244000; suma = 404356698.

  Directo       #01 ● 0.7s #02 ● 0.8s #03 ● 0.6s #04 ● 0.6s #05 ● 0.6s #06 ● 0.5s #07 ● 0.6s #08 ● 0.6s
  Zero-shot CoT #01 ● 2.6s #02 ● 2.4s #03 ● 2.6s #04 ● 2.9s #05 ● 2.8s #06 ● 4.8s #07 ● 5.3s #08 ● 2.4s
  Few-shot CoT  #01 ● 1.6s #02 ● 1.4s #03 ● 1.1s #04 ● 1.4s #05 ● 1.4s #06 ● 1.3s #07 ● 1.3s #08 ● 1.3s

  Estrategia     ┃  Aciertos por corrida         ┃  Voto de mayoría    ┃  Tokens salida  ┃  Tiempo prom.  
━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━
  Directo        │  ░░░░░░░░░░░░░░░░ 0/8 (0%)    │  404987058 (4/8) ✗  │             13  │          0.6s  
  Zero-shot CoT  │  ████████████████ 8/8 (100%)  │  404356698 (8/8) ✓  │            634  │          3.2s  
  Few-shot CoT   │  ████████████████ 8/8 (100%)  │  404356698 (8/8) ✓  │            198  │          1.3s  

───────────────────────────────────── Pregunta 4/5: Navegación en grilla ─────────────────────────────────────
P: Partes en el origen (0, 0) mirando al norte (+Y). Avanza 5. Gira a la derecha. Avanza 2. Gira a la derecha.
Avanza 8. Gira a la izquierda. Retrocede 4. Gira a la izquierda. Avanza 3. Gira a la derecha. Avanza 1. 
¿Cuáles son tus coordenadas finales? Formato (X, Y).
Respuesta correcta: -1,0
N (0,5) → E (2,5) → S (2,-3) → E, retroceder 4 es ir al oeste (-2,-3) → N (-2,0) → E (-1,0).

  Directo       #01 ● 0.5s #02 ● 0.5s #03 ● 0.5s #04 ● 0.6s #05 ● 1.0s #06 ● 0.9s #07 ● 0.8s #08 ● 0.9s
  Zero-shot CoT #01 ● 3.1s #02 ● 3.5s #03 ● 3.5s #04 ● 3.3s #05 ● 3.0s #06 ● 3.9s #07 ● 3.5s #08 ● 3.5s
  Few-shot CoT  #01 ● 1.4s #02 ● 1.4s #03 ● 1.5s #04 ● 1.3s #05 ● 1.5s #06 ● 1.5s #07 ● 1.5s #08 ● 1.5s

  Estrategia     ┃  Aciertos por corrida         ┃  Voto de mayoría  ┃  Tokens salida  ┃  Tiempo prom.  
━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━
  Directo        │  ░░░░░░░░░░░░░░░░ 0/8 (0%)    │  6,-2 (6/8) ✗     │              9  │          0.7s  
  Zero-shot CoT  │  ████████████████ 8/8 (100%)  │  -1,0 (8/8) ✓     │            747  │          3.4s  
  Few-shot CoT   │  ████████████████ 8/8 (100%)  │  -1,0 (8/8) ✓     │            255  │          1.5s  

────────────────────────────────────── Pregunta 5/5: Horario con pausas ──────────────────────────────────────
P: Un proceso empieza a las 22:38 y tiene 4 etapas de 47, 125, 33 y 76 minutos, con una pausa de 8 minutos 
entre etapas consecutivas. ¿A qué hora termina? Formato HH:MM.
Respuesta correcta: 03:43
Etapas 47+125+33+76 = 281 min + 3 pausas × 8 = 305 min = 5 h 05 min; 22:38 + 5:05 = 03:43.

  Directo       #01 ● 0.5s #02 ● 0.5s #03 ● 0.8s #04 ● 0.4s #05 ● 0.5s #06 ● 0.5s #07 ● 0.8s #08 ● 1.0s
  Zero-shot CoT #01 ● 2.6s #02 ● 2.3s #03 ● 2.5s #04 ● 2.7s #05 ● 2.1s #06 ● 2.4s #07 ● 2.6s #08 ● 2.5s
  Few-shot CoT  #01 ● 1.5s #02 ● 1.5s #03 ● 1.3s #04 ● 1.5s #05 ● 1.4s #06 ● 1.5s #07 ● 1.4s #08 ● 1.5s

  Estrategia     ┃  Aciertos por corrida         ┃  Voto de mayoría  ┃  Tokens salida  ┃  Tiempo prom.  
━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━
  Directo        │  ░░░░░░░░░░░░░░░░ 0/8 (0%)    │  01:21 (2/8) ✗    │              9  │          0.6s  
  Zero-shot CoT  │  ████████████████ 8/8 (100%)  │  03:43 (8/8) ✓    │            449  │          2.5s  
  Few-shot CoT   │  ████████████████ 8/8 (100%)  │  03:43 (8/8) ✓    │            266  │          1.5s  

────────────────────────────────────────────────── Resumen ───────────────────────────────────────────────────

          Aciertos por pregunta (corridas correctas / voto de mayoría)          
  Pregunta                   ┃    Directo    ┃  Zero-shot CoT  ┃  Few-shot CoT  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━
  Última letra (9 palabras)  │  0/8  voto ✗  │   8/8  voto ✓   │  6/8  voto ✓   
  Contar letras              │  0/8  voto ✗  │   6/8  voto ✓   │  1/8  voto ✗   
  Multiplicación 5×4 cifras  │  0/8  voto ✗  │   8/8  voto ✓   │  8/8  voto ✓   
  Navegación en grilla       │  0/8  voto ✗  │   8/8  voto ✓   │  8/8  voto ✓   
  Horario con pausas         │  0/8  voto ✗  │   8/8  voto ✓   │  8/8  voto ✓   

                                          Resumen por estrategia                                          
               ┃                          ┃ Self-consistency ┃ Tokens entrada ┃ Tokens salida ┃  Latencia 
 Estrategia    ┃ Exactitud por corrida    ┃   (voto de 8)    ┃      / llamada ┃     / llamada ┃ / llamada 
━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━
 Directo       │ ░░░░░░░░░░░░ 0/40 (0%)   │  0/5 preguntas   │             76 │             9 │      0.8s 
 Zero-shot CoT │ ███████████░ 38/40 (95%) │  5/5 preguntas   │             76 │           455 │      2.4s 
 Few-shot CoT  │ █████████░░░ 31/40 (78%) │  4/5 preguntas   │            639 │           192 │      1.3s 
Self-consistency reutiliza las 8 corridas ya hechas; en producción cuesta 8× tokens por respuesta (y 8 
llamadas en paralelo).

VEREDICTO: CoT sube la exactitud por corrida de 0% (Directo) a 95% (Zero-shot CoT), +95 pp, generando 50× 
tokens de salida.
Few-shot vs zero-shot CoT: 78% vs 95%, con 8.4× tokens de entrada y 0.4× de salida.
Self-consistency (voto de 8): Directo 0/5, Zero-shot 5/5, Few-shot 4/5 preguntas; en CoT el voto rescató 2 
pregunta(s) con fallos esporádicos y no corrigió 1 donde la respuesta correcta no era la más votada.

Tiempo total: 23s
```
