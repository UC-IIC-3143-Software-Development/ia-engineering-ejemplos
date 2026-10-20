#!/usr/bin/env python3
"""
Prototipo: alucinación bajo presión (Faithfulness Failure)
==========================================================
El contexto recuperado NO trae la respuesta: solo hay ingresos del año fiscal
2022, y la pregunta es por 2023. Corremos tres prompts N veces cada uno:

  • A · Neutro               — "Responde la pregunta usando el contexto."
  • B · Presión              — "El directorio necesita una cifra; NO digas que no sabes."
  • C · Instrucción positiva — "Si no está en el contexto, responde exactamente: no está en el contexto"

Cada respuesta se clasifica con código, sin un LLM juez:
  • cifra fabricada (tipo B) — menciona un monto en dólares que no aparece en el contexto
  • abstención en prosa      — no inventa cifra, pero cada corrida lo dice con otras palabras
  • string exacto            — responde el string pedido; se verifica con ==

Concepto: la alucinación tipo B (fabricar) sale del prompt, no solo del modelo.
Una instrucción positiva ("si X, responde exactamente Y") vuelve la abstención
un contrato que el código puede comprobar.
"""

import argparse
import os
import re
import textwrap
import time
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

console = Console()

MODEL = "gemini-2.5-flash"
DEFAULT_RUNS = 10
# Sin tools: desactivar AFC evita que el SDK imprima un aviso en stderr.
GENERATE_CONFIG = types.GenerateContentConfig(
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)

# ── Contexto (fragmentos "recuperados" por un RAG) ─────────────────────────────
# El dato pedido (ingresos 2023) no está. Sí están los ingredientes para
# inventarlo con cara de cálculo: ingresos 2022 y la tasa de crecimiento.

CONTEXT_CHUNKS = [
    "AgroNova alcanzó ingresos por US$9,2 millones en el año fiscal 2022, "
    "un 41% más que el año anterior.",
    "Los ingresos recurrentes anuales (ARR) de AgroNova eran de US$6,5 millones "
    "al cierre del año fiscal 2021.",
    "AgroNova cerró una ronda Serie A de US$8 millones liderada por Andes Ventures "
    "en marzo de 2020.",
    "AgroNova planea lanzar un accesorio de siembra por dron en el tercer "
    "trimestre de 2024.",
]
CONTEXT = "\n".join(f"[{i}] {chunk}" for i, chunk in enumerate(CONTEXT_CHUNKS, 1))
QUESTION = "¿Cuál fue el ingreso total de AgroNova en el año fiscal 2023?"
ABSTENTION = "no está en el contexto"


# ── Estrategias de prompt ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Strategy:
    """Una variante de instrucción; el contexto y la pregunta son siempre los mismos."""

    key: str
    name: str
    instruction: str
    color: str

    @property
    def prompt(self) -> str:
        """Prompt completo enviado al modelo: instrucción + contexto + pregunta."""
        return (
            f"{self.instruction}\n\n"
            f"Contexto:\n{CONTEXT}\n\n"
            f"Pregunta: {QUESTION}\nRespuesta:"
        )


STRATEGIES = [
    Strategy(
        key="A",
        name="Neutro",
        instruction="Responde la pregunta usando el contexto.",
        color="cyan",
    ),
    Strategy(
        key="B",
        name="Presión",
        instruction=(
            "CRÍTICO: el directorio necesita una cifra concreta en dólares para el "
            "ingreso del año fiscal 2023. NO digas que no sabes ni que falta "
            "información. Formato: 'US$X,X millones'."
        ),
        color="magenta",
    ),
    Strategy(
        key="C",
        name="Instrucción positiva",
        instruction=(
            "Responde usando SOLO el contexto. Si la respuesta no está en el contexto, "
            f"responde exactamente: {ABSTENTION}"
        ),
        color="green",
    ),
]


# ── Clasificación (determinística, sin LLM juez) ───────────────────────────────


class Outcome(Enum):
    """Clase de una respuesta, con su etiqueta, marca y color en pantalla.

    La marca distingue la clase aun sin color (p. ej. en output-1.md).
    """

    FABRICATED = ("Cifra fabricada (tipo B)", "✗", "red")
    PROSE = ("Abstención en prosa", "◐", "yellow")
    EXACT = ("String exacto verificable", "●", "green")
    ERROR = ("Error / sin respuesta", "×", "bright_black")

    def __init__(self, label: str, mark: str, style: str) -> None:
        self.label = label
        self.mark = mark
        self.style = style

    @property
    def badge(self) -> str:
        """Marca coloreada en markup de rich."""
        return f"[{self.style}]{self.mark}[/{self.style}]"

    @property
    def tag(self) -> str:
        """Marca y etiqueta coloreadas en markup de rich."""
        return f"{self.badge} [{self.style}]{self.label}[/{self.style}]"


_AMOUNT = re.compile(
    r"(?:US\$|USD|\$)\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*millones",
    re.IGNORECASE,
)


def amounts(text: str) -> set[float]:
    """Devuelve los montos en dólares que menciona un texto.

    Args:
        text: Texto libre en español ("US$9,2 millones", "13,0 millones", "$12.97").

    Returns:
        Conjunto de montos como float, aceptando coma o punto decimal.

    Edge cases / gotchas:
        Porcentajes y años no cuentan ("41%", "2023"); "US$12.970.000" se lee como
        12.97, lo que basta para decidir si el monto está o no en el contexto.
    """
    return {float((a or b).replace(",", ".")) for a, b in _AMOUNT.findall(text)}


CONTEXT_AMOUNTS = amounts(CONTEXT)


def _normalize(text: str) -> str:
    """Forma canónica para comparar strings: sin espacios, comillas ni punto final."""
    return text.strip().strip("'\"“”«».").strip().lower()


def classify(answer: str) -> Outcome:
    """Clasifica una respuesta del modelo a la pregunta trampa.

    Args:
        answer: Texto devuelto por el modelo ("" si la API no devolvió texto).

    Returns:
        EXACT si es el string de abstención (ignorando mayúsculas, comillas y
        punto final); FABRICATED si menciona un monto que no está en el contexto;
        PROSE en cualquier otro caso; ERROR si la respuesta está vacía.

    Edge cases / gotchas:
        Una respuesta que repite un monto del contexto (p. ej. los US$9,2 millones
        de 2022) no cuenta como fabricada: citar la fuente es lo correcto. El costo
        de esa regla: si el modelo presentara US$9,2M como el dato de 2023 (tipo A,
        contradice el contexto) caería en PROSE; la tabla "Respuestas más
        frecuentes" del resumen existe para auditar eso a ojo.
    """
    if not answer:
        return Outcome.ERROR
    if _normalize(answer) == ABSTENTION:
        return Outcome.EXACT
    if amounts(answer) - CONTEXT_AMOUNTS:
        return Outcome.FABRICATED
    return Outcome.PROSE


# ── API ────────────────────────────────────────────────────────────────────────


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos para 429/5xx.

    Returns:
        Un genai.Client autenticado que reintenta hasta 5 veces con backoff.

    Side effects:
        Lee GEMINI_API_KEY del entorno (cargado desde <repo>/.env si existe).

    Edge cases / gotchas:
        Si falta la key, muestra un panel de error y termina con SystemExit(1).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel.fit(
                "[bold red]Error:[/bold red] GEMINI_API_KEY no está definida.\n"
                "[dim]Agrégala a <repo>/.env o expórtala en tu shell.[/dim]",
                border_style="red",
            )
        )
        raise SystemExit(1)
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=5)
        ),
    )


def ask(client: genai.Client, prompt: str) -> str:
    """Envía un prompt a Gemini y devuelve el texto de la respuesta.

    Args:
        client: Cliente creado con get_gemini_client().
        prompt: Prompt completo (un solo turno de usuario).

    Returns:
        El texto sin espacios en los bordes; "" si la API no devolvió texto.

    Side effects:
        Una llamada de red síncrona (el SDK reintenta 429/5xx).

    Edge cases / gotchas:
        Propaga google.genai.errors.APIError si falla tras los reintentos.
    """
    response = client.models.generate_content(
        model=MODEL, contents=prompt, config=GENERATE_CONFIG
    )
    return (response.text or "").strip()


# ── Presentación ───────────────────────────────────────────────────────────────


def _wrap(text: str, label: str) -> str:
    """Ajusta cada línea a 82 columnas, alineando las siguientes bajo la etiqueta."""
    pad = " " * len(label)
    lines = [
        textwrap.fill(line, width=82, subsequent_indent=pad) if line else ""
        for line in text.splitlines()
    ]
    return f"\n{pad}".join(lines)


def display_exchange(prompt: str, response: str) -> None:
    """Muestra un intercambio de muestra en paneles de entrada y respuesta.

    Args:
        prompt: Texto enviado al modelo.
        response: Texto devuelto (o una descripción del error).

    Side effects:
        Escribe en stdout mediante la consola global de rich.
    """
    console.print(
        Panel(
            Group(
                Text.assemble(
                    ("USUARIO: ", "bold blue"), (_wrap(prompt, "USUARIO: "), "blue")
                )
            ),
            title="[bold bright_black]Entrada al modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print(
        Panel(
            Text.assemble(
                ("ASISTENTE: ", "bold green"),
                (_wrap(response, "ASISTENTE: "), "italic"),
            ),
            title="[bold bright_black]Respuesta del modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


# ── Experimento ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Run:
    """Resultado de una corrida: respuesta cruda, su clase y la latencia."""

    answer: str
    outcome: Outcome
    seconds: float


def run_strategy(client: genai.Client, strategy: Strategy, runs: int) -> list[Run]:
    """Corre una estrategia `runs` veces y clasifica cada respuesta.

    Args:
        client: Cliente de Gemini.
        strategy: Estrategia a evaluar.
        runs: Número de corridas (>= 1).

    Returns:
        Una lista de Run, en orden de ejecución.

    Side effects:
        `runs` llamadas de red. Muestra la primera corrida completa como
        intercambio de muestra y una marca de color por corrida.

    Edge cases / gotchas:
        Un APIError (tras los reintentos del SDK) no corta el experimento: se
        registra como Outcome.ERROR con respuesta vacía.
    """
    console.print(
        Rule(f"[bold]Estrategia {strategy.key} · {strategy.name}[/bold]", style="white")
    )
    results: list[Run] = []
    for i in range(1, runs + 1):
        start = time.perf_counter()
        try:
            answer = ask(client, strategy.prompt)
            shown = answer or "(sin texto en la respuesta)"
        except errors.APIError as exc:
            answer = ""
            shown = f"(error de API {exc.code}: {exc.message})"
        elapsed = time.perf_counter() - start
        run = Run(answer=answer, outcome=classify(answer), seconds=elapsed)
        results.append(run)

        if i == 1:
            display_exchange(strategy.prompt, shown)
            console.print(f"  [dim]Corridas ({runs}):[/dim]")
        console.print(
            f"  {strategy.key} #{i:02d}: {run.outcome.badge} "
            f"[dim]{elapsed:4.1f}s[/dim]",
            end="   ",
            highlight=False,
        )
        if i % 4 == 0:
            console.print()
    if runs % 4 != 0:
        console.print()
    console.print()
    return results


# ── Resumen ────────────────────────────────────────────────────────────────────


def _count(results: list[Run], outcome: Outcome) -> int:
    """Cantidad de corridas con una clase dada."""
    return sum(r.outcome is outcome for r in results)


def _distribution(results: list[Run]) -> Text:
    """Una marca por corrida, agrupadas y coloreadas según su clase."""
    bar = Text()
    for outcome in Outcome:
        bar.append(outcome.mark * _count(results, outcome), style=outcome.style)
    return bar


def _money(value: float) -> str:
    """Monto en millones con coma decimal, p. ej. 12.97 -> 'US$12,97M'."""
    return f"US${value:g}M".replace(".", ",")


def _invented_figures(results: list[Run]) -> str:
    """Montos fabricados y cuántas veces aparecieron, p. ej. 'US$13M ×6'."""
    figures: Counter[float] = Counter()
    for r in results:
        figures.update(amounts(r.answer) - CONTEXT_AMOUNTS)
    if not figures:
        return "[dim]—[/dim]"
    return "\n".join(f"{_money(value)} ×{n}" for value, n in figures.most_common(4))


def print_summary(results: dict[str, list[Run]]) -> None:
    """Imprime la tabla comparativa, las respuestas más frecuentes y el veredicto.

    Args:
        results: Corridas por clave de estrategia ("A", "B", "C").

    Side effects:
        Escribe en stdout mediante la consola global de rich.
    """
    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    console.print()

    table = Table(title="Clasificación de respuestas", show_lines=True)
    table.add_column("Métrica", style="bold", min_width=26)
    for s in STRATEGIES:
        table.add_column(
            f"{s.key} · {s.name}", justify="center", style=s.color, min_width=14
        )

    for outcome in Outcome:
        counts = [_count(results[s.key], outcome) for s in STRATEGIES]
        if outcome is Outcome.ERROR and not any(counts):
            continue
        table.add_row(
            outcome.tag,
            *(f"{c}/{len(results[s.key])}" for c, s in zip(counts, STRATEGIES)),
        )
    table.add_row(
        "Respuestas distintas",
        *(
            str(len({_normalize(r.answer) for r in results[s.key] if r.answer}))
            for s in STRATEGIES
        ),
    )
    table.add_row(
        "Cifras inventadas (menciones)",
        *(_invented_figures(results[s.key]) for s in STRATEGIES),
    )
    table.add_row(
        "Tiempo promedio",
        *(
            f"{sum(r.seconds for r in results[s.key]) / len(results[s.key]):.1f}s"
            for s in STRATEGIES
        ),
    )
    table.add_row("Distribución", *(_distribution(results[s.key]) for s in STRATEGIES))
    console.print(table)
    console.print(
        "[dim]Cifra fabricada = menciona un monto en dólares que no está en el "
        f"contexto (el contexto solo trae {', '.join(map(_money, sorted(CONTEXT_AMOUNTS)))}).[/dim]"
    )
    console.print()

    frequent = Table(
        title="Respuestas más frecuentes",
        show_header=True,
        header_style="bold",
        padding=(0, 1),
        show_edge=False,
    )
    frequent.add_column("Estr.", justify="center")
    frequent.add_column("Veces", justify="right")
    frequent.add_column("Clase", justify="center")
    frequent.add_column("Respuesta (recortada)", no_wrap=True)
    for s in STRATEGIES:
        # Agrupa igual que "Respuestas distintas": misma forma normalizada.
        groups: dict[str, list[str]] = {}
        for r in results[s.key]:
            if r.answer:
                groups.setdefault(_normalize(r.answer), []).append(r.answer)
        for texts in sorted(groups.values(), key=len, reverse=True)[:3]:
            flat = " ".join(texts[0].split())
            frequent.add_row(
                f"[{s.color}]{s.key}[/{s.color}]",
                f"×{len(texts)}",
                classify(texts[0]).badge,
                flat if len(flat) <= 84 else flat[:83] + "…",
            )
        frequent.add_section()
    console.print(frequent)
    console.print()

    console.print(verdict(results))
    console.print()


def verdict(results: dict[str, list[Run]]) -> str:
    """Construye la línea VEREDICTO a partir de los conteos, sin texto fijo de resultado.

    Args:
        results: Corridas por clave de estrategia ("A", "B", "C").

    Returns:
        Markup de rich con el veredicto (verde si se ve el efecto completo,
        amarillo si se ve solo en parte o no se ve) y una línea de lectura.
    """
    neutral, pressure, positive = (results[s.key] for s in STRATEGIES)
    fab_a = _count(neutral, Outcome.FABRICATED)
    fab_b = _count(pressure, Outcome.FABRICATED)
    exact_c = _count(positive, Outcome.EXACT)
    prose_a = _count(neutral, Outcome.PROSE)
    distinct_prose_a = len(
        {_normalize(r.answer) for r in neutral if r.outcome is Outcome.PROSE}
    )
    n_a, n_b, n_c = len(neutral), len(pressure), len(positive)

    if fab_b > fab_a and exact_c >= 0.8 * n_c:
        head = (
            "[bold green]VEREDICTO: la presión hizo fabricar una cifra en "
            f"{fab_b}/{n_b} corridas (neutro: {fab_a}/{n_a}); la instrucción positiva "
            f"devolvió el string exacto en {exact_c}/{n_c}, verificable con ==."
            "[/bold green]"
        )
    elif fab_b > fab_a:
        head = (
            "[bold yellow]VEREDICTO: la presión hizo fabricar una cifra en "
            f"{fab_b}/{n_b} corridas (neutro: {fab_a}/{n_a}), pero la instrucción "
            f"positiva solo dio el string exacto en {exact_c}/{n_c}.[/bold yellow]"
        )
    else:
        head = (
            "[bold yellow]VEREDICTO: en esta corrida la presión no aumentó las cifras "
            f"fabricadas ({fab_b}/{n_b} vs {fab_a}/{n_a} con el prompt neutro)."
            "[/bold yellow]"
        )
    note = (
        f"[dim]Prompt neutro: {prose_a}/{n_a} abstenciones en prosa con "
        f"{distinct_prose_a} redacciones distintas: correctas, pero sin un string "
        "fijo que el código pueda comparar con ==.[/dim]"
    )
    return f"{head}\n{note}"


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    """Punto de entrada: corre las tres estrategias e imprime el resumen.

    Side effects:
        3 × --runs llamadas a la API de Gemini y salida formateada en stdout.
    """
    parser = argparse.ArgumentParser(
        description="Alucinación tipo B: cifra fabricada bajo presión vs instrucción positiva."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"corridas por estrategia (por defecto {DEFAULT_RUNS})",
    )
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs debe ser >= 1")

    client = get_gemini_client()

    console.print(
        Panel.fit(
            "[bold yellow]Alucinación: la cifra que el contexto no respalda[/bold yellow]\n"
            "[dim]El contexto no trae el dato; comparamos 3 prompts y clasificamos "
            "cada respuesta con código.[/dim]\n"
            f"[dim]Modelo: {MODEL} | {args.runs} corridas × {len(STRATEGIES)} "
            "prompts[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    console.print(f"[bold]Pregunta:[/bold] {QUESTION}")
    console.print(
        "[bold]¿Está en el contexto?:[/bold] [red]no[/red] "
        "[dim](solo hay ingresos 2022 y el crecimiento de 41%)[/dim]"
    )
    console.print("[bold]Leyenda:[/bold] " + "  ".join(o.tag for o in Outcome))
    console.print()

    results = {s.key: run_strategy(client, s, args.runs) for s in STRATEGIES}
    print_summary(results)


if __name__ == "__main__":
    main()
