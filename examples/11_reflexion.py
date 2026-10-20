#!/usr/bin/env python3
"""Agentes 3: Reflexion.

Pedimos merge_intervals. Los tests tienen 2 requisitos ocultos que el prompt no
menciona: la entrada puede venir desordenada y los intervalos contiguos
([1,3],[3,5]) deben unirse. Si falla, el agente genera una REFLEXIÓN verbal
("por qué falló mi enfoque") que se guarda en un buffer y se reinyecta en el
siguiente intento. Max 3 intentos. Qué observar: la reflexión cambia el
enfoque, no solo parcha el síntoma ("weight-free learning").
"""
import re

from llm import ask

MAX_TRIES = 3
TESTS = [
    ([[1, 4], [2, 5]], [[1, 5]]),
    ([[5, 8], [1, 3]], [[1, 3], [5, 8]]),          # oculto: desordenado
    ([[1, 3], [3, 5]], [[1, 5]]),                  # oculto: contiguos se unen
    ([[1, 2], [4, 5]], [[1, 2], [4, 5]]),
]
TASK = "Implementa en Python `merge_intervals(intervals: list[list[int]]) -> list[list[int]]`."


def run_tests(code: str) -> str:
    ns: dict = {}
    try:
        exec(code, ns)
        for inp, expected in TESTS:
            got = ns["merge_intervals"]([list(i) for i in inp])
            if got != expected:
                return f"FAIL merge_intervals({inp}) = {got}, esperado {expected}"
        return "OK"
    except Exception as e:  # noqa: BLE001 - el error es la observación
        return f"ERROR {type(e).__name__}: {e}"


def generate(reflections: list[str]) -> str:
    memo = "\n".join(f"- {r}" for r in reflections) or "(ninguna)"
    out = ask(f"{TASK}\nReflexiones de intentos anteriores:\n{memo}\n"
              "Devuelve SOLO la función en un bloque ```python, sin tests.")
    m = re.search(r"```python\n(.*?)```", out, re.DOTALL)
    return m.group(1) if m else out


def reflect(code: str, failure: str) -> str:
    return ask(f"Este código falló:\n```python\n{code}\n```\nFallo: {failure}\n"
               "En 2 frases: ¿por qué falló el ENFOQUE y qué debe cambiar? Sin código.")


def main() -> None:
    reflections: list[str] = []
    for attempt in range(1, MAX_TRIES + 1):
        code = generate(reflections)
        result = run_tests(code)
        print(f"[intento {attempt}] tests: {result}")
        if result == "OK":
            print("Aprobado.\n" + code)
            return
        reflections.append(reflect(code, result))
        print(f"[intento {attempt}] reflexión: {reflections[-1]}")
    print("Se agotaron los intentos.")


if __name__ == "__main__":
    main()
