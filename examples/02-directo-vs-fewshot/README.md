# Directo vs Few-shot: domar el formato con ejemplos

Este prototipo muestra qué pasa cuando a un prompt simple ("Escribe un post de redes
sociales sobre [tema]") se le anteponen tres ejemplos resueltos. El pedido es el mismo; lo
único que cambia es que el modelo ve cómo se ve un buen post antes de escribir el suyo.

## El concepto

Un prompt directo deja abierto casi todo: largo, tono, plataforma, estructura, cuántas
versiones entregar. El modelo elige lo más probable para un pedido tan amplio y, en un
modelo de chat, eso suele ser "¡Claro! Aquí tienes varias opciones…" con encabezados,
listas y bloques de hashtags. Es un león suelto: cada corrida trae una forma distinta.

El few-shot ("tame the lion") agrega ejemplos al prompt. El modelo **desplaza su
distribución hacia salidas estructuralmente similares a los ejemplos** (in-context learning):
sin que el prompt describa ninguna regla, copia el patrón que ve.

### ¿Por qué pasa?

Un LLM predice el siguiente token condicionado a todo lo anterior. Si lo último que ve es
`Tema: ... Post:` después de tres pares `Tema:/Post:` que empiezan con un emoji, ocupan una
línea y cierran con un hashtag, la continuación más probable es otro post igual. Los
ejemplos fijan la forma; las palabras siguen variando.

Los ejemplos tienen un costo: más tokens de entrada en cada llamada. Y su calidad importa:
el modelo copia también sus defectos, y un caso que los ejemplos no cubren queda sin guía.

## Qué hace el prototipo

Compara dos estrategias sobre el mismo tema ("el lanzamiento de nuestra app de finanzas
personales"), con `gemini-2.5-flash` a temperatura 1.0 (la de fábrica de Gemini):

1. **Estrategia A — Directo:** `Escribe un post de redes sociales sobre <tema>.`
2. **Estrategia B — Few-shot:** la misma instrucción más 3 ejemplos `Tema:/Post:`
   (biblioteca, taller de cerámica, cafetería) y el tema nuevo al final.

Cada estrategia se ejecuta N veces (10 por defecto). La primera corrida se muestra completa
en los paneles "Entrada al modelo" / "Respuesta del modelo"; el resto aparece como
progreso (`o` = cumple el formato de los ejemplos, `x` = no cumple, `!` = error de API).
Al final, una tabla compara métricas de forma y costo, y una línea VEREDICTO se redacta a
partir de esos números.

Los posts completos quedan en `respuestas/directo.md` y `respuestas/few-shot.md` (carpeta
local ignorada por git; se sobrescribe en cada corrida).

## Setup

1. Python 3.10+.
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Define `GEMINI_API_KEY` en `<repo>/.env` (main.py lo encuentra subiendo desde su carpeta)
   o expórtala en la terminal:
   ```bash
   export GEMINI_API_KEY='tu_api_key'
   ```

## Cómo correr

```bash
python3 main.py            # 10 corridas por estrategia, ~3 min
python3 main.py --runs 3   # versión rápida para clase, ~1 min
```

La estrategia A es la lenta (~12 s por corrida): el modelo escribe más de 4.000 caracteres
cada vez.

## Qué observar

- **Estrategia A (directo):** ningún post cumple el formato. El modelo entrega varias
  "opciones" en Markdown (encabezados, negritas, listas con emojis, placeholders como
  `[Nombre de la App]`) y un bloque de hashtags. Cada corrida tiene una forma distinta.
- **Estrategia B (few-shot):** todos los posts empiezan con un emoji, ocupan una línea y
  terminan en un hashtag, igual que los ejemplos. El texto cambia de corrida en corrida
  (emoji, frase, hashtag), pero la forma es una sola.
- **El costo se invierte:** few-shot paga ~7 veces más tokens de entrada, pero genera ~40
  veces menos tokens de salida y es más rápido por corrida.

En la corrida grabada (`output-1.md`, 10 corridas por estrategia):

| Métrica | A: Directo | B: Few-shot |
|---|---|---|
| Conformidad (3 reglas) | RESULT_CONF_A | RESULT_CONF_B |
| Largo promedio (caracteres) | RESULT_LEN_A | RESULT_LEN_B |
| Formatos distintos | RESULT_FMT_A | RESULT_FMT_B |
| Tokens de entrada / salida (prom.) | RESULT_TOK_A | RESULT_TOK_B |

## Métricas

- **Conformidad (3 reglas):** % de posts que cumplen a la vez las tres reglas implícitas en
  los ejemplos. El desglose muestra cada una:
  - *emoji inicial:* el primer carácter es un símbolo Unicode (categoría `So` o plano
    U+1F000+). Un post que empieza con `**` o `¡` no cuenta.
  - *una sola línea:* el post no tiene saltos de línea.
  - *hashtag final:* el post termina en `#Palabra` (sin nada después).
- **Largo promedio y desviación estándar:** en caracteres; la desviación mide qué tan
  predecible es el largo.
- **Formatos distintos:** cantidad de firmas diferentes entre las N corridas. La firma de un
  post es (emoji inicial, nº de líneas, nº de hashtags, hashtag final): dos posts con las
  mismas palabras cambiadas pero igual estructura cuentan como el mismo formato.
- **Formato más frecuente:** % de corridas con la firma más común (análogo al "consistency
  score" de `non-deterministic`).
- **Tokens de entrada / salida:** promedio por llamada según `usage_metadata`. La salida
  cuenta solo el texto visible, no los tokens de "thinking" del modelo.

En la tabla, la columna Delta se pinta de verde cuando B mejora respecto de A, de rojo cuando
empeora (p. ej. más tokens de entrada) y en gris cuando la métrica es neutra (el largo).
