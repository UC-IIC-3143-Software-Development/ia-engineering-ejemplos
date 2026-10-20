#!/usr/bin/env python3
"""Agentes 1: loop Observar-Pensar-Actuar (OTA).

Entorno observable: una función con bug + tests locales. En cada iteración:
  1. Observar: correr los tests y capturar el error.
  2. Pensar : pedir al LLM un fix dado el código y la observación.
  3. Actuar : reemplazar el código y volver a observar.
Termina cuando los tests pasan o tras MAX_ITER. Qué observar: el agente no
necesita acertar a la primera; el feedback del entorno corrige cada paso.
"""
import re

from llm import ask

MAX_ITER = 5
BUGGY = '''def average(nums):
    """Promedio de una lista; lista vacía -> 0.0."""
    return sum(nums) / len(nums)
'''
TESTS = [([2, 4, 6], 4.0), ([], 0.0), ([5], 5.0)]


def observe(code: str) -> str:
    """Ejecuta el código en un namespace aislado y devuelve 'OK' o el error."""
    ns: dict = {}
    try:
        exec(code, ns)
        for nums, expected in TESTS:
            got = ns["average"](nums)
            if got != expected:
                return f"FAIL average({nums}) = {got}, esperado {expected}"
        return "OK"
    except Exception as e:  # noqa: BLE001 - el error es la observación
        return f"ERROR {type(e).__name__}: {e}"


def think(code: str, observation: str) -> str:
    out = ask(f"Este código falla sus tests.\n\n```python\n{code}\n```\n\nObservación: "
              f"{observation}\n\nDevuelve SOLO la función corregida en un bloque ```python.")
    m = re.search(r"```python\n(.*?)```", out, re.DOTALL)
    return m.group(1) if m else out


def main() -> None:
    code = BUGGY
    for i in range(1, MAX_ITER + 1):
        obs = observe(code)
        print(f"[iter {i}] Observar: {obs}")
        if obs == "OK":
            print("Tests en verde. Código final:\n" + code)
            return
        code = think(code, obs)
        print(f"[iter {i}] Actuar: nuevo código de {len(code.splitlines())} líneas")
    print("Se agotaron las iteraciones sin pasar los tests.")


if __name__ == "__main__":
    main()
