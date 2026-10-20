# Prompt como código: registry + arnés de regresión

Este prototipo guarda dos versiones de un prompt de triage en un registry versionado y corre los mismos
10 casos contra ambas. Muestra cómo un cambio que arregla los casos que motivaron el cambio también
puede romper, sin avisar, casos que antes funcionaban. Esas regresiones silenciosas no se ven en el
puntaje total: hay que comparar caso a caso.

## El concepto

Si el prompt decide el comportamiento del sistema, es código y se trata como tal:

- **Registry**: el prompt no se hardcodea en el call site. Vive en un registry con clave
  `nombre@vN` y es un template con parámetros (`{mensaje}`). En producción suele ser Jinja y un
  servicio o repositorio compartido; aquí es un `dict` y `str.format` para no agregar dependencias.
- **Versiones inmutables**: una versión publicada no se edita. Cada cambio es una clave nueva, y
  la versión en producción queda congelada hasta que otra la reemplace.
- **Evals por versión**: antes de promover una versión nueva se corre la misma suite contra ambas.
  La suite es la especificación: describe el comportamiento que queremos hoy.

### Por qué aparecen regresiones

`triage_ticket@v2` nace de reclamos reales: cobros duplicados que llegaban con urgencia media y una
cuenta hackeada que se derivó a "general". Para arreglarlos, v2 hace tres cosas que suenan razonables
por separado:

1. **Agrega una regla correcta**: un cobro duplicado o no reconocido es urgencia alta.
2. **Manda la seguridad a `tecnico`**: declara los incidentes de seguridad como `alta/tecnico` y agrega
   una regla por palabra clave: todo mensaje que mencione "contraseña", "cuenta", "acceso", "sesión",
   "API" o "token" es urgencia alta y categoría `tecnico`, *sin importar el contexto*.
3. **"Limpia" v1**: borra las aclaraciones que decían que los tokens o la documentación de la API
   para uso personal, dónde cambiar la contraseña y las copias de facturas son urgencia baja, y
   además agrega que las facturas para la contabilidad son urgencia media.

Las reglas 1 y 2 arreglan los casos del reclamo. La regla 2 aplicada sin contexto y la limpieza
de la regla 3 rompen consultas rutinarias que v1 resolvía bien. Si solo se mira el total, no se
nota nada.

## Qué hace el prototipo

1. Muestra el registry (clave, estado, líneas) y el diff línea a línea de v1 a v2.
2. Corre los 10 casos `--runs` veces (3 por defecto) contra cada versión, con salida estructurada
   (`response_schema` con enums de Pydantic) y `temperature=0`. Imprime un punto por corrida:
   `●` verde si acierta y `○` rojo si falla.
3. Un caso pasa si acierta en la mayoría de las corridas. La tabla de regresión marca cada caso
   como `REGRESIÓN` (v1 pasa y v2 falla), `ARREGLO` (v1 falla y v2 pasa) o `igual`.
4. Muestra el detalle de cada regresión, con la entrada y la respuesta completas de la primera.
5. Calcula el veredicto a partir de los datos con esta regla de promoción: v2 reemplaza a v1 solo si
   arregla al menos un caso y no rompe ninguno.

## Setup

```bash
pip install -r requirements.txt
```

La key se lee de `GEMINI_API_KEY`: ponla en `<repo>/.env` (`GEMINI_API_KEY=...`), que `python-dotenv`
encuentra solo, o expórtala en la terminal:

```bash
export GEMINI_API_KEY=tu_key
```

## Cómo correr

```bash
python3 main.py            # 10 casos × 2 versiones × 3 corridas = 60 llamadas, ~2 min
python3 main.py --runs 1   # versión rápida para la clase: 20 llamadas, ~40 s
```

El cliente reintenta solo los errores 429/5xx con backoff (5 intentos). Si una llamada falla después
de los reintentos, esa corrida cuenta como falla y la suite sigue.

## Qué observar / resultados esperados

La corrida en [`output-1.md`](output-1.md) (gemini-2.5-flash, 3 corridas) muestra:

- **Total empatado**: v1 y v2 pasan **7/10** casos cada una (21/30 llamadas correctas). Solo con
  ese número, v2 parece igual de buena.
- **3 arreglos**: el cobro duplicado (#6) y el cargo no reconocido (#10) pasan de `media` a `alta`, y
  la cuenta hackeada (#9) pasa de `general` a `tecnico`.
- **3 regresiones**: la copia de factura para el contador (#3) sube a `media`, el token de la API
  para un proyecto personal (#4) sube a `alta`, y "dónde cambio mi contraseña" (#8) termina en
  `alta/tecnico`. Las tres son consultas rutinarias que v1 resolvía 3/3 y que v2 ahora mandaría
  como urgentes al equipo técnico.
- **Resultados estables**: ningún caso quedó inestable. Cada caso dio lo mismo en las 3 corridas,
  así que las regresiones vienen del prompt y no de la variabilidad del modelo.
- **Veredicto**: `NO PROMOVER triage_ticket@v2`. v1 sigue en producción y el reporte dice qué
  arreglar antes de proponer una v3: acotar la regla de palabras clave al contexto y conservar las
  aclaraciones de v1.

Lectura para la clase: el eval no reemplaza el criterio, pero hace que cada cambio al prompt tenga
un diff, un reporte y una decisión reversible, igual que un cambio de código.

## Métricas

| Métrica | Qué mide |
|---|---|
| Casos que pasan | Casos cuya clasificación (urgencia **y** categoría) coincide con la esperada en la mayoría de las corridas |
| Llamadas correctas | Aciertos sobre el total de llamadas (casos × corridas) |
| Casos inestables | Casos que aciertan en algunas corridas y fallan en otras |
| Latencia media por llamada | Tiempo medio de una llamada al modelo, incluidos los reintentos |
| Arreglos | Casos que pasan de FALLA en v1 a PASA en v2 |
| Regresiones | Casos que pasan de PASA en v1 a FALLA en v2 (bloquean la promoción) |
