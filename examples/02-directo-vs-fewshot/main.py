"""Directo vs few-shot: tres ejemplos "doman" el formato de un post de redes sociales.

Se pide el mismo post N veces con tres prompts:
  A. Directo: sin ejemplos. El modelo decide formato, tono y largo.
  B. Few-shot: el mismo pedido con 3 ejemplos resueltos (in-context learning).
     Ninguna regla de formato se escribe; el modelo la infiere de los ejemplos.
  C. Few-shot + "Responde solo con el post.": cubre el caso que los ejemplos no
     resuelven (qué hacer con el texto de cortesía alrededor del post).
El formato de los ejemplos es: emoji inicial, una sola línea, hashtag final.
"""

from __future__ import annotations

import argparse
import os
import re
import statistics
import textwrap
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

MODEL = "gemini-2.5-flash"
# Temperatura por defecto de Gemini: el efecto debe venir del prompt, no de bajar el muestreo.
TEMPERATURE = 1.0
DEFAULT_RUNS = 10
WRAP_WIDTH = 82
MAX_RESPONSE_LINES = 20
SNIPPET_CHARS = 60
RESPONSES_DIR = Path(__file__).resolve().parent / "respuestas"

TOPIC = "el lanzamiento de nuestra app de finanzas personales"

DIRECT_PROMPT = f"Escribe un post de redes sociales sobre {TOPIC}."

FEW_SHOT_INSTRUCTION = (
    "Escribe un post de redes sociales siguiendo el estilo de los ejemplos."
)
EXAMPLES = """Tema: nuevo horario de la biblioteca
Post: 📚 La biblioteca ahora abre hasta las 22:00. Más horas, más ideas. #EstudiaTarde

Tema: taller de cerámica del sábado
Post: 🏺 Sábado 10:00, manos en el barro. Cupos limitados, inscríbete hoy. #TallerCreativo

Tema: descuento de invierno en la cafetería
Post: ☕ Invierno = 20% off en todo lo caliente. Ven a calentarte. #CafeDeInvierno"""

FEW_SHOT_PROMPT = f"{FEW_SHOT_INSTRUCTION}\n\n{EXAMPLES}\n\nTema: {TOPIC}\nPost:"
ONLY_POST_PROMPT = (
    f"{FEW_SHOT_INSTRUCTION} Responde solo con el post.\n\n{EXAMPLES}\n\n"
    f"Tema: {TOPIC}\nPost:"
)

# (columna de la tabla, archivo en respuestas/, prompt)
STRATEGIES = [
    ("A: Directo", "directo.md", DIRECT_PROMPT),
    ("B: Few-shot", "few-shot.md", FEW_SHOT_PROMPT),
    ("C: Few-shot + solo el post", "few-shot-solo-post.md", ONLY_POST_PROMPT),
]
STRATEGY_COLORS = ["cyan", "magenta", "yellow"]

HASHTAG = re.compile(r"#\w+")
ENDS_WITH_HASHTAG = re.compile(r"#\w+$")

console = Console()


@dataclass(frozen=True)
class Run:
    """Una corrida exitosa del modelo.

    Attributes:
        text: Respuesta sin espacios al inicio ni al final ("" si el modelo no devolvió texto).
        input_tokens: Tokens del prompt según usage_metadata.
        output_tokens: Tokens del texto generado (sin los tokens de "thinking").
        elapsed: Latencia de la llamada en segundos.
    """

    text: str
    input_tokens: int
    output_tokens: int
    elapsed: float


@dataclass(frozen=True)
class Metrics:
    """Métricas de formato y costo de un conjunto de corridas (porcentajes en 0-100)."""

    total: int
    conformity_pct: float
    emoji_pct: float
    one_line_pct: float
    hashtag_pct: float
    avg_length: float
    length_stdev: float
    distinct_formats: int
    top_format_pct: float
    avg_input_tokens: float
    avg_output_tokens: float


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos ante 429/5xx.

    Returns:
        Un genai.Client autenticado que reintenta hasta 5 veces con backoff exponencial.

    Side effects:
        Lee GEMINI_API_KEY del entorno (load_dotenv ya cargó <repo>/.env si existe).

    Edge cases / gotchas:
        Si falta la key imprime un panel de error y termina el proceso con código 1.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel.fit(
                "[bold red]Error:[/bold red] falta GEMINI_API_KEY.\n"
                "[dim]Agrégala a <repo>/.env o expórtala en la terminal.[/dim]",
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


def call_gemini(client: genai.Client, prompt: str) -> Run:
    """Envía un prompt de un solo turno al modelo y mide la llamada.

    Args:
        client: Cliente de get_gemini_client().
        prompt: Texto completo que se envía como mensaje del usuario.

    Returns:
        La corrida con el texto, los tokens de entrada/salida y la latencia.

    Side effects:
        Hace una llamada de red síncrona a la API de Gemini.

    Edge cases / gotchas:
        Lanza google.genai.errors.APIError si la API sigue fallando tras los reintentos.
        Una respuesta vacía o bloqueada se devuelve como texto "" (cuenta como no conforme).
    """
    start = time.perf_counter()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=TEMPERATURE,
            # Sin herramientas: desactivarlo evita un warning del SDK en cada llamada.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )
    elapsed = time.perf_counter() - start
    usage = response.usage_metadata
    return Run(
        text=(response.text or "").strip(),
        input_tokens=(usage.prompt_token_count or 0) if usage else 0,
        output_tokens=(usage.candidates_token_count or 0) if usage else 0,
        elapsed=elapsed,
    )


def starts_with_emoji(text: str) -> bool:
    """Indica si el primer carácter es un emoji.

    Edge cases / gotchas:
        Aproxima "emoji" como símbolo Unicode de categoría So o del plano U+1F000+,
        así que también acepta símbolos como ©. Un post que empieza con "**" o "¡" no cuenta.
    """
    if not text:
        return False
    first = text[0]
    return unicodedata.category(first) == "So" or ord(first) >= 0x1F000


def conforms(text: str) -> bool:
    """Indica si la respuesta completa tiene el formato de los ejemplos.

    Returns:
        True si empieza con emoji, no tiene saltos de línea y termina en un hashtag.
        Cualquier texto alrededor del post (p. ej. "Aquí tienes:") la hace no conforme.
    """
    return (
        starts_with_emoji(text)
        and "\n" not in text
        and bool(ENDS_WITH_HASHTAG.search(text))
    )


def format_signature(text: str) -> tuple[bool, int, int, bool]:
    """Resume la estructura de un post para contar formatos distintos.

    Returns:
        (empieza con emoji, líneas no vacías, cantidad de hashtags, termina en hashtag).
        Dos posts con igual firma tienen la misma forma aunque cambien las palabras.
    """
    return (
        starts_with_emoji(text),
        count_lines(text),
        len(HASHTAG.findall(text)),
        bool(ENDS_WITH_HASHTAG.search(text)),
    )


def count_lines(text: str) -> int:
    """Cuenta las líneas no vacías del texto."""
    return sum(1 for line in text.splitlines() if line.strip())


def wrap_block(text: str, indent: int, max_lines: int | None = None) -> str:
    """Envuelve el texto a WRAP_WIDTH columnas respetando sus saltos de línea.

    Args:
        text: Texto a envolver.
        indent: Sangría de las líneas 2..n (el ancho de la etiqueta que precede a la primera).
        max_lines: Si se excede, corta ahí y agrega una línea "… (+N líneas más)".

    Returns:
        Texto listo para ir a continuación de una etiqueta de `indent` caracteres.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        lines.extend(textwrap.wrap(raw, width=WRAP_WIDTH) or [""])
    if max_lines is not None and len(lines) > max_lines:
        hidden = len(lines) - max_lines
        lines = [*lines[:max_lines], f"… (+{hidden} líneas más)"]
    return ("\n" + " " * indent).join(lines)


def show_prompt(prompt: str) -> None:
    """Imprime el panel "Entrada al modelo" con el prompt completo."""
    label = "USUARIO: "
    content = Text.assemble(
        (label, "bold blue"), (wrap_block(prompt, len(label)), "blue")
    )
    console.print(
        Panel(
            content,
            title="[bold bright_black]Entrada al modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )


def show_response(text: str) -> None:
    """Imprime el panel "Respuesta del modelo".

    Edge cases / gotchas:
        Se trunca a MAX_RESPONSE_LINES y envuelve líneas largas, así que un post de
        una línea puede verse en dos; la línea de progreso muestra el conteo real.
    """
    label = "ASISTENTE: "
    body = wrap_block(text, len(label), MAX_RESPONSE_LINES)
    console.print(
        Panel(
            Text.assemble((label, "bold green"), (body, "italic")),
            title="[bold bright_black]Respuesta del modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )


def progress_line(index: int, run: Run) -> str:
    """Arma la línea de progreso de una corrida: conformidad, latencia, líneas y comienzo.

    Returns:
        Markup de rich, p. ej. "Corrida #03: x 10.5s |  3 líneas | Aquí tienes una opción:".
        El comienzo es la primera línea de la respuesta, recortada a SNIPPET_CHARS.
    """
    dot = "[green]o[/green]" if conforms(run.text) else "[red]x[/red]"
    first_line = run.text.splitlines()[0] if run.text else ""
    if len(first_line) > SNIPPET_CHARS:
        first_line = first_line[:SNIPPET_CHARS] + "…"
    n_lines = count_lines(run.text)
    unit = "línea " if n_lines == 1 else "líneas"
    return (
        f"  Corrida #{index:02d}: {dot} [dim]{run.elapsed:4.1f}s | "
        f"{n_lines:2d} {unit} |[/dim] [italic]{escape(first_line)}[/italic]"
    )


def run_experiment(
    client: genai.Client, name: str, prompt: str, iterations: int
) -> list[Run]:
    """Ejecuta el mismo prompt `iterations` veces y devuelve las corridas exitosas.

    Args:
        client: Cliente de get_gemini_client().
        name: Etiqueta de la estrategia para la cabecera.
        prompt: Prompt que se repite sin cambios.
        iterations: Cantidad de llamadas (>= 1).

    Returns:
        Las corridas que la API respondió, en orden. Las que fallaron tras los
        reintentos no se incluyen (se informan en su línea de progreso con "!").

    Side effects:
        Hace `iterations` llamadas de red. Imprime el prompt, la primera respuesta
        como muestra y una línea de progreso por corrida (o = cumple el formato,
        x = no cumple, ! = error de API).
    """
    console.print(
        f"[bold cyan]-- Estrategia {name} --------------------------------------[/bold cyan]"
    )
    console.print(f"[dim]Corriendo {iterations} iteraciones...[/dim]")
    show_prompt(prompt)

    runs: list[Run] = []
    for i in range(1, iterations + 1):
        try:
            run = call_gemini(client, prompt)
        except errors.APIError as exc:
            message = escape(str(exc)[:SNIPPET_CHARS])
            console.print(f"  Corrida #{i:02d}: [red]! error de API: {message}[/red]")
            continue
        if not runs:
            show_response(run.text)
        runs.append(run)
        console.print(progress_line(i, run), highlight=False)
    console.print()
    return runs


def calculate_metrics(runs: list[Run]) -> Metrics:
    """Calcula conformidad, largo, variedad de formatos y tokens de las corridas.

    Args:
        runs: Corridas exitosas; debe tener al menos una.

    Returns:
        Las métricas agregadas (porcentajes en 0-100, largos en caracteres).

    Edge cases / gotchas:
        Lanza ValueError si `runs` está vacía.
    """
    if not runs:
        raise ValueError("calculate_metrics necesita al menos una corrida")
    texts = [run.text for run in runs]
    total = len(texts)
    lengths = [len(text) for text in texts]
    formats = Counter(format_signature(text) for text in texts)

    def pct(flags: list[bool]) -> float:
        return 100 * sum(flags) / total

    return Metrics(
        total=total,
        conformity_pct=pct([conforms(t) for t in texts]),
        emoji_pct=pct([starts_with_emoji(t) for t in texts]),
        one_line_pct=pct(["\n" not in t for t in texts]),
        hashtag_pct=pct([bool(ENDS_WITH_HASHTAG.search(t)) for t in texts]),
        avg_length=statistics.mean(lengths),
        length_stdev=statistics.pstdev(lengths),
        distinct_formats=len(formats),
        top_format_pct=100 * formats.most_common(1)[0][1] / total,
        avg_input_tokens=statistics.mean(run.input_tokens for run in runs),
        avg_output_tokens=statistics.mean(run.output_tokens for run in runs),
    )


def log_responses_to_file(path: Path, prompt: str, runs: list[Run]) -> None:
    """Escribe el prompt y todas las respuestas en un Markdown para revisarlas después.

    Side effects:
        Crea el directorio padre si no existe y sobrescribe `path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# Prompt\n\n```text\n{prompt}\n```\n\n# Respuestas\n"]
    for i, run in enumerate(runs, 1):
        mark = "cumple" if conforms(run.text) else "no cumple"
        parts.append(f"\n## Corrida {i} ({mark})\n\n```text\n{run.text}\n```\n")
    path.write_text("".join(parts), encoding="utf-8")


def build_verdict(direct: Metrics, few_shot: Metrics, only_post: Metrics) -> str:
    """Redacta el veredicto a partir de las métricas de A, B y C.

    Returns:
        Una línea con markup de rich que empieza con "VEREDICTO:" y cita los números.
    """
    a, b, c = direct, few_shot, only_post
    facts = (
        f"conformidad A {a.conformity_pct:.0f}% → B {b.conformity_pct:.0f}% → "
        f"C {c.conformity_pct:.0f}%; formatos distintos {a.distinct_formats} → "
        f"{b.distinct_formats} → {c.distinct_formats}"
    )
    if max(b.conformity_pct, c.conformity_pct) <= a.conformity_pct:
        return f"[bold red]VEREDICTO: los ejemplos no mejoraron la conformidad ({facts}).[/bold red]"
    gain = c.conformity_pct - b.conformity_pct
    if gain > 0:
        tail = f"«Responde solo con el post» sumó {gain:.0f} puntos más"
    elif gain < 0:
        tail = f"«Responde solo con el post» restó {-gain:.0f} puntos"
    else:
        tail = "«Responde solo con el post» no cambió la conformidad"
    return (
        f"[bold green]VEREDICTO: los ejemplos mejoraron la conformidad y {tail}.[/bold green]\n"
        f"[green]{facts}[/green]"
    )


def display_summary(labels: list[str], metrics: list[Metrics]) -> None:
    """Imprime la tabla comparativa de las estrategias y la línea de veredicto.

    Args:
        labels: Nombre de columna de cada estrategia, en el mismo orden que `metrics`.
        metrics: Métricas de A (directo), B (few-shot) y C (few-shot + solo el post).
    """
    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    console.print()
    console.print(
        "[dim]Conformidad = cumple las 3 reglas implícitas en los ejemplos: "
        "emoji inicial, una sola línea, hashtag final.\n"
        "Formato = firma (emoji inicial, nº de líneas, nº de hashtags, hashtag final).[/dim]"
    )
    console.print()

    table = Table(title="Directo vs Few-shot", show_lines=True)
    table.add_column("Métrica", style="bold", min_width=28)
    for label, color in zip(labels, STRATEGY_COLORS):
        table.add_column(label, justify="center", style=color)

    rows: list[tuple[str, str, list[float]]] = [
        ("Conformidad (3 reglas)", "%", [m.conformity_pct for m in metrics]),
        ("  · emoji inicial", "%", [m.emoji_pct for m in metrics]),
        ("  · una sola línea", "%", [m.one_line_pct for m in metrics]),
        ("  · hashtag final", "%", [m.hashtag_pct for m in metrics]),
        ("Largo promedio (caracteres)", "", [m.avg_length for m in metrics]),
        ("Desv. estándar del largo", "", [m.length_stdev for m in metrics]),
        ("Formatos distintos", "", [m.distinct_formats for m in metrics]),
        ("Formato más frecuente", "%", [m.top_format_pct for m in metrics]),
        ("Tokens de entrada (prom.)", "", [m.avg_input_tokens for m in metrics]),
        ("Tokens de salida (prom.)", "", [m.avg_output_tokens for m in metrics]),
    ]
    for label, suffix, values in rows:
        table.add_row(label, *(f"{value:.0f}{suffix}" for value in values))

    console.print(table)
    console.print()
    console.print(build_verdict(*metrics))
    console.print()


def parse_args() -> argparse.Namespace:
    """Lee --runs (corridas por estrategia, >= 1)."""
    parser = argparse.ArgumentParser(
        description="Directo vs few-shot: conformidad de formato en N corridas."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"corridas por estrategia (default: {DEFAULT_RUNS})",
    )
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs debe ser >= 1")
    return args


def main() -> None:
    """Corre las tres estrategias, guarda las respuestas en respuestas/ e imprime la comparación.

    Side effects:
        3 x --runs llamadas de red a Gemini; escribe respuestas/*.md; termina con
        código 1 si falta la key o si una estrategia no obtuvo ninguna respuesta.
    """
    args = parse_args()
    client = get_gemini_client()

    console.print(
        Panel.fit(
            "[bold yellow]Directo vs Few-shot: domar el formato con ejemplos[/bold yellow]\n"
            "[dim]Mismo post pedido sin ejemplos, con 3 ejemplos y con 3 ejemplos + "
            "«Responde solo con el post».[/dim]\n"
            f"[dim]Modelo: {MODEL} | {args.runs} corridas por estrategia[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    metrics: list[Metrics] = []
    for label, filename, prompt in STRATEGIES:
        runs = run_experiment(client, label, prompt, args.runs)
        if not runs:
            console.print(
                f"[bold red]{label}: ninguna corrida respondió; no hay qué comparar.[/bold red]"
            )
            raise SystemExit(1)
        log_responses_to_file(RESPONSES_DIR / filename, prompt, runs)
        metrics.append(calculate_metrics(runs))

    display_summary([label for label, _, _ in STRATEGIES], metrics)
    console.print(
        "[dim]Respuestas completas en respuestas/ (directo.md, few-shot.md, "
        "few-shot-solo-post.md)[/dim]"
    )


if __name__ == "__main__":
    main()
