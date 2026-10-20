# Ralph loop

Patrón de orquestación a nivel de shell: `while :; do cat spec.md | claude -p; done`
con un criterio de término (`grep COMPLETE`) y un máximo de iteraciones.

- **Loop externo (Ralph)**: reinicia el contexto en cada iteración.
- **Loop interno (OTA)**: dentro de cada `claude -p`, el agente observa, piensa y actúa.
- **Fuente de verdad**: el file system + `git log`. La salida de la iteración *n*
  (archivos, commits) es el input de la *n+1*, sin arrastrar un contexto gigante.

## Correr

```bash
cd examples/ralph
python3 -m pip install pytest pytest-cov   # si no están
MAX_ITER=5 ./ralph.sh
```

`spec.md` pide tests para `src/parser.py` (que no debe modificarse) y que el agente
imprima `COMPLETE` cuando se cumplan los criterios. Revisa `git log` y
`tests/test_parser.py` al terminar para ver qué hizo cada iteración.

Cuándo sirve: tareas largas y verificables (coding, síntesis). Cuándo no: chat o
cualquier cosa donde la latencia de respuesta importe.
