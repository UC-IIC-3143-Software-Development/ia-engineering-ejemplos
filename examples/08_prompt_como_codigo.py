#!/usr/bin/env python3
"""Técnica 5: el prompt es código.

Mini prompt registry: prompts versionados con template (`str.format`), sin
hardcodear en el call site. Un mini eval corre los mismos 3 casos contra v1 y
v2 y reporta aciertos, para detectar regresiones y decidir qué versión va a
producción.
Qué observar: v1 es vago ("clasifica"); v2 especifica tarea, restricción y
salida (enum explícito, solo una palabra). El eval lo hace medible.
"""
from typing import Literal

from pydantic import BaseModel

from llm import ask_json

REGISTRY: dict[str, str] = {
    "clasificar_ticket@v1": "Clasifica este mensaje: {texto}",
    "clasificar_ticket@v2": (
        "Tarea: clasificar un mensaje de cliente en UNA categoría.\n"
        "Categorías: facturacion (cobros, pagos), soporte_tecnico (errores, fallas), "
        "ventas (precios, planes, compras).\n"
        "Si no calza claramente en ninguna, usa 'otro'.\n\nMensaje: {texto}"),
}

CASES = [
    ("La app se cierra sola cuando abro el mapa.", "soporte_tecnico"),
    ("¿Tienen plan anual con descuento para empresas?", "ventas"),
    ("Necesito la factura de julio para rendir gastos.", "facturacion"),
]


class Label(BaseModel):
    categoria: Literal["facturacion", "soporte_tecnico", "ventas", "otro"]


def evaluate(version: str) -> int:
    template = REGISTRY[version]
    hits = 0
    for texto, expected in CASES:
        got = ask_json(template.format(texto=texto), Label).categoria
        ok = got == expected
        hits += ok
        print(f"  [{'ok' if ok else 'X '}] {texto[:45]!r:50} -> {got}")
    return hits


def main() -> None:
    for version in REGISTRY:
        print(f"=== {version} ===")
        hits = evaluate(version)
        print(f"  aciertos: {hits}/{len(CASES)}\n")


if __name__ == "__main__":
    main()
