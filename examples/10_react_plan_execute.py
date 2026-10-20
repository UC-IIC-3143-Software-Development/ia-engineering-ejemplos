#!/usr/bin/env python3
"""Agentes 2: ReAct + Plan-and-Execute (híbrido, como Claude Code).

  - Planner  : genera la lista de subtareas en JSON (ask_json).
  - Executor : cada subtarea se resuelve estilo ReAct, imprimiendo
               Thought / Action / Observation.
  - Replanner: si una subtarea falla, pide un plan nuevo con el error como contexto.
Tarea: resumir 3 textos y consolidar. Qué observar: el razonamiento escrito
hace visibles los errores temprano y el plan da estructura global.
"""
from pydantic import BaseModel

from llm import ask, ask_json

TEXTS = {
    "t1": "El equipo migró la base de datos a Postgres 16 con una réplica de lectura.",
    "t2": "Se agregó PgBouncer para agrupar conexiones y bajar la latencia p99 un 30%.",
    "t3": "El rate limiting por IP se movió del backend al gateway.",
}
GOAL = f"Resume cada texto en una frase y luego consolida en un párrafo. Textos: {list(TEXTS)}"


class Plan(BaseModel):
    subtareas: list[str]


class Step(BaseModel):
    thought: str
    action: str  # "resumir:<id>" | "consolidar" | "terminar"


def plan(context: str = "") -> list[str]:
    p = ask_json(f"Objetivo: {GOAL}\n{context}\nDivide en 3-4 subtareas cortas y concretas.", Plan)
    return p.subtareas


def execute(subtask: str, memory: dict[str, str]) -> str:
    step = ask_json(f"Subtarea: {subtask}\nTextos disponibles: {list(TEXTS)}\n"
                    f"Resúmenes ya hechos: {memory}\nDecide la acción: 'resumir:<t1|t2|t3>' "
                    "(lee y resume ese texto), 'consolidar' (une los resúmenes) o 'terminar'.", Step)
    print(f"  Thought: {step.thought}\n  Action : {step.action}")
    if step.action.startswith("resumir:"):
        key = step.action.split(":", 1)[1].strip()
        if key not in TEXTS:
            raise KeyError(f"texto desconocido {key!r}")
        memory[key] = ask(f"Resume en una frase: {TEXTS[key]}")
        obs = memory[key]
    elif step.action == "consolidar":
        obs = memory["final"] = ask(f"Consolida en un párrafo: {list(memory.values())}")
    else:
        obs = "nada que hacer"
    print(f"  Observation: {obs[:120]}")
    return obs


def main() -> None:
    memory: dict[str, str] = {}
    subtasks = plan()
    print("Plan:", *[f"\n  {i + 1}. {s}" for i, s in enumerate(subtasks)])
    for attempt in range(2):
        try:
            for s in subtasks:
                print(f"\n> {s}")
                execute(s, memory)
            break
        except KeyError as e:
            print(f"\n!! Falló: {e}. Replanificando...")
            subtasks = plan(f"El intento anterior falló con: {e}")
    print("\n=== Resultado ===\n" + memory.get("final", "(sin consolidado)"))


if __name__ == "__main__":
    main()
