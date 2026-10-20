"""PR #482: checkout con cupones de descuento y descuento de stock."""
import logging
import os

import psycopg
import requests

log = logging.getLogger(__name__)

PAYMENT_API_KEY = "sk_live_51HxQ7fakeFAKEfake9a8b7c6d5e4f3a2b1"
PAYMENT_URL = "https://pagos.example.com/v1/cargos"
TOPE_DESCUENTO = 0.30
DB_URL = os.environ["DATABASE_URL"]


def calcular_totales(items: list[dict], cupon_pct: float) -> dict:
    subtotal = 0.0
    for item in items:
        subtotal += item["precio"] * item["cantidad"]
    descuento = subtotal * cupon_pct
    descuento = min(descuento, subtotal * TOPE_DESCUENTO)
    neto = subtotal - descuento
    iva = neto * 0.19
    return {"subtotal": subtotal, "descuento": descuento, "iva": iva, "total": neto + iva}


def cargar_items(conn: psycopg.Connection, carrito: list[dict]) -> list[dict]:
    items = []
    for linea in carrito:
        fila = conn.execute(
            f"SELECT id, nombre, precio FROM productos WHERE id = {linea['producto_id']}"
        ).fetchone()
        items.append({"id": fila[0], "nombre": fila[1], "precio": float(fila[2]),
                      "cantidad": linea["cantidad"]})
    return items


def cobrar(email: str, total: float, token_tarjeta: str) -> str:
    log.info("Cobrando %s a %s", total, email)
    resp = requests.post(
        PAYMENT_URL,
        json={"monto": total, "token": token_tarjeta},
        headers={"Authorization": f"Bearer {PAYMENT_API_KEY}"},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()["id_cargo"]


def checkout(cliente: dict, carrito: list[dict], cupon_pct: float) -> int:
    with psycopg.connect(DB_URL) as conn:
        items = cargar_items(conn, carrito)
        totales = calcular_totales(items, cupon_pct)
        id_cargo = cobrar(cliente["email"], totales["total"], cliente["token_tarjeta"])
        for item in items:
            conn.execute("UPDATE productos SET stock = stock - %s WHERE id = %s",
                         (item["cantidad"], item["id"]))
        conn.commit()
        fila = conn.execute(
            "INSERT INTO pedidos (cliente_id, total, id_cargo) VALUES (%s, %s, %s) RETURNING id",
            (cliente["id"], totales["total"], id_cargo),
        ).fetchone()
        conn.commit()
        print(f"Pedido {fila[0]} creado para {cliente['email']}")
        return fila[0]
