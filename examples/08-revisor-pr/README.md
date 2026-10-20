# Bot revisor de PRs: reglas de negocio verificables

Un bot que lee un archivo Python de un pull request y lo revisa contra las **reglas de negocio del
equipo**, no contra una persona ("eres un ingeniero senior") ni contra un principio vago ("usa clean
code").

## El concepto

"Eres un experto en Python, revisa este PR" deja que el modelo decida qué importa. El resultado es
texto libre: largo, distinto en cada corrida, mezcla estilo con bugs graves y **no se puede
comprobar**. Además, el modelo no conoce las reglas propias del negocio: que el IVA se lee de
`config.IVA_CL`, que el descuento tiene tope de 30 % o que los datos personales se loguean con
`enmascarar()`.

Un prompt confiable explicita tarea, restricción, salida y casos borde. Aplicado a la revisión de código:

| Elemento | En este bot |
|---|---|
| **Tarea** | Verificar CADA regla de una lista cerrada, con ID |
| **Restricción** | No comentar nada fuera de la lista (ni estilo, ni nombres, ni docstrings) |
| **Salida** | JSON validado (Pydantic): `regla_id`, `veredicto` (cumple / no_cumple / no_aplica), `lineas`, `evidencia` (cita literal), `sugerencia` |
| **Casos borde** | "no_aplica" si el código no toca lo que la regla regula |

Cada regla dice qué se permite, qué se prohíbe y dónde mirar. Eso es lo que la vuelve verificable:

| ID | Regla | Tipo |
|---|---|---|
| NEG-01 | Montos de dinero con `decimal.Decimal`; prohibido `float` | bloqueante |
| NEG-02 | IVA desde `config.IVA_CL`; prohibido escribir `0.19` / `1.19` | advertencia |
| NEG-03 | Descuento acotado explícitamente a máx. 30 % del subtotal | bloqueante |
| SEG-01 | Sin API keys, tokens ni passwords literales; usar `os.environ[...]` | bloqueante |
| SEG-02 | SQL con parámetros (`%s` + tupla); prohibido f-string / concatenación | bloqueante |
| SEG-03 | Email, RUT y tarjeta nunca en `log.*` ni `print`; usar `enmascarar()` | bloqueante |
| PERF-01 | Sin consultas a la BD dentro de `for`/`while` (N+1) | bloqueante |
| PERF-02 | Toda llamada HTTP con `timeout=` ≤ 10 s | advertencia |
| DAT-01 | Stock y pedido en una misma transacción; sin `commit()` entre ambos | bloqueante |

## Qué hace el prototipo

1. Lee el archivo a revisar (por defecto `pr_checkout.py`, un checkout de e-commerce con violaciones
   plantadas) y le antepone número de línea a cada línea.
2. **A) Prompt vago:** "ingeniero senior + clean code". Muestra la respuesta tal cual.
3. **B) Bot con reglas:** pide un veredicto por regla con `response_schema` y `temperature=0`.
4. **Comprueba por código** lo que el modelo afirma:
   - que las 9 reglas tengan veredicto (si falta alguna, la revisión es inválida);
   - que cada cita de violación exista literalmente en el archivo (descarta hallazgos inventados).
5. Arma el comentario que el bot publicaría en el PR y, como un check de CI, **termina con código 1**
   si hay reglas bloqueantes incumplidas.
6. Si revisa `pr_checkout.py`, compara con la verdad-terreno (`VERDAD` en `main.py`): 7 reglas
   incumplidas y 2 que se cumplen (NEG-03 y PERF-02), para medir también falsos positivos.

## Setup

```bash
pip install -r requirements.txt
# GEMINI_API_KEY en <repo>/.env (lo carga python-dotenv) o exportada:
export GEMINI_API_KEY=tu_key
```

## Cómo correr

```bash
python3 main.py                      # revisa pr_checkout.py
python3 main.py ruta/a/otro_archivo.py
echo $?                              # 1 = PR bloqueado, 0 = aprobado
```

Tarda ~1 minuto (2 llamadas; la respuesta vaga es larga). La corrida grabada está en `output-1.md`.

## Qué observar

- **A)** La respuesta vaga es un ensayo (~2.600 palabras en `output-1.md`). Encuentra problemas
  reales, pero no se puede saber sin leerla completa si revisó cada regla del equipo, y cambia en
  cada corrida. Tampoco conoce las convenciones propias (`config.IVA_CL`, `enmascarar()`, el tope de
  30 %).
- **B)** El bot da exactamente 9 veredictos. En `output-1.md`: **9/9 correctos** contra la
  verdad-terreno (incluye no marcar NEG-03 ni PERF-02, que sí se cumplen), **7/7 citas verificadas**
  contra el código y `VEREDICTO: PR BLOQUEADO` con 6 reglas bloqueantes.
- Las **líneas** que reporta el modelo pueden venir corridas en uno. Por eso la verificación se hace
  sobre la cita literal y no sobre el número de línea: se comprueba lo que el modelo copia, no lo que
  cuenta.
- La regla hace el trabajo, no la persona: si cambias una regla (p.ej. el tope a 20 %) cambia la
  revisión, sin tocar el system prompt.

## Métricas

- **Reglas evaluadas:** reglas con veredicto / total (tiene que ser 9/9 o la revisión es inválida).
- **Citas verificadas:** citas de violación que aparecen literalmente en el código.
- **Violaciones detectadas y veredictos correctos:** contra `VERDAD`, solo con el archivo por defecto.
