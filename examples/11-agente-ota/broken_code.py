"""Reporte de ventas por mes a partir de ventas.csv (export de la planilla de ventas)."""

import csv
from collections import defaultdict
from datetime import datetime

ARCHIVO = "ventas.csv"


def leer_ventas(ruta):
    ventas = []
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            fecha = datetime.strptime(fila["fecha"], "%Y-%m-%d")
            monto = int(fila["monto"])
            ventas.append((fecha, monto))
    return ventas


def total_por_mes(ventas):
    totales = defaultdict(int)
    for fecha, monto in ventas:
        totales[fecha.strftime("%Y-%m")] += monto
    return totales


def pesos(monto):
    return "$" + f"{monto:,}".replace(",", ".")


if __name__ == "__main__":
    ventas = leer_ventas(ARCHIVO)
    for mes, total in sorted(total_por_mes(ventas).items()):
        print(f"{mes}: {pesos(total)}")
    print(f"Total: {pesos(sum(ventas))}")
