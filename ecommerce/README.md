# Mini e-commerce — prototipo guiado por `SPECS.md`

Demo de la clase: cómo un `SPECS.md` con versiones incrementales y criterios
verificables guía a Claude Code para prototipar (ver `PROMPTS.md`).

- **v1** catálogo + carrito + pedidos (React/Vite + FastAPI + PostgreSQL)
- **v2** rate limiting por IP (token bucket, 10 req/s, burst 20, `429` + `Retry-After`)
- **v3** PostgreSQL primaria + réplica (streaming) y PgBouncer (pool transaction)

## Levantar

```bash
cd ecommerce
docker compose up --build        # web :5173, api :8000, pgbouncer :6432, primaria :5432, réplica :5433
```

## Arquitectura (v3)

```
  navegador ──▶ web (Vite preview :5173)
      │
      └── fetch ──▶ api (FastAPI :8000, rate limit por IP en memoria)
                      │  DATABASE_URL_RW  (shop)      DATABASE_URL_RO (shop_ro)
                      ▼                                ▼
                  ┌──────────────── pgbouncer :6432 ────────────────┐
                  │   pool_mode=transaction, auth md5, userlist.txt  │
                  └──────┬───────────────────────────────┬──────────┘
                         │ escrituras + GET /orders/{id} │ GET /products
                         ▼                               ▼
                  db-primary :5432  ══ streaming WAL ══▶ db-replica :5433
                  (wal_level=replica,                   (pg_basebackup -R,
                   rol replicator)                       hot_standby, solo lectura)
```

## Verificar cada versión

**v1 — API y UI**
```bash
curl -s localhost:8000/health
curl -s localhost:8000/products
curl -s -X POST localhost:8000/orders -H 'content-type: application/json' -d '{"items":[{"product_id":1,"qty":2}]}'
curl -s localhost:8000/orders/1
open http://localhost:5173
```

**v2 — Rate limit** (las primeras ~20 dan 200, el resto 429 con `Retry-After`)
```bash
for i in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/products; done | sort | uniq -c
curl -si localhost:8000/products | grep -i retry-after
```

**v3 — Replicación**
```bash
docker compose exec db-primary psql -U shop -c "select client_addr, state, sync_state from pg_stat_replication"
docker compose exec db-replica psql -U shop -c "select pg_is_in_recovery()"    # t
curl -s localhost:8000/health   # {"primary":{"in_recovery":false},"replica":{"in_recovery":true}}
```

**v3 — PgBouncer**
```bash
psql -h localhost -p 6432 -U shop pgbouncer -c "show pools"      # password: shop
psql -h localhost -p 6432 -U shop shop_ro -c "select count(*) from products"
```

## Por qué réplica + PgBouncer (y sus límites)

1. **Las lecturas escalan horizontalmente**: el catálogo (la mayoría del tráfico) se
   sirve desde la réplica; la primaria queda libre para escribir pedidos.
2. **Conexiones baratas**: cada conexión de Postgres es un proceso (~10 MB); PgBouncer
   multiplexa cientos de clientes sobre pocas conexiones reales.
3. **`pool_mode = transaction`** devuelve la conexión al pool al terminar cada transacción,
   así 10 conexiones de servidor atienden a muchos workers de la API.
4. **Límite: replication lag**. La réplica va unos ms (o más, bajo carga) detrás; por eso
   `GET /orders/{id}` lee desde la primaria: el cliente debe ver su propio pedido
   (*read-your-writes*). Regla práctica: lo que acabas de escribir, léelo de la primaria.
5. **Límite: modo transaction** rompe estado por sesión (prepared statements con nombre,
   `SET`, advisory locks, `LISTEN`); el cliente se configura con `prepare_threshold=None`.
