"""
Prototipo: Chain of Thought vs. Directo (y self-consistency)
============================================================
Demuestra que pedir "piensa paso a paso" es una palanca de exactitud, no un
detalle de estilo, y que votar entre varias corridas (self-consistency) corrige
errores esporádicos pero no los sistemáticos.

Cinco tareas algorítmicas (no se pueden responder de memoria) se preguntan con
tres estrategias, N veces cada una:
  - Directo        -- "responde solo con la respuesta final".
  - Zero-shot CoT  -- "piensa paso a paso" y termina con 'Respuesta: <valor>'.
  - Few-shot CoT   -- tres ejemplos resueltos paso a paso antes de la pregunta.

Se mide exactitud por corrida, tokens de entrada/salida (usage_metadata) y
latencia. Self-consistency se calcula votando por mayoría sobre las N corridas
ya hechas de cada estrategia (sin llamadas extra).

El razonamiento interno de gemini-2.5-flash (thinking) se desactiva para aislar
el efecto del prompt: con thinking activo el modelo ya razona "por dentro"
incluso ante un prompt directo.
"""

from __future__ import annotations

import argparse
import os
import re
import textwrap
import time
import unicodedata
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

console = Console()

MODEL = "gemini-2.5-flash"
# 0 = sin razonamiento interno: la única cadena de pensamiento es la que pide el
# prompt. None = thinking dinámico (default del modelo): el directo también acierta,
# pero paga tokens de "thinking" que no se ven en la respuesta.
THINKING_BUDGET: int | None = 0
DEFAULT_RUNS = 8
MAX_WORKERS = 8  # llamadas concurrentes; los 429 los reintenta el SDK con backoff


# ── Preguntas ──────────────────────────────────────────────────────────────────
# Tareas algorítmicas con respuesta única y verificable. Las respuestas se
# calcularon con código, no con el modelo.


@dataclass(frozen=True)
class Problem:
    """Pregunta de razonamiento multi-paso con su respuesta verificable.

    Attributes:
        title: Nombre corto para tablas.
        question: Enunciado que recibe el modelo.
        valid_answers: Grafías aceptadas de la respuesta, ya normalizadas
            (minúsculas, sin tildes ni espacios). La primera es la canónica.
        explanation: Solución paso a paso, para mostrar en pantalla.
    """

    title: str
    question: str
    valid_answers: tuple[str, ...]
    explanation: str


PROBLEMS: tuple[Problem, ...] = (
    Problem(
        title="Última letra (9 palabras)",
        question=(
            "Toma la última letra de cada una de estas palabras y concaténalas en "
            "orden, sin espacios: volcán, reloj, nariz, pared, camión, tenedor, "
            "ciudad, arroz, fénix."
        ),
        valid_answers=("njzdnrdzx",),
        explanation=(
            "volcán→n, reloj→j, nariz→z, pared→d, camión→n, tenedor→r, ciudad→d, "
            "arroz→z, fénix→x."
        ),
    ),
    Problem(
        title="Contar letras",
        question=(
            "¿Cuántas veces aparece la letra 'r' en la frase 'el perro de rosa corre "
            "rápido por la carretera rural hacia el barrio'?"
        ),
        valid_answers=("14",),
        explanation=(
            "perro 2 + rosa 1 + corre 2 + rápido 1 + por 1 + carretera 3 + "
            "rural 2 + barrio 2 = 14."
        ),
    ),
    Problem(
        title="Multiplicación 5×4 cifras",
        question="¿Cuánto es 58374 × 6927?",
        valid_answers=("404356698", "404.356.698", "404,356,698"),
        explanation=(
            "58374×7 = 408618; ×20 = 1167480; ×900 = 52536600; ×6000 = 350244000; "
            "suma = 404356698."
        ),
    ),
    Problem(
        title="Navegación en grilla",
        question=(
            "Partes en el origen (0, 0) mirando al norte (+Y). Avanza 5. Gira a la "
            "derecha. Avanza 2. Gira a la derecha. Avanza 8. Gira a la izquierda. "
            "Retrocede 4. Gira a la izquierda. Avanza 3. Gira a la derecha. Avanza 1. "
            "¿Cuáles son tus coordenadas finales? Formato (X, Y)."
        ),
        valid_answers=("-1,0",),
        explanation=(
            "N (0,5) → E (2,5) → S (2,-3) → E, retroceder 4 es ir al oeste (-2,-3) "
            "→ N (-2,0) → E (-1,0)."
        ),
    ),
    Problem(
        title="Horario con pausas",
        question=(
            "Un proceso empieza a las 22:38 y tiene 4 etapas de 47, 125, 33 y 76 "
            "minutos, con una pausa de 8 minutos entre etapas consecutivas. ¿A qué "
            "hora termina? Formato HH:MM."
        ),
        valid_answers=("03:43", "3:43"),
        explanation=(
            "Etapas 47+125+33+76 = 281 min + 3 pausas × 8 = 305 min = 5 h 05 min; "
            "22:38 + 5:05 = 03:43."
        ),
    ),
)

# ── Estrategias de prompt ──────────────────────────────────────────────────────
# Las tres piden la misma línea final 'Respuesta: <valor>', así el parser es el
# mismo y lo único que cambia es cuánto razonamiento se pide.

FEW_SHOT_EXAMPLES = """\
Pregunta: ¿Cuánto es 4127 × 358?
Razonamiento: Multiplico por cada cifra de 358 y sumo los productos parciales.
- 4127 × 8 = 33016
- 4127 × 50 = 206350
- 4127 × 300 = 1238100
- Suma: 33016 + 206350 = 239366; 239366 + 1238100 = 1477466
Respuesta: 1477466

Pregunta: Partes en el origen (0, 0) mirando al norte (+Y). Avanza 2. Gira a la \
izquierda. Avanza 3. Gira a la izquierda. Retrocede 1. ¿Cuáles son tus coordenadas \
finales? Formato (X, Y).
Razonamiento: Anoto posición y orientación después de cada instrucción.
- Inicio: (0, 0), mirando al norte.
- Avanza 2 hacia el norte: (0, 2), mirando al norte.
- Gira a la izquierda: (0, 2), mirando al oeste.
- Avanza 3 hacia el oeste: (-3, 2), mirando al oeste.
- Gira a la izquierda: (-3, 2), mirando al sur.
- Retrocede 1 (mirando al sur, retroceder es moverse al norte): (-3, 3), mirando al sur.
Respuesta: (-3, 3)

Pregunta: Una reunión empieza a las 23:20 y tiene dos bloques de 50 y 35 minutos \
con una pausa de 10 minutos entre ellos. ¿A qué hora termina? Formato HH:MM.
Razonamiento: Avanzo el reloj bloque por bloque.
- Inicio: 23:20.
- Bloque 1 (50 min): 23:20 + 0:50 = 00:10 (pasa la medianoche).
- Pausa (10 min): 00:10 + 0:10 = 00:20.
- Bloque 2 (35 min): 00:20 + 0:35 = 00:55.
Respuesta: 00:55"""


@dataclass(frozen=True)
class Strategy:
    """Forma de preguntar: una plantilla con el marcador {pregunta}.

    Attributes:
        name: Etiqueta para pantalla y tablas.
        color: Color rich de la estrategia.
        template: Prompt completo; {pregunta} se reemplaza por el enunciado.
    """

    name: str
    color: str
    template: str

    def prompt(self, question: str) -> str:
        """Devuelve el prompt de esta estrategia para `question`."""
        return self.template.replace("{pregunta}", question)


DIRECT = Strategy(
    "Directo",
    "cyan",
    "{pregunta}\n\nNo muestres razonamiento ni pasos intermedios. Responde "
    "únicamente con una línea: 'Respuesta: <valor>'.",
)
ZERO_SHOT_COT = Strategy(
    "Zero-shot CoT",
    "magenta",
    "{pregunta}\n\nPiensa paso a paso y muestra tu razonamiento. Termina con una "
    "última línea: 'Respuesta: <valor>'.",
)
FEW_SHOT_COT = Strategy(
    "Few-shot CoT",
    "yellow",
    "Resuelve el problema. Razona paso a paso como en los ejemplos y termina con "
    "una última línea: 'Respuesta: <valor>'.\n\n"
    + FEW_SHOT_EXAMPLES
    + "\n\nPregunta: {pregunta}\nRazonamiento:",
)
STRATEGIES: tuple[Strategy, ...] = (DIRECT, ZERO_SHOT_COT, FEW_SHOT_COT)


# ── Llamada al modelo y corrección ─────────────────────────────────────────────


@dataclass(frozen=True)
class RunResult:
    """Resultado de una llamada: respuesta corregida, costo y latencia.

    Attributes:
        answer: Respuesta final normalizada, usada como voto. Si es correcta se
            reemplaza por la grafía canónica para que "404.356.698" y
            "404356698" cuenten como el mismo voto.
        correct: Si la respuesta final coincide con alguna grafía válida.
        input_tokens: Tokens del prompt (usage_metadata.prompt_token_count).
        output_tokens: Tokens generados, incluidos los de thinking si está activo.
        seconds: Latencia de la llamada, reintentos incluidos.
        text: Respuesta completa del modelo ("" si falló).
        failed: True si la API falló tras agotar los reintentos.
    """

    answer: str
    correct: bool
    input_tokens: int
    output_tokens: int
    seconds: float
    text: str
    failed: bool = False


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos automáticos.

    Returns:
        Un genai.Client que reintenta hasta 5 veces con backoff exponencial ante
        429 y errores 5xx.

    Side effects:
        Lee GEMINI_API_KEY del entorno (cargado desde <repo>/.env por load_dotenv).

    Edge cases:
        Si falta la key, imprime un panel de error y termina con SystemExit(1).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel.fit(
                "GEMINI_API_KEY no está definida.\n"
                "Agrégala a <repo>/.env (GEMINI_API_KEY=...) o expórtala en la terminal.",
                title="[bold red]Error[/bold red]",
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


def _normalize(text: str) -> str:
    """Pasa a minúsculas y quita tildes, markdown, comillas, paréntesis y punto final."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"[*`\"'()\[\]]", "", plain).strip().rstrip(".").strip()


_ANSWER_LINE = re.compile(r"^[\s*#_>-]*respuesta[^:\n]*:(.*)$", re.I | re.M)


def grade(text: str, problem: Problem) -> tuple[str, bool]:
    """Extrae la respuesta final de `text` y la compara con la esperada.

    Args:
        text: Respuesta completa del modelo.
        problem: Pregunta con sus grafías válidas.

    Returns:
        (voto, correcta). El voto es la grafía canónica si la respuesta es
        correcta, o la respuesta normalizada si no lo es.

    Edge cases:
        Toma la última línea 'Respuesta: ...'; si no hay, la última línea no
        vacía. Acepta la respuesta correcta dentro de una frase ("El resultado
        es 14"), pero no como parte de otro número ("140").
    """
    matches = _ANSWER_LINE.findall(text)
    lines = [line for line in text.splitlines() if line.strip()]
    line = _normalize(matches[-1] if matches else (lines[-1] if lines else ""))
    compact = re.sub(r"\s+", "", line)
    for valid in problem.valid_answers:
        standalone = rf"(?<![\w.,:-]){re.escape(valid)}(?![\w,:-]|\.\d)"
        if compact == valid or re.search(standalone, line):
            return problem.valid_answers[0], True
    return compact or "(vacía)", False


def run_once(client: genai.Client, problem: Problem, strategy: Strategy) -> RunResult:
    """Hace una llamada al modelo con `strategy` y corrige la respuesta.

    Args:
        client: Cliente creado por get_gemini_client().
        problem: Pregunta a responder.
        strategy: Forma de preguntar.

    Returns:
        El RunResult de la llamada.

    Side effects:
        Una llamada de red a la API de Gemini (más reintentos si hay 429/5xx).

    Edge cases:
        Si la API falla tras los reintentos, devuelve failed=True y la corrida
        cuenta como incorrecta en vez de abortar la demo. Una respuesta vacía
        (p.ej. bloqueada por seguridad) también cuenta como incorrecta.
    """
    start = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=strategy.prompt(problem.question),
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
                # sin tools: evita que el SDK intente function calling automático
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except errors.APIError as exc:
        console.print(f"[red]Error de API ({exc.code}): {exc.message}[/red]")
        return RunResult("(error)", False, 0, 0, time.perf_counter() - start, "", True)
    seconds = time.perf_counter() - start
    text = response.text or ""
    usage = response.usage_metadata
    input_tokens = (usage.prompt_token_count or 0) if usage else 0
    output_tokens = (
        (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
        if usage
        else 0
    )
    answer, correct = grade(text, problem)
    return RunResult(answer, correct, input_tokens, output_tokens, seconds, text)


def majority_vote(results: list[RunResult]) -> tuple[str | None, int]:
    """Self-consistency: la respuesta más votada entre varias corridas.

    Args:
        results: Corridas de una misma pregunta y estrategia (no vacía).

    Returns:
        (respuesta ganadora, votos). La respuesta es None si hay empate en el
        primer lugar: sin mayoría no hay respuesta, y eso cuenta como fallo.
    """
    ranked = Counter(r.answer for r in results).most_common(2)
    winner, votes = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == votes:
        return None, votes
    return winner, votes


def vote_is_correct(results: list[RunResult], problem: Problem) -> bool:
    """True si la mayoría de `results` eligió la respuesta correcta de `problem`."""
    winner, _ = majority_vote(results)
    return winner == problem.valid_answers[0]


# ── Presentación ───────────────────────────────────────────────────────────────


def _labeled(label: str, body: str, label_style: str, body_style: str) -> Text:
    """Texto 'ETIQUETA: cuerpo' con sangría francesa, respetando saltos de línea."""
    indent = " " * len(label)
    wrapped = [
        textwrap.fill(line, width=82, subsequent_indent=indent) if line else ""
        for line in body.strip().splitlines()
    ]
    return Text.assemble(
        (label, label_style), (("\n" + indent).join(wrapped), body_style)
    )


def show_exchange(strategy: Strategy, problem: Problem, result: RunResult) -> None:
    """Imprime el prompt y la respuesta de una corrida en paneles.

    Side effects:
        Escribe en stdout mediante la consola rich global.
    """
    console.print(
        Panel(
            _labeled(
                "USUARIO: ", strategy.prompt(problem.question), "bold blue", "blue"
            ),
            title=f"[bold bright_black]Entrada al modelo · {strategy.name}[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print(
        Panel(
            _labeled(
                "MODELO: ", result.text or "(sin respuesta)", "bold green", "italic"
            ),
            title=f"[bold bright_black]Respuesta del modelo · {strategy.name}[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


def show_progress(strategy: Strategy, results: list[RunResult]) -> None:
    """Imprime un punto verde/rojo y la latencia de cada corrida, 8 por línea.

    Side effects:
        Escribe en stdout mediante la consola rich global.
    """
    per_line = 8
    for first in range(0, len(results), per_line):
        label = strategy.name if first == 0 else ""
        cells = []
        for run, result in enumerate(
            results[first : first + per_line], start=first + 1
        ):
            dot = "[green]●[/green]" if result.correct else "[red]●[/red]"
            mark = "[red]err[/red]" if result.failed else ""
            cells.append(f"#{run:02d} {dot} [dim]{result.seconds:.1f}s[/dim]{mark}")
        console.print(
            f"  [{strategy.color}]{label:<14}[/{strategy.color}]" + " ".join(cells),
            highlight=False,
        )


def accuracy_bar(correct: int, total: int, width: int = 16) -> Text:
    """Barra llena/vacía coloreada según exactitud (verde ≥80 %, amarillo ≥50 %)."""
    pct = correct / total if total else 0.0
    filled = round(pct * width)
    color = "green" if pct >= 0.8 else "yellow" if pct >= 0.5 else "red"
    bar = "█" * filled + "░" * (width - filled)
    return Text(f"{bar} {correct}/{total} ({pct:.0%})", style=color)


def vote_cell(results: list[RunResult], problem: Problem) -> Text:
    """Celda 'respuesta (votos/N) ✓/✗' con el resultado de la votación."""
    winner, votes = majority_vote(results)
    shown = "empate" if winner is None else winner
    if len(shown) > 14:
        shown = shown[:13] + "…"
    ok = winner == problem.valid_answers[0]
    return Text(
        f"{shown} ({votes}/{len(results)}) {'✓' if ok else '✗'}",
        style="green" if ok else "red",
    )


def show_problem(
    index: int, problem: Problem, by_strategy: dict[str, list[RunResult]]
) -> None:
    """Imprime el enunciado, el progreso de cada estrategia y una tabla parcial.

    Side effects:
        Escribe en stdout mediante la consola rich global.
    """
    console.print(
        Rule(
            f"[bold]Pregunta {index}/{len(PROBLEMS)}: {problem.title}[/bold]",
            style="white",
        )
    )
    console.print(f"[bold]P:[/bold] {problem.question}", highlight=False)
    console.print(
        f"[bold]Respuesta correcta:[/bold] [green]{problem.valid_answers[0]}[/green]",
        highlight=False,
    )
    console.print(f"[dim]{problem.explanation}[/dim]\n", highlight=False)

    for strategy in STRATEGIES:
        show_progress(strategy, by_strategy[strategy.name])
    console.print()

    table = Table(
        show_header=True, header_style="bold", padding=(0, 2), show_edge=False
    )
    table.add_column("Estrategia", min_width=13)
    table.add_column("Aciertos por corrida")
    table.add_column("Voto de mayoría")
    table.add_column("Tokens salida", justify="right")
    table.add_column("Tiempo prom.", justify="right")
    for strategy in STRATEGIES:
        results = by_strategy[strategy.name]
        table.add_row(
            f"[{strategy.color}]{strategy.name}[/{strategy.color}]",
            accuracy_bar(sum(r.correct for r in results), len(results)),
            vote_cell(results, problem),
            f"{sum(r.output_tokens for r in results) / len(results):.0f}",
            f"{sum(r.seconds for r in results) / len(results):.1f}s",
        )
    console.print(table)
    console.print()


@dataclass(frozen=True)
class StrategyStats:
    """Métricas agregadas de una estrategia sobre todas las preguntas."""

    correct: int
    runs: int
    votes_correct: int
    rescued: int  # preguntas con algún fallo por corrida que el voto acertó
    input_tokens: float  # promedio por llamada
    output_tokens: float  # promedio por llamada
    seconds: float  # promedio por llamada

    @property
    def accuracy(self) -> float:
        """Fracción de corridas correctas (0 a 1)."""
        return self.correct / self.runs if self.runs else 0.0


def summarize(
    results: dict[tuple[int, str], list[RunResult]],
) -> dict[str, StrategyStats]:
    """Agrega los resultados por estrategia.

    Args:
        results: Corridas indexadas por (índice de pregunta, nombre de estrategia).

    Returns:
        StrategyStats por nombre de estrategia.
    """
    stats: dict[str, StrategyStats] = {}
    for strategy in STRATEGIES:
        per_problem = [
            (problem, results[(i, strategy.name)]) for i, problem in enumerate(PROBLEMS)
        ]
        flat = [r for _, runs in per_problem for r in runs]
        votes = [vote_is_correct(runs, problem) for problem, runs in per_problem]
        rescued = sum(
            ok and not all(r.correct for r in runs)
            for ok, (_, runs) in zip(votes, per_problem)
        )
        stats[strategy.name] = StrategyStats(
            correct=sum(r.correct for r in flat),
            runs=len(flat),
            votes_correct=sum(votes),
            rescued=rescued,
            input_tokens=sum(r.input_tokens for r in flat) / len(flat),
            output_tokens=sum(r.output_tokens for r in flat) / len(flat),
            seconds=sum(r.seconds for r in flat) / len(flat),
        )
    return stats


def verdict(stats: dict[str, StrategyStats], runs: int) -> str:
    """Construye el veredicto a partir de las métricas (nada hardcodeado).

    Args:
        stats: Salida de summarize().
        runs: Corridas por estrategia y pregunta (tamaño del voto).

    Returns:
        Texto con markup rich: efecto de CoT, costo de few-shot y efecto del voto.
    """
    direct = stats[DIRECT.name]
    zero, few = stats[ZERO_SHOT_COT.name], stats[FEW_SHOT_COT.name]
    best_name, best = max(
        ((ZERO_SHOT_COT.name, zero), (FEW_SHOT_COT.name, few)),
        key=lambda kv: kv[1].accuracy,
    )
    lift = (best.accuracy - direct.accuracy) * 100
    if lift > 0:
        cot = (
            f"CoT sube la exactitud por corrida de {direct.accuracy:.0%} (Directo) a "
            f"{best.accuracy:.0%} ({best_name}), +{lift:.0f} pp, generando "
            f"{best.output_tokens / max(direct.output_tokens, 1):.0f}× tokens de salida."
        )
    else:
        cot = (
            f"En esta corrida CoT no superó al directo ({best.accuracy:.0%} vs "
            f"{direct.accuracy:.0%})."
        )
    few_vs_zero = (
        f"Few-shot vs zero-shot CoT: {few.accuracy:.0%} vs {zero.accuracy:.0%}, con "
        f"{few.input_tokens / max(zero.input_tokens, 1):.1f}× tokens de entrada y "
        f"{few.output_tokens / max(zero.output_tokens, 1):.1f}× de salida."
    )
    n = len(PROBLEMS)
    missed = sum(n - s.votes_correct for s in (zero, few))
    rescued = zero.rescued + few.rescued
    vote = (
        f"Self-consistency (voto de {runs}): Directo {direct.votes_correct}/{n}, "
        f"Zero-shot {zero.votes_correct}/{n}, Few-shot {few.votes_correct}/{n} preguntas; "
        f"en CoT el voto rescató {rescued} pregunta(s) con fallos esporádicos y no "
        f"corrigió {missed} donde la respuesta correcta no era la más votada."
    )
    return f"[bold]VEREDICTO:[/bold] {cot}\n{few_vs_zero}\n{vote}"


def show_summary(results: dict[tuple[int, str], list[RunResult]], runs: int) -> None:
    """Imprime las tablas de resumen y el veredicto.

    Side effects:
        Escribe en stdout mediante la consola rich global.
    """
    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    console.print()

    per_problem = Table(
        title="Aciertos por pregunta (corridas correctas / voto de mayoría)",
        show_header=True,
        header_style="bold",
        padding=(0, 2),
        show_edge=False,
    )
    per_problem.add_column("Pregunta", min_width=24)
    for strategy in STRATEGIES:
        per_problem.add_column(
            f"[{strategy.color}]{strategy.name}[/{strategy.color}]", justify="center"
        )
    for i, problem in enumerate(PROBLEMS):
        cells = []
        for strategy in STRATEGIES:
            runs_here = results[(i, strategy.name)]
            ok = vote_is_correct(runs_here, problem)
            mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
            cells.append(
                f"{sum(r.correct for r in runs_here)}/{len(runs_here)}  voto {mark}"
            )
        per_problem.add_row(problem.title, *cells)
    console.print(per_problem)
    console.print()

    stats = summarize(results)
    table = Table(
        title="Resumen por estrategia",
        show_header=True,
        header_style="bold",
        padding=(0, 1),
        show_edge=False,
    )
    table.add_column("Estrategia", style="bold", min_width=13)
    table.add_column("Exactitud por corrida", no_wrap=True)
    table.add_column(f"Self-consistency\n(voto de {runs})", justify="center")
    table.add_column("Tokens entrada\n/ llamada", justify="right")
    table.add_column("Tokens salida\n/ llamada", justify="right")
    table.add_column("Latencia\n/ llamada", justify="right")
    for strategy in STRATEGIES:
        s = stats[strategy.name]
        table.add_row(
            f"[{strategy.color}]{strategy.name}[/{strategy.color}]",
            accuracy_bar(s.correct, s.runs, width=12),
            f"{s.votes_correct}/{len(PROBLEMS)} preguntas",
            f"{s.input_tokens:.0f}",
            f"{s.output_tokens:.0f}",
            f"{s.seconds:.1f}s",
        )
    console.print(table)
    console.print(
        f"[dim]Self-consistency reutiliza las {runs} corridas ya hechas; en producción "
        f"cuesta {runs}× tokens por respuesta (y {runs} llamadas en paralelo).[/dim]"
    )
    failures = sum(r.failed for runs_here in results.values() for r in runs_here)
    if failures:
        console.print(
            f"[yellow]Aviso: {failures} llamada(s) fallaron tras 5 reintentos y "
            "cuentan como incorrectas.[/yellow]"
        )
    console.print()
    console.print(verdict(stats, runs), highlight=False)
    console.print()


# ── Main ───────────────────────────────────────────────────────────────────────


def _positive_int(value: str) -> int:
    """Tipo argparse: entero ≥ 1."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("debe ser un entero ≥ 1")
    return number


def main() -> None:
    """Corre las 3 estrategias × N corridas × 5 preguntas y muestra el resumen.

    Side effects:
        3 × N × 5 llamadas a la API de Gemini (en paralelo, MAX_WORKERS a la vez)
        y salida formateada en stdout. No escribe archivos.
    """
    parser = argparse.ArgumentParser(description="CoT vs Directo y self-consistency.")
    parser.add_argument(
        "--runs",
        type=_positive_int,
        default=DEFAULT_RUNS,
        help=f"corridas por estrategia y pregunta (default {DEFAULT_RUNS})",
    )
    runs: int = parser.parse_args().runs
    client = get_gemini_client()
    thinking = "thinking desactivado" if THINKING_BUDGET == 0 else "thinking activo"

    console.print(
        Panel.fit(
            "[bold yellow]Chain of Thought vs. Directo (y self-consistency)[/bold yellow]\n"
            "[dim]¿Pensar paso a paso sube la exactitud? ¿Y votar entre corridas?[/dim]\n"
            f"[dim]Modelo: {MODEL} ({thinking}) | {runs} corridas × "
            f"{len(STRATEGIES)} estrategias × {len(PROBLEMS)} preguntas[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures: dict[tuple[int, str], list[Future[RunResult]]] = {
            (i, strategy.name): [
                pool.submit(run_once, client, problem, strategy) for _ in range(runs)
            ]
            for i, problem in enumerate(PROBLEMS)
            for strategy in STRATEGIES
        }
        results: dict[tuple[int, str], list[RunResult]] = {}
        for i, problem in enumerate(PROBLEMS):
            by_strategy = {
                strategy.name: [f.result() for f in futures[(i, strategy.name)]]
                for strategy in STRATEGIES
            }
            if i == 0:
                console.print(
                    Rule(
                        "[bold]Intercambio de muestra: corrida #1 de la pregunta 1[/bold]"
                    )
                )
                for strategy in STRATEGIES:
                    show_exchange(strategy, problem, by_strategy[strategy.name][0])
            show_problem(i + 1, problem, by_strategy)
            for name, runs_here in by_strategy.items():
                results[(i, name)] = runs_here

    show_summary(results, runs)
    console.print(f"[dim]Tiempo total: {time.perf_counter() - started:.0f}s[/dim]")


if __name__ == "__main__":
    main()
