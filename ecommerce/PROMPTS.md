# PROMPTS — cómo se prototipa iterativamente con Claude Code

Los tres prompts que se le dan a Claude Code, uno por versión. Todos referencian
`SPECS.md`: el spec es la fuente de verdad; el prompt sólo dice **qué versión**
implementar y **cómo demostrar** que quedó lista. Fíjate en el patrón
*tarea → restricción → salida/verificación* y en que cada prompt cierra con
criterios comprobables (el agente no "termina" hasta demostrarlos).

---

## Prompt 1 — v1 (catálogo + carrito + pedido)

```
Lee ecommerce/SPECS.md. Implementa SOLO la sección "v1" bajo ecommerce/:
docker-compose.yml con un único postgres:16 + api (FastAPI, psycopg3 pool,
Dockerfile python:3.11-slim) + web (React + Vite, Dockerfile node:20-alpine).
Respeta las "Restricciones globales" (tamaño de archivos, puertos, sin deps extra).

Cuando termines: `docker compose up -d --build`, ejecuta cada comando de
"Criterios de aceptación (v1)" y pégame la salida real. Si algo falla,
arréglalo y vuelve a correr; no me reportes éxito sin la salida.
Haz un commit por hito con mensaje en español (feat(ecommerce): ...).
```

---

## Prompt 2 — v2 (rate limiting)

```
Lee ecommerce/SPECS.md, sección "v2". Agrega el rate limit por IP a api/main.py
como middleware token-bucket (10 req/s, burst 20, 429 + Retry-After) sin
dependencias nuevas y sin tocar la web ni el compose.

Los criterios de v1 deben seguir pasando. Verifica con el loop de curl de
"Criterios de aceptación (v2)" y muéstrame el conteo de códigos 200/429 y el
header Retry-After. Commit: feat(ecommerce): v2 rate limit token bucket por IP.
```

---

## Prompt 3 — v3 (primaria + réplica + PgBouncer)

```
Lee ecommerce/SPECS.md, sección "v3". Reemplaza el postgres único por
db-primary + db-replica (streaming replication vía pg_basebackup -R) y
agrega pgbouncer (edoburu/pgbouncer, pool_mode transaction) con las bases
lógicas shop (→ primaria) y shop_ro (→ réplica). La API usa DATABASE_URL_RW
y DATABASE_URL_RO: catálogo desde réplica, pedidos (crear y leer) desde primaria.

Escribe ecommerce/README.md con: cómo levantar, cómo verificar cada versión,
diagrama ASCII de la arquitectura y 5 líneas sobre por qué réplica + PgBouncer
y sus límites (replication lag). Verifica con los comandos de
"Criterios de aceptación (v3)" (pg_stat_replication, show pools, /health)
y pégame la salida real. Commit: feat(ecommerce): v3 réplica + pgbouncer.
```

---

## Qué muestra este flujo

1. **El spec vive fuera del prompt** y se versiona: los prompts son cortos y
   estables; el conocimiento está en `SPECS.md`.
2. **Cada iteración es pequeña y verificable**: el agente entra en un loop
   Observar-Pensar-Actuar contra criterios ejecutables (curl/psql), no contra
   "que se vea bien".
3. **La regresión es explícita**: cada prompt exige que los criterios anteriores
   sigan pasando, así el agente no rompe v1 al construir v3.
