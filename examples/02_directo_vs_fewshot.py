#!/usr/bin/env python3
"""Técnica 2: prompt directo vs few-shot.

Pedimos un post de redes sociales sobre un tema. Sin ejemplos, el modelo elige
formato, tono y largo por su cuenta. Con 3 ejemplos ("in-context learning") la
salida se parece estructuralmente a ellos: emoji inicial, una línea, hashtag final.
Qué observar: los ejemplos "doman" la distribución sin describir reglas.
"""
from llm import ask

TOPIC = "el lanzamiento de nuestra app de finanzas personales"

DIRECT = f"Escribe un post de redes sociales sobre {TOPIC}."

FEW_SHOT = f"""Escribe un post de redes sociales siguiendo el estilo de los ejemplos.

Tema: nuevo horario de la biblioteca
Post: 📚 La biblioteca ahora abre hasta las 22:00. Más horas, más ideas. #EstudiaTarde

Tema: taller de cerámica del sábado
Post: 🏺 Sábado 10:00, manos en el barro. Cupos limitados, inscríbete hoy. #TallerCreativo

Tema: descuento de invierno en la cafetería
Post: ☕ Invierno = 20% off en todo lo caliente. Ven a calentarte. #CafeDeInvierno

Tema: {TOPIC}
Post:"""


def main() -> None:
    print("=== Directo ===")
    print(ask(DIRECT))
    print("\n=== Few-shot (3 ejemplos) ===")
    print(ask(FEW_SHOT))


if __name__ == "__main__":
    main()
