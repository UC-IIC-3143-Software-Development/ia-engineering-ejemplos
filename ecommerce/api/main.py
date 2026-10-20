"""API del mini e-commerce: catálogo, pedidos y health."""

import math
import time
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import db

app = FastAPI(title="shop")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# v2: token bucket por IP en memoria. Se rellena a RATE tokens/s hasta BURST.
RATE, BURST = 10.0, 20.0
_buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, último timestamp)


def _take_token(ip: str) -> float:
    """Consume un token; devuelve 0 si había, o los segundos hasta el próximo."""
    now = time.monotonic()
    tokens, last = _buckets.get(ip, (BURST, now))
    tokens = min(BURST, tokens + (now - last) * RATE)
    if tokens >= 1:
        _buckets[ip] = (tokens - 1, now)
        return 0.0
    _buckets[ip] = (tokens, now)
    return (1 - tokens) / RATE


@app.middleware("http")
async def rate_limit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    ip = request.client.host if request.client else "unknown"
    wait = _take_token(ip)
    if wait > 0:
        return JSONResponse({"detail": "rate limited"}, status_code=429, headers={"Retry-After": str(math.ceil(wait))})
    return await call_next(request)


class Item(BaseModel):
    product_id: int
    qty: int = Field(gt=0)


class NewOrder(BaseModel):
    items: list[Item] = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, Any]:
    """Reporta si cada pool responde y si está en modo réplica (recovery)."""
    out: dict[str, Any] = {"status": "ok"}
    for name, pool in (("primary", db.rw), ("replica", db.ro)):
        with pool.connection() as conn:
            row = conn.execute("select pg_is_in_recovery() as in_recovery").fetchone()
        out[name] = {"in_recovery": bool(row and row["in_recovery"])}
    return out


@app.get("/products")
def list_products() -> list[dict[str, Any]]:
    with db.ro.connection() as conn:
        return conn.execute("select id, name, price_cents, stock from products order by id").fetchall()


@app.post("/orders", status_code=201)
def create_order(order: NewOrder) -> dict[str, Any]:
    """Crea el pedido en una transacción: valida y descuenta stock, inserta ítems."""
    with db.rw.connection() as conn, conn.transaction():
        total = 0
        lines: list[tuple[int, int, int]] = []
        for item in order.items:
            row = conn.execute(
                "select price_cents, stock from products where id = %s for update", (item.product_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(404, f"product {item.product_id} not found")
            if row["stock"] < item.qty:
                raise HTTPException(409, f"insufficient stock for product {item.product_id}")
            conn.execute("update products set stock = stock - %s where id = %s", (item.qty, item.product_id))
            total += row["price_cents"] * item.qty
            lines.append((item.product_id, item.qty, row["price_cents"]))
        order_id = conn.execute(
            "insert into orders (total_cents) values (%s) returning id", (total,)
        ).fetchone()["id"]
        for product_id, qty, price in lines:
            conn.execute(
                "insert into order_items (order_id, product_id, qty, unit_price_cents) values (%s, %s, %s, %s)",
                (order_id, product_id, qty, price),
            )
    return {"id": order_id, "total_cents": total}


@app.get("/orders/{order_id}")
def get_order(order_id: int) -> dict[str, Any]:
    """Lee desde la primaria: el cliente debe ver su propio pedido sin esperar la réplica."""
    with db.rw.connection() as conn:
        order = conn.execute(
            "select id, total_cents, created_at from orders where id = %s", (order_id,)
        ).fetchone()
        if order is None:
            raise HTTPException(404, "order not found")
        items = conn.execute(
            "select product_id, qty, unit_price_cents from order_items where order_id = %s", (order_id,)
        ).fetchall()
    return {**order, "items": items}
