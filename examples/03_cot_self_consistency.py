#!/usr/bin/env python3
"""Técnica 3: Chain of Thought (CoT) y self-consistency.

Tres preguntas de razonamiento multi-paso, cada una de dos formas:
  - Directo: "responde solo el número".
  - Zero-shot CoT: "piensa paso a paso y termina con 'Respuesta: N'".
Luego self-consistency: 5 corridas CoT y votación por mayoría.
Qué observar: CoT mejora en problemas multi-paso; la votación reduce el ruido
estocástico a costa de 5x tokens y latencia.
"""
import re
from collections import Counter

from llm import ask

QUESTIONS = [
    ("Un tren sale a las 14:35 y viaja 2 horas 50 minutos. ¿A qué hora llega? "
     "Responde en formato HHMM sin dos puntos.", "1725"),
    ("Tengo 3 cajas con 12 manzanas cada una. Regalo 7 y compro 2 cajas más de 12. "
     "¿Cuántas manzanas tengo?", "53"),
    ("Si 5 máquinas hacen 5 piezas en 5 minutos, ¿cuántos minutos tardan 100 máquinas "
     "en hacer 100 piezas?", "5"),
]
N_VOTES = 5


def final_number(text: str) -> str:
    m = re.search(r"Respuesta:\s*([\d]+)", text)
    return m.group(1) if m else (re.findall(r"\d+", text) or ["?"])[-1]


def main() -> None:
    for q, expected in QUESTIONS:
        print(f"\nPregunta: {q}\n  esperado: {expected}")
        direct = ask(f"{q}\nResponde SOLO con el número, nada más.")
        print(f"  directo  : {final_number(direct)}")
        cot = ask(f"{q}\nPiensa paso a paso y termina con la línea 'Respuesta: <número>'.")
        print(f"  CoT      : {final_number(cot)}")
        votes = Counter(final_number(ask(
            f"{q}\nPiensa paso a paso y termina con la línea 'Respuesta: <número>'."))
            for _ in range(N_VOTES))
        winner, count = votes.most_common(1)[0]
        print(f"  self-consistency ({N_VOTES}): {dict(votes)} -> {winner} ({count}/{N_VOTES})")


if __name__ == "__main__":
    main()
