#!/usr/bin/env python3
"""Modo de falla 1: alucinación.

Damos un contexto y preguntamos algo que NO está en él. Sin instrucción, el
modelo rellena con datos plausibles (modelos débiles) o se abstiene en prosa
libre, distinta en cada corrida (modelos actuales): ninguna es verificable por
código. Con la instrucción positiva "si no está en el contexto, di exactamente
'no está en el contexto'", la abstención es un string fijo y comprobable.
Qué observar: la instrucción positiva ("si X, haz Y") funciona mejor que
"no alucines".
"""
from llm import ask

CONTEXT = """Política de devoluciones de TiendaSur:
- Plazo: 30 días desde la compra, con boleta.
- Productos abiertos de electrónica: solo cambio, no reembolso.
- El reembolso se hace al mismo medio de pago en 5 a 10 días hábiles."""

QUESTION = "¿Cuál es el costo de envío para devoluciones desde regiones?"

GUARD = ("Responde usando SOLO el contexto. Si la respuesta no está en el contexto, "
         "responde exactamente: 'no está en el contexto'.")


def main() -> None:
    base = f"Contexto:\n{CONTEXT}\n\nPregunta: {QUESTION}"
    print("=== Sin instrucción ===")
    print(ask(base))
    print("\n=== Con instrucción de abstención ===")
    print(ask(f"{GUARD}\n\n{base}"))


if __name__ == "__main__":
    main()
