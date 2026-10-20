#!/usr/bin/env python3
"""Técnica 4: salidas estructuradas.

Regla: clasificación única de un set fijo -> enum (Literal); datos con varios
campos -> modelo Pydantic PLANO (el anidamiento profundo confunde al modelo).
El JSON queda validado por Pydantic: si falta un campo o el tipo no calza,
falla aquí y no en el sistema downstream.
Qué observar: el modelo no puede devolver una categoría fuera del enum ni
"Here's the JSON:" que rompa el parser.
"""
from typing import Literal

from pydantic import BaseModel

from llm import ask_json


class Ticket(BaseModel):
    categoria: Literal["facturacion", "soporte_tecnico", "ventas", "otro"]


class Order(BaseModel):
    cliente: str
    items: list[str]
    total: float
    moneda: Literal["CLP", "USD"]


TICKET = "Me cobraron dos veces la suscripción de este mes, necesito que reviertan un cargo."
ORDER = ("Pedido de María Pérez: 2 poleras negras talla M y 1 gorro de lana. "
         "Total a pagar $34.990 pesos chilenos.")


def main() -> None:
    print("=== Enum: clasificación de ticket ===")
    t = ask_json(f"Clasifica este ticket de soporte.\n\n{TICKET}", Ticket)
    print(t.model_dump_json(indent=2))

    print("\n=== Pydantic plano: extracción de pedido ===")
    o = ask_json(f"Extrae los datos del pedido.\n\n{ORDER}", Order)
    print(o.model_dump_json(indent=2))
    print(f"\nvalidado: cliente={o.cliente!r}, {len(o.items)} items, total={o.total} {o.moneda}")


if __name__ == "__main__":
    main()
