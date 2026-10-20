#!/usr/bin/env python3
"""Técnica 1: los LLMs son estocásticos.

Misma reseña, misma pregunta, 5 veces:
  A) sin restricción  -> el texto varía en forma, largo y a veces en veredicto.
  B) restringida a un enum (positivo/negativo/neutral) -> la salida se concentra.
Qué observar: la restricción no elimina el azar, pero "desplaza la masa de
probabilidad" hacia un conjunto pequeño de respuestas comparables.
"""
from collections import Counter
from typing import Literal

from pydantic import BaseModel

from llm import ask, ask_json

REVIEW = ("El envío tardó dos semanas y la caja llegó golpeada, pero el producto "
          "funciona perfecto y el soporte respondió rápido.")
N = 5


class Sentiment(BaseModel):
    sentimiento: Literal["positivo", "negativo", "neutral"]


def main() -> None:
    print("=== A) Sin restricción ===")
    for i in range(N):
        out = ask(f"¿Cuál es el sentimiento de esta reseña?\n\n{REVIEW}")
        print(f"[{i + 1}] {out[:120].replace(chr(10), ' ')}")

    print("\n=== B) Restringida a enum ===")
    votes: Counter[str] = Counter()
    for i in range(N):
        s = ask_json(f"Clasifica el sentimiento de esta reseña.\n\n{REVIEW}", Sentiment)
        votes[s.sentimiento] += 1
        print(f"[{i + 1}] {s.sentimiento}")
    print(f"\nDistribución: {dict(votes)}")


if __name__ == "__main__":
    main()
