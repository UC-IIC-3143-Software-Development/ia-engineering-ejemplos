# SPECS — Mini e-commerce (prototipo guiado por spec)

Este archivo es el **contrato** que guía al agente (Claude Code). Cada versión es
incremental: vN debe seguir cumpliendo todos los criterios de v(N-1).
Regla de oro: si un criterio no se puede verificar con un comando, no es criterio.

## Restricciones globales

- Stack: FastAPI + psycopg3 (API), React + Vite (web), PostgreSQL 16, Docker Compose v2.
- Código pequeño: `api/main.py` (< 200 líneas) + `api/db.py`; web en `App.jsx`,
  `main.jsx`, `index.html`, `package.json`, `vite.config.js`.
- Puertos en el host: web 5173, api 8000, pgbouncer 6432, primaria 5432, réplica 5433.
- Sin dependencias fuera de `api/requirements.txt` y `web/package.json`.
- Todo se levanta con `docker compose up --build` desde `ecommerce/`.
- Nombres en inglés, comentarios en español, breves.

---

## v1 — Catálogo + carrito + crear pedido

### Alcance
- Esquema en `db/init/01_schema.sql` (lo ejecuta la imagen oficial al inicializar):
  - `products(id, name, price_cents, stock)` sembrada con **6 productos**.
  - `orders(id, total_cents, created_at)`.
  - `order_items(order_id, product_id, qty, unit_price_cents)`.
- API REST (`api/main.py`):
  - `GET /health` → `{"status":"ok", ...}`.
  - `GET /products` → lista de productos.
  - `POST /orders` con `{"items":[{"product_id":1,"qty":2}]}` → `201 {"id":..,"total_cents":..}`.
    Todo en **una transacción**: valida stock, lo descuenta, inserta pedido e ítems.
    `404` si un producto no existe, `409` si no hay stock, `422` si el body es inválido.
  - `GET /orders/{id}` → pedido con sus ítems; `404` si no existe.
  - CORS abierto (`*`) para que la web en 5173 pueda llamar a 8000.
- Web (`web/`): lista de productos, botón "Agregar" por producto, total del carrito,
  botón "Comprar" que hace `POST /orders` y muestra el id del pedido creado.
  La URL de la API viene de `VITE_API_URL` (default `http://localhost:8000`).

### Criterios de aceptación (v1)
```bash
curl -s localhost:8000/health                       # {"status":"ok",...}
curl -s localhost:8000/products | jq length         # 6
curl -s -X POST localhost:8000/orders -H 'content-type: application/json' \
  -d '{"items":[{"product_id":1,"qty":2}]}'         # 201 {"id":1,"total_cents":...}
curl -s localhost:8000/orders/1 | jq .items         # 1 ítem con qty 2
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/orders \
  -H 'content-type: application/json' -d '{"items":[{"product_id":999,"qty":1}]}'  # 404
open http://localhost:5173                          # UI: agregar → Comprar → muestra id
```

---

## v2 — Rate limiting por IP

### Alcance
- Middleware en `api/main.py` con **token bucket en memoria por IP cliente**:
  tasa **10 req/s**, **burst 20**. Sin dependencias nuevas (dict + `time.monotonic`).
- Al exceder: `429` con body `{"detail":"rate limited"}` y header `Retry-After`
  (segundos enteros, mínimo 1) calculado a partir del déficit de tokens.
- Aplica a todos los endpoints. El estado se pierde al reiniciar la API (aceptable
  para prototipo; en producción iría en Redis).

### Criterios de aceptación (v2)
```bash
# Las primeras ~20 responden 200, el resto 429 (ráfaga más rápida que 10 req/s)
for i in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/products; done | sort | uniq -c
# Header presente en un 429
for i in $(seq 1 25); do curl -s -o /dev/null localhost:8000/products; done; curl -si localhost:8000/products | grep -i retry-after
sleep 2 && curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/products   # 200 de nuevo
```

---

## v3 — PostgreSQL primaria + réplica (streaming) + PgBouncer

### Alcance
- `db-primary` (`postgres:16`): `wal_level=replica`, `max_wal_senders=10`,
  usuario `replicator` (rol REPLICATION) creado por script en
  `/docker-entrypoint-initdb.d/`, regla `pg_hba` que permite `replication` desde la
  red de compose. Healthcheck con `pg_isready`.
- `db-replica` (`postgres:16`): si el data dir está vacío ejecuta
  `pg_basebackup -h db-primary -U replicator -D $PGDATA -Fp -Xs -R -P` y luego
  arranca en modo standby (hot_standby). `depends_on` de la primaria healthy.
- `pgbouncer` (`edoburu/pgbouncer`): `pgbouncer.ini` + `userlist.txt` montados.
  Bases lógicas: `shop` → `db-primary:5432`, `shop_ro` → `db-replica:5432`.
  `pool_mode = transaction`. Autenticación md5 (postgres inicializado con
  `POSTGRES_HOST_AUTH_METHOD=md5` + `--auth-host=md5` para evitar fricción con SCRAM; el socket local sigue en trust).
- API: dos pools psycopg3. `DATABASE_URL_RW=postgresql://shop:shop@pgbouncer:5432/shop`
  para escrituras y `DATABASE_URL_RO=postgresql://shop:shop@pgbouncer:5432/shop_ro`
  para lecturas de catálogo. Reglas de enrutamiento:
  - `GET /products` → **réplica** (RO).
  - `POST /orders` → **primaria** (RW, transacción).
  - `GET /orders/{id}` → **primaria** (RW): evita que el cliente no vea su propio
    pedido por replication lag (read-your-writes).
  - `GET /health` reporta `pg_is_in_recovery()` de ambos pools:
    `{"primary": {"in_recovery": false}, "replica": {"in_recovery": true}}`.
- Prepared statements desactivados en el cliente (`prepare_threshold=None`) porque
  PgBouncer en modo transaction no garantiza la misma conexión de servidor.

### Criterios de aceptación (v3)
```bash
docker compose exec db-primary psql -U shop -c "select client_addr, state, sync_state from pg_stat_replication"
#  → 1 fila, state = streaming
docker compose exec db-replica psql -U shop -c "select pg_is_in_recovery()"   # t
psql -h localhost -p 6432 -U shop pgbouncer -c "show pools"                    # shop y shop_ro
curl -s localhost:8000/health | jq                                             # replica.in_recovery == true
# La réplica recibe los datos de la primaria:
docker compose exec db-primary psql -U shop -c "insert into products(name,price_cents,stock) values('Replicado',100,1)"
sleep 1; docker compose exec db-replica psql -U shop -c "select name from products where name='Replicado'"
# La réplica es solo lectura:
docker compose exec db-replica psql -U shop -c "insert into products(name,price_cents,stock) values('x',1,1)"
#  → ERROR: cannot execute INSERT in a read-only transaction
```
