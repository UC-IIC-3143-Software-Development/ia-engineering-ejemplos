#!/usr/bin/env python3
"""Router de LLMs con LiteLLM: una interfaz para varios modelos, fallback y ruteo.

Tres fases sobre la misma tarea (clasificar mensajes de clientes en 4 categorías):
  Fase 1 — la misma llamada litellm.completion() contra tres modelos Gemini:
           aciertos, latencia, tokens y costo por llamada (litellm.completion_cost).
  Fase 2 — un Router con un deployment roto a propósito: el error llega
           estandarizado y el fallback responde con el deployment sano.
  Fase 3 — tres estrategias de ruteo (simple-shuffle, latency-based,
           cost-based) sobre un grupo de tres deployments.
"""

import argparse
import asyncio
import logging
import os
import re
import statistics
import textwrap
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any

import litellm
import openai  # lo instala litellm: sus excepciones son las "estandarizadas"
from dotenv import load_dotenv
from litellm import ModelResponse, Router
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

# LiteLLM imprime banners de ayuda y un log por cada reintento o fallback; la demo
# muestra lo que importa con rich, así que se silencian.
litellm.suppress_debug_info = True
for _logger_name in ("LiteLLM", "LiteLLM Router"):
    logging.getLogger(_logger_name).setLevel(logging.ERROR)

# ── Modelos ────────────────────────────────────────────────────────────────
# En LiteLLM el proveedor va como prefijo del modelo ("gemini/", "openai/",
# "anthropic/"); el resto del código es idéntico para cualquier proveedor.
MODEL = "gemini/gemini-2.5-flash"
MODELS = (MODEL, "gemini/gemini-3.1-flash-lite", "gemini/gemini-3.8-flash")
BROKEN_MODEL = "gemini/gemini-modelo-inexistente"

DEFAULT_RUNS = 10
# El Router reintenta solo errores transitorios (408, 409, 429 y 5xx).
# litellm.completion(num_retries=...) reintenta cualquier error, sin espera por
# defecto; por eso en la Fase 1 se le pide backoff exponencial.
NUM_RETRIES = 3

# ── Fase 2: un grupo roto con fallback a uno sano ──────────────────────────
FALLBACK_MODEL_LIST: list[dict[str, Any]] = [
    # Roto a propósito: simula un modelo retirado o un proveedor caído.
    {"model_name": "principal", "litellm_params": {"model": BROKEN_MODEL}},
    {"model_name": "respaldo", "litellm_params": {"model": MODEL}},
    # Otro proveedor es solo otra entrada; el código que llama no cambia.
    # (No se usan aquí porque solo hay key de Gemini.)
    # {"model_name": "respaldo",
    #  "litellm_params": {"model": "openai/gpt-5-mini", "api_key": "os.environ/OPENAI_API_KEY"}},
    # {"model_name": "respaldo",
    #  "litellm_params": {"model": "anthropic/claude-haiku-4-5",
    #                     "api_key": "os.environ/ANTHROPIC_API_KEY"}},
]
FALLBACKS = [{"principal": ["respaldo"]}]

# ── Fase 3: un grupo con tres deployments; el Router elige a cuál llamar ───
ROUTER_GROUP = "clasificador"
GROUP_MODEL_LIST: list[dict[str, Any]] = [
    {"model_name": ROUTER_GROUP, "litellm_params": {"model": model}} for model in MODELS
]


@dataclass(frozen=True)
class Strategy:
    """Una estrategia de ruteo de LiteLLM.

    Attributes:
        letter: Letra de la columna en la tabla (A/B/C).
        name: Valor de `routing_strategy` que recibe litellm.Router.
        criterion: Qué optimiza la estrategia, tal como la implementa LiteLLM.
    """

    letter: str
    name: str
    criterion: str


STRATEGIES = (
    Strategy("A", "simple-shuffle", "al azar entre los deployments sanos (línea base)"),
    Strategy(
        "B",
        "latency-based-routing",
        "menor latencia, medida en segundos por token de salida",
    ),
    Strategy(
        "C",
        "cost-based-routing",
        "menor precio de lista por token (tabla de precios de LiteLLM)",
    ),
)

# ── Tarea: la misma para todos los modelos y fases ─────────────────────────
SYSTEM_PROMPT = (
    "Clasificas mensajes de clientes de una plataforma de cursos en línea en UNA categoría:\n"
    "- facturacion: cobros, pagos, reembolsos, boletas o facturas\n"
    "- soporte_tecnico: errores, fallas o problemas para entrar o usar la app\n"
    "- ventas: precios, planes, promociones o contratar algo nuevo\n"
    "- otro: todo lo demás\n"
    "Responde solo con el nombre de la categoría."
)

# (mensaje, categoría esperada). Algunos traen distractores ("Pagar", "plan").
TICKETS: tuple[tuple[str, str], ...] = (
    ("La app se cierra sola cuando abro un video del curso.", "soporte_tecnico"),
    ("¿Tienen plan anual con descuento para estudiantes?", "ventas"),
    ("Necesito la boleta de marzo para rendir gastos.", "facturacion"),
    ("Me cobraron dos veces la suscripción de este mes.", "facturacion"),
    (
        "No puedo iniciar sesión: dice 'token expirado' aunque cambié la clave.",
        "soporte_tecnico",
    ),
    ("Quiero pasar del plan básico al pro, ¿cuánto sale la diferencia?", "ventas"),
    ("El botón 'Pagar' no hace nada cuando lo toco en el celular.", "soporte_tecnico"),
    (
        "Cancelé hace una semana y me siguen cobrando; quiero el reembolso.",
        "facturacion",
    ),
    ("Solo quería decirles que el curso de SQL está excelente.", "otro"),
    ("Si inscribo a 10 personas de mi empresa, ¿hay precio por volumen?", "ventas"),
)

Send = Callable[..., ModelResponse]
AsyncSend = Callable[..., Awaitable[ModelResponse]]

console = Console()


@dataclass(frozen=True)
class CallResult:
    """Una llamada medida: qué respondió, qué deployment respondió y cuánto costó.

    Attributes:
        ok: False si la llamada terminó en excepción (tras reintentos y fallbacks).
        correct: True si la categoría respondida es la esperada.
        answer: Categoría normalizada ("" si falló).
        deployment: Modelo que respondió (`response.model`) o, si falló, el nombre
            de la excepción.
        latency_s: Tiempo de reloj de la llamada completa, incluidos reintentos y
            fallbacks.
        prompt_tokens: Tokens de entrada reportados (0 si falló).
        completion_tokens: Tokens de salida, incluidos los de razonamiento.
        reasoning_tokens: Parte de `completion_tokens` que el modelo usó para pensar.
        cost_usd: `litellm.completion_cost` de la respuesta (0 si falló).
        error: La excepción, si la hubo.
    """

    ok: bool
    correct: bool
    answer: str
    deployment: str
    latency_s: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    error: openai.APIError | None = None

    @classmethod
    def from_response(
        cls, response: ModelResponse, expected: str, latency_s: float
    ) -> "CallResult":
        """Construye el resultado de una llamada exitosa.

        Args:
            response: Respuesta de litellm.completion / Router.(a)completion.
            expected: Categoría correcta del ticket.
            latency_s: Duración medida por quien llamó.

        Returns:
            Un CallResult con tokens y costo calculado por LiteLLM con su tabla de
            precios (incluye los tokens de razonamiento, que se cobran como salida).
        """
        answer = parse_label(response.choices[0].message.content)
        usage = response.usage
        details = usage.completion_tokens_details
        return cls(
            ok=True,
            correct=answer == expected,
            answer=answer,
            deployment=response.model or "?",
            latency_s=latency_s,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            reasoning_tokens=(details.reasoning_tokens or 0) if details else 0,
            cost_usd=litellm.completion_cost(completion_response=response),
        )

    @classmethod
    def from_error(cls, error: openai.APIError, latency_s: float) -> "CallResult":
        """Construye el resultado de una llamada fallida (deployment = tipo de error)."""
        return cls(
            ok=False,
            correct=False,
            answer="",
            deployment=type(error).__name__,
            latency_s=latency_s,
            error=error,
        )


@dataclass(frozen=True)
class Stats:
    """Métricas agregadas de un conjunto de llamadas.

    Attributes:
        n: Llamadas intentadas.
        ok: Llamadas que devolvieron respuesta.
        correct: Respuestas con la categoría esperada.
        avg_latency_s: Latencia promedio por llamada (todas, incluso las fallidas).
        avg_prompt_tokens, avg_completion_tokens, avg_reasoning_tokens: Promedios
            sobre las llamadas exitosas.
        ms_per_output_token: Promedio de latencia / tokens de salida por llamada; es
            la métrica que usa latency-based-routing de LiteLLM.
        cost_per_call_usd: Costo promedio por llamada exitosa.
        total_cost_usd: Costo sumado de todas las llamadas.
        shares: Llamadas exitosas por deployment (nombre sin prefijo de proveedor).
    """

    n: int
    ok: int
    correct: int
    avg_latency_s: float
    avg_prompt_tokens: float
    avg_completion_tokens: float
    avg_reasoning_tokens: float
    ms_per_output_token: float
    cost_per_call_usd: float
    total_cost_usd: float
    shares: Counter[str]

    @classmethod
    def of(cls, results: Sequence[CallResult]) -> "Stats":
        """Agrega una lista no vacía de resultados.

        Edge cases:
            Si ninguna llamada fue exitosa, los promedios de tokens y costo valen 0.
        """
        good = [r for r in results if r.ok]
        return cls(
            n=len(results),
            ok=len(good),
            correct=sum(r.correct for r in results),
            avg_latency_s=_mean([r.latency_s for r in results]),
            avg_prompt_tokens=_mean([r.prompt_tokens for r in good]),
            avg_completion_tokens=_mean([r.completion_tokens for r in good]),
            avg_reasoning_tokens=_mean([r.reasoning_tokens for r in good]),
            ms_per_output_token=_mean(
                [
                    r.latency_s * 1000 / r.completion_tokens
                    for r in good
                    if r.completion_tokens
                ]
            ),
            cost_per_call_usd=_mean([r.cost_usd for r in good]),
            total_cost_usd=sum(r.cost_usd for r in results),
            shares=Counter(r.deployment for r in good),
        )

    def share_pct(self, model: str) -> float:
        """Porcentaje de las llamadas intentadas que atendió `model` (con o sin prefijo)."""
        return 100 * self.shares[short(model)] / self.n if self.n else 0.0


def _mean(values: Sequence[float]) -> float:
    """Promedio que vale 0.0 para una lista vacía."""
    return statistics.fmean(values) if values else 0.0


def short(model: str) -> str:
    """Quita el prefijo de proveedor: "gemini/gemini-2.5-flash" -> "gemini-2.5-flash"."""
    return model.split("/", 1)[-1]


def parse_label(content: str | None) -> str:
    """Normaliza la respuesta del modelo a una categoría candidata.

    Returns:
        La primera palabra en minúsculas, sin comillas, asteriscos ni puntuación;
        "" si la respuesta vino vacía. No valida que sea una categoría conocida:
        una respuesta rara simplemente no coincide con la esperada.
    """
    words = (content or "").strip().lower().split()
    return words[0].strip("`*\"'.,:") if words else ""


def build_messages(text: str) -> list[dict[str, str]]:
    """Mensajes en formato OpenAI, el que LiteLLM acepta para cualquier proveedor."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]


def classify(send: Send, run: int) -> CallResult:
    """Clasifica el ticket de la corrida `run` con `send` y mide la llamada.

    Args:
        send: Función con la firma de litellm.completion ya fijada al modelo o
            grupo (p. ej. `partial(litellm.completion, model=...)` o
            `partial(router.completion, model="principal")`); recibe `messages`.
        run: Número de corrida (desde 0); elige el ticket en forma cíclica.

    Returns:
        El CallResult de la llamada. Nunca lanza errores de proveedor: LiteLLM los
        traduce a subclases de openai.APIError y quedan en `CallResult.error`.

    Side effects:
        Una o más peticiones de red (según reintentos y fallbacks).
    """
    text, expected = TICKETS[run % len(TICKETS)]
    start = time.perf_counter()
    try:
        response = send(messages=build_messages(text))
    except openai.APIError as exc:
        return CallResult.from_error(exc, time.perf_counter() - start)
    return CallResult.from_response(response, expected, time.perf_counter() - start)


async def aclassify(send: AsyncSend, run: int) -> CallResult:
    """Versión asíncrona de `classify` para `router.acompletion` (mismo contrato)."""
    text, expected = TICKETS[run % len(TICKETS)]
    start = time.perf_counter()
    try:
        response = await send(messages=build_messages(text))
    except openai.APIError as exc:
        return CallResult.from_error(exc, time.perf_counter() - start)
    return CallResult.from_response(response, expected, time.perf_counter() - start)


# ── Presentación ────────────────────────────────────────────────────────────


def _wrap(text: str, indent: int) -> str:
    """Envuelve a 82 columnas respetando los saltos de línea y alineando con `indent`."""
    pad = " " * indent
    lines = [
        textwrap.fill(line, width=82, subsequent_indent=pad)
        for line in text.splitlines()
    ]
    return ("\n" + pad).join(lines)


def display_exchange(messages: list[dict[str, str]], result: CallResult) -> None:
    """Muestra un intercambio de muestra: mensajes enviados y respuesta con su uso.

    Side effects:
        Escribe dos paneles en stdout.
    """
    parts = [
        Text.assemble(
            (f"{m['role'].upper()}: ", "bold blue"),
            (_wrap(m["content"], len(m["role"]) + 2), "blue"),
        )
        for m in messages
    ]
    console.print(
        Panel(
            Group(*parts),
            title="[bold bright_black]Entrada al modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    response = Text.assemble(
        ("ASSISTANT: ", "bold green"), (result.answer or "(vacío)", "italic")
    )
    usage = Text(
        f"\n\n{result.deployment} · {result.prompt_tokens} tokens de entrada / "
        f"{result.completion_tokens} de salida ({result.reasoning_tokens} de razonamiento) · "
        f"US${result.cost_usd:.6f} · {result.latency_s:.2f}s",
        style="dim",
    )
    console.print(
        Panel(
            Text.assemble(response, usage),
            title="[bold bright_black]Respuesta del modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


def display_error(error: openai.APIError) -> None:
    """Muestra la excepción que LiteLLM entrega y su jerarquía de clases.

    Side effects:
        Escribe un panel en stdout.
    """
    # p. ej. litellm.NotFoundError → openai.NotFoundError → openai.APIError
    chain = " → ".join(
        f"{cls.__module__.split('.')[0]}.{cls.__name__}"
        for cls in type(error).__mro__
        if cls.__name__ in (type(error).__name__, "APIError")
    )
    match = re.search(r'"message":\s*"([^"]+)"', str(error))
    detail = match.group(1) if match else str(error)
    body = Text.assemble(
        ("Tipo:        ", "bold"),
        (chain, "red"),
        "\n",
        ("status_code: ", "bold"),
        str(getattr(error, "status_code", "?")),
        "\n",
        ("proveedor:   ", "bold"),
        str(getattr(error, "llm_provider", "?")),
        "\n",
        ("mensaje:     ", "bold"),
        (_wrap(detail, 13), "dim"),
        "\n\n",
        (
            "Con OpenAI o Anthropic el `except` es el mismo: LiteLLM traduce cada error "
            "del proveedor a estas clases.",
            "italic",
        ),
    )
    console.print(
        Panel(
            body,
            title="[bold bright_black]Error estandarizado (sin router)[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()


PROGRESS_LEGEND = "Leyenda: [green]o[/green] acierto  [yellow]~[/yellow] categoría errada  [red]x[/red] error"


def _per_line(show_deployment: bool) -> int:
    """Corridas por fila de progreso (menos si cada una lleva el deployment)."""
    return 3 if show_deployment else 5


def print_progress(run: int, result: CallResult, show_deployment: bool) -> None:
    """Imprime una marca por corrida (ver PROGRESS_LEGEND) con su latencia.

    Args:
        run: Número de corrida desde 1; al completar una fila se salta de línea.
        result: Resultado de la corrida.
        show_deployment: Si True, agrega qué deployment respondió (o el error).

    Side effects:
        Escribe en stdout sin salto de línea salvo al completar la fila.
    """
    if result.correct:
        mark = "[green]o[/green]"
    elif result.ok:
        mark = "[yellow]~[/yellow]"
    else:
        mark = "[red]x[/red]"
    label = f" {short(result.deployment):<21}" if show_deployment else ""
    console.print(
        f"  #{run:02d}: {mark} [dim]{result.latency_s:4.1f}s{label}[/dim]",
        end="  ",
        highlight=False,
    )
    if run % _per_line(show_deployment) == 0:
        console.print()


def end_progress(last_run: int, show_deployment: bool) -> None:
    """Cierra la fila de progreso si quedó a medias y deja una línea en blanco."""
    if last_run % _per_line(show_deployment) != 0:
        console.print()
    console.print()


def add_metric_row(
    table: Table,
    label: str,
    values: Sequence[float],
    fmt: Callable[[float], str],
    better: Callable[[Sequence[float]], float] = min,
) -> None:
    """Agrega una fila y pinta de verde el mejor valor (`min` o `max`)."""
    best = better(values)
    table.add_row(
        label, *[f"[green]{fmt(v)}[/green]" if v == best else fmt(v) for v in values]
    )


# ── Fases ─────────────────────────────────────────────────────────────────


def run_models(runs: int) -> dict[str, Stats]:
    """Fase 1: la misma llamada litellm.completion contra cada modelo de MODELS.

    Args:
        runs: Tickets por modelo.

    Returns:
        Stats por modelo (clave: nombre con prefijo de proveedor).

    Side effects:
        runs × len(MODELS) llamadas de red; imprime una muestra, el progreso y la tabla.
    """
    console.print(
        Rule("[bold]Fase 1 — La misma llamada, tres modelos[/bold]", style="white")
    )
    console.print(
        '[dim]litellm.completion(model="gemini/<id>", messages=[...]) — solo cambia el string '
        "del modelo; el costo sale de litellm.completion_cost(response).[/dim]\n"
        f"[dim]{PROGRESS_LEGEND}[/dim]"
    )
    console.print()
    stats: dict[str, Stats] = {}
    for model in MODELS:
        send = partial(
            litellm.completion,
            model=model,
            num_retries=NUM_RETRIES,
            retry_strategy="exponential_backoff_retry",
        )
        results: list[CallResult] = []
        first = 1
        if model == MODEL:
            sample = classify(send, 0)
            results.append(sample)
            display_exchange(build_messages(TICKETS[0][0]), sample)
            first = 2
        console.print(f"[bold cyan]-- {short(model)} " + "-" * 40 + "[/bold cyan]")
        for run in range(first, runs + 1):
            result = classify(send, run - 1)
            results.append(result)
            print_progress(run, result, show_deployment=False)
        end_progress(runs, show_deployment=False)
        stats[model] = Stats.of(results)

    table = Table(title="Fase 1 — misma llamada, tres modelos", show_lines=True)
    table.add_column("Métrica", style="bold", min_width=26)
    for model in MODELS:
        table.add_column(short(model), justify="center")
    rows = [stats[m] for m in MODELS]
    add_metric_row(
        table, "Aciertos", [s.correct for s in rows], lambda v: f"{v:.0f}/{runs}", max
    )
    add_metric_row(
        table,
        "Latencia prom. por llamada",
        [s.avg_latency_s for s in rows],
        lambda v: f"{v:.2f}s",
    )
    add_metric_row(
        table,
        "Tokens de entrada (prom.)",
        [s.avg_prompt_tokens for s in rows],
        lambda v: f"{v:.0f}",
    )
    table.add_row(
        "Tokens de salida (prom.)",
        *[
            f"{s.avg_completion_tokens:.0f} ({s.avg_reasoning_tokens:.0f} razon.)"
            for s in rows
        ],
    )
    add_metric_row(
        table,
        "Latencia por token de salida",
        [s.ms_per_output_token for s in rows],
        lambda v: f"{v:.1f} ms",
    )
    add_metric_row(
        table,
        "Costo por llamada",
        [s.cost_per_call_usd for s in rows],
        lambda v: f"US${v:.6f}",
    )
    add_metric_row(
        table,
        "Costo por 1.000 llamadas",
        [s.cost_per_call_usd * 1000 for s in rows],
        lambda v: f"US${v:.3f}",
    )
    console.print(table)
    console.print()
    return stats


def run_fallback(runs: int) -> tuple[Stats, Stats]:
    """Fase 2: llamar a un modelo roto sin router vs. con Router + fallback.

    Args:
        runs: Llamadas por variante.

    Returns:
        (stats sin router, stats con Router + fallback).

    Side effects:
        2 × runs llamadas de red (las del modelo roto fallan rápido con 404, sin
        costo); imprime el error estandarizado, el progreso y la tabla.
    """
    console.print(
        Rule("[bold]Fase 2 — Fallback: un deployment roto[/bold]", style="white")
    )
    console.print(
        f"[dim]model_list:  principal → {BROKEN_MODEL} (roto a propósito)\n"
        f"             respaldo  → {MODEL}\n"
        f"fallbacks:   {FALLBACKS}\n"
        "Otro proveedor sería otra entrada (openai/gpt-5-mini, anthropic/claude-haiku-4-5); "
        "aquí solo hay key de Gemini.[/dim]"
    )
    console.print()

    console.print(
        f'[bold cyan]-- Sin router: litellm.completion(model="{BROKEN_MODEL}") ---[/bold cyan]'
    )
    # La llamada tal cual, sin reintentos: así se ve un modelo caído sin router.
    direct_send = partial(litellm.completion, model=BROKEN_MODEL)
    direct = [classify(direct_send, 0)]
    if direct[0].error is not None:
        display_error(direct[0].error)
    for run in range(2, runs + 1):
        result = classify(direct_send, run - 1)
        direct.append(result)
        print_progress(run, result, show_deployment=True)
    end_progress(runs, show_deployment=True)

    console.print(
        '[bold cyan]-- Con Router + fallback: router.completion(model="principal") ---[/bold cyan]'
    )
    router = Router(
        model_list=FALLBACK_MODEL_LIST, fallbacks=FALLBACKS, num_retries=NUM_RETRIES
    )
    routed_send = partial(router.completion, model="principal")
    routed: list[CallResult] = []
    for run in range(1, runs + 1):
        result = classify(routed_send, run - 1)
        routed.append(result)
        print_progress(run, result, show_deployment=True)
    end_progress(runs, show_deployment=True)

    direct_stats, routed_stats = Stats.of(direct), Stats.of(routed)
    table = Table(title="Fase 2 — un deployment roto", show_lines=True)
    table.add_column("Métrica", style="bold", min_width=26)
    table.add_column("Sin router", justify="center", style="cyan")
    table.add_column("Router + fallback", justify="center", style="magenta")
    table.add_row(
        "Llamadas con respuesta",
        f"{direct_stats.ok}/{runs}",
        f"{routed_stats.ok}/{runs}",
    )
    table.add_row(
        "Aciertos", f"{direct_stats.correct}/{runs}", f"{routed_stats.correct}/{runs}"
    )
    table.add_row(
        "Latencia prom. por llamada",
        f"{direct_stats.avg_latency_s:.2f}s",
        f"{routed_stats.avg_latency_s:.2f}s",
    )
    table.add_row(
        "Quién respondió",
        _describe_outcomes(direct),
        _describe_outcomes(routed),
    )
    console.print(table)
    console.print(
        "[dim]El 404 no se reintenta (no es transitorio): el Router pasa directo al fallback. "
        "Un 429 o 5xx sí se reintentaría con backoff antes de caer al respaldo.[/dim]"
    )
    console.print()
    return direct_stats, routed_stats


def _describe_outcomes(results: Sequence[CallResult]) -> str:
    """Resume quién respondió cada llamada: "gemini-2.5-flash ×10" o "NotFoundError ×10"."""
    counts = Counter(short(r.deployment) for r in results)
    return "\n".join(f"{name} ×{count}" for name, count in counts.most_common())


async def run_strategies(runs: int) -> dict[str, Stats]:
    """Fase 3: el mismo grupo de deployments con cada estrategia de STRATEGIES.

    Usa router.acompletion porque en LiteLLM 1.103 cost-based-routing solo existe
    en el camino asíncrono (el síncrono no encuentra deployment). Las tres
    estrategias corren en un mismo event loop.

    Args:
        runs: Llamadas por estrategia.

    Returns:
        Stats por nombre de estrategia.

    Side effects:
        runs × len(STRATEGIES) llamadas de red; imprime el progreso.
    """
    console.print(Rule("[bold]Fase 3 — Estrategias de ruteo[/bold]", style="white"))
    console.print(
        f'[dim]Grupo "{ROUTER_GROUP}" = {len(MODELS)} deployments (los modelos de la Fase 1). '
        'El código llama siempre router.acompletion(model="clasificador"); '
        "la estrategia decide a quién.[/dim]"
    )
    console.print()
    stats: dict[str, Stats] = {}
    for strategy in STRATEGIES:
        console.print(
            f"[bold cyan]-- {strategy.letter} · {strategy.name}: {strategy.criterion}[/bold cyan]"
        )
        router = Router(
            model_list=GROUP_MODEL_LIST,
            routing_strategy=strategy.name,
            num_retries=NUM_RETRIES,
        )
        send = partial(router.acompletion, model=ROUTER_GROUP)
        results: list[CallResult] = []
        for run in range(1, runs + 1):
            result = await aclassify(send, run - 1)
            results.append(result)
            print_progress(run, result, show_deployment=True)
            # latency-based registra la latencia en un callback que LiteLLM encola en
            # el event loop; cederle el turno hace que la próxima elección ya la vea.
            await asyncio.sleep(0.05)
        end_progress(runs, show_deployment=True)
        stats[strategy.name] = Stats.of(results)
    return stats


# ── Resumen ─────────────────────────────────────────────────────────────────


def print_summary(
    runs: int,
    models: dict[str, Stats],
    direct: Stats,
    routed: Stats,
    strategies: dict[str, Stats],
) -> None:
    """Imprime la tabla A/B/C de estrategias y el veredicto calculado de las tres fases.

    Side effects:
        Escribe en stdout.
    """
    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    console.print()

    table = Table(
        title="Fase 3 — estrategias de ruteo sobre el mismo grupo", show_lines=True
    )
    table.add_column("Métrica", style="bold", min_width=26)
    for s in STRATEGIES:
        table.add_column(f"{s.letter} · {s.name}", justify="center")
    rows = [strategies[s.name] for s in STRATEGIES]
    for model in MODELS:
        table.add_row(
            f"% a {short(model)}", *[f"{st.share_pct(model):.0f}%" for st in rows]
        )
    add_metric_row(
        table, "Aciertos", [st.correct for st in rows], lambda v: f"{v:.0f}/{runs}", max
    )
    add_metric_row(
        table,
        "Latencia prom. por llamada",
        [st.avg_latency_s for st in rows],
        lambda v: f"{v:.2f}s",
    )
    add_metric_row(
        table,
        "Costo total",
        [st.total_cost_usd for st in rows],
        lambda v: f"US${v:.6f}",
    )
    base_cost = rows[0].total_cost_usd
    table.add_row(
        "Costo vs. A",
        *[_times(st.total_cost_usd / base_cost) if base_cost else "—" for st in rows],
    )
    console.print(table)
    console.print()

    headline, details = verdict(models, direct, routed, strategies)
    console.print(headline)
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold", no_wrap=True)
    grid.add_column()
    for label, text in details:
        grid.add_row(f"  · {label}:", text)
    console.print(grid)
    console.print()


def _times(ratio: float) -> str:
    """Formatea un cociente con precisión según su tamaño: "0.08×", "1.4×", "37×"."""
    if ratio < 1:
        return f"{ratio:.2f}×"
    return f"{ratio:.1f}×" if ratio < 10 else f"{ratio:.0f}×"


def verdict(
    models: dict[str, Stats],
    direct: Stats,
    routed: Stats,
    strategies: dict[str, Stats],
) -> tuple[str, list[tuple[str, str]]]:
    """Redacta el veredicto a partir de las métricas (nada hardcodeado).

    Returns:
        (línea VEREDICTO con estilo rich, [(etiqueta, detalle)] para costo,
        disponibilidad y ruteo).
    """
    # Costo: el más barato entre los modelos que lograron el máximo de aciertos.
    top_correct = max(s.correct for s in models.values())
    best = min(
        (m for m, s in models.items() if s.correct == top_correct),
        key=lambda m: models[m].cost_per_call_usd,
    )
    base = models[MODEL]
    if best == MODEL:
        cost_text = (
            f"{short(MODEL)} ya es el más barato entre los de más aciertos "
            f"({top_correct}/{base.n})."
        )
    else:
        pct = 100 * models[best].cost_per_call_usd / base.cost_per_call_usd
        cost_text = (
            f"{short(best)} acertó {models[best].correct}/{base.n} "
            f"(vs {base.correct}/{base.n} de {short(MODEL)}) con el {pct:.0f}% "
            f"de su costo por llamada."
        )

    extra = routed.avg_latency_s - direct.avg_latency_s
    availability_text = (
        f"con el deployment principal roto respondieron {direct.ok}/{direct.n} "
        f"llamadas sin router y {routed.ok}/{routed.n} con fallback "
        f"({extra:+.2f}s por llamada)."
    )

    shuffle, latency, cost = (strategies[s.name] for s in STRATEGIES)
    top_latency, latency_n = (
        latency.shares.most_common(1)[0] if latency.shares else ("—", 0)
    )
    top_cost, cost_n = cost.shares.most_common(1)[0] if cost.shares else ("—", 0)
    fastest_call = short(min(models, key=lambda m: models[m].avg_latency_s))
    cheaper = (
        shuffle.total_cost_usd / cost.total_cost_usd if cost.total_cost_usd else 0.0
    )
    routing_text = (
        f"cost-based mandó el {100 * cost_n / cost.n:.0f}% a {top_cost} y costó "
        f"{_times(cheaper)} menos que simple-shuffle. latency-based prefirió "
        f"{top_latency} ({100 * latency_n / latency.n:.0f}%)"
    )
    if top_latency == fastest_call:
        routing_text += ", que también fue el más rápido por llamada en la Fase 1."
    else:
        routing_text += (
            ": el de menor latencia POR TOKEN de salida, no por llamada (en la "
            f"Fase 1 el más rápido por llamada fue {fastest_call}; los tokens de "
            "razonamiento bajan la latencia por token)."
        )

    saved_all = routed.ok == routed.n and direct.ok < direct.n
    if saved_all and cheaper > 1:
        headline = (
            "[bold green]VEREDICTO: sin cambiar el código que llama, el Router "
            f"sostuvo {routed.ok}/{routed.n} respuestas con un deployment caído y, "
            f"ruteando por costo, gastó {_times(cheaper)} menos que al azar.[/bold green]"
        )
    elif saved_all:
        headline = (
            f"[bold yellow]VEREDICTO: el fallback sostuvo {routed.ok}/{routed.n} "
            "respuestas, pero rutear por costo no abarató esta corrida.[/bold yellow]"
        )
    else:
        headline = (
            "[bold red]VEREDICTO: el fallback no cubrió todas las llamadas "
            f"({routed.ok}/{routed.n}); revisa el deployment de respaldo.[/bold red]"
        )
    details = [
        ("Costo", cost_text),
        ("Disponibilidad", availability_text),
        ("Ruteo", routing_text),
    ]
    return headline, details


# ── Entrada ─────────────────────────────────────────────────────────────────


def require_api_key() -> None:
    """Verifica que exista GEMINI_API_KEY, que LiteLLM usa para los modelos "gemini/...".

    Side effects:
        Lee el entorno (ya cargado desde .env). Si falta la key imprime un error y
        termina el proceso con código 1.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        console.print(
            Panel.fit(
                "[bold red]Error:[/bold red] GEMINI_API_KEY no está definida.\n"
                "Ponla en el .env de la raíz del repo o expórtala en la terminal.",
                border_style="red",
            )
        )
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    """Lee `--runs N` (llamadas por modelo, por variante y por estrategia)."""
    parser = argparse.ArgumentParser(
        description="Router de LLMs con LiteLLM: costo, fallback y ruteo."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"llamadas por modelo / variante / estrategia (por defecto {DEFAULT_RUNS})",
    )
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs debe ser >= 1")
    return args


def main() -> None:
    """Corre las tres fases e imprime el resumen.

    Side effects:
        Llamadas de red a la API de Gemini vía LiteLLM; escribe en stdout.
    """
    args = parse_args()
    require_api_key()
    others = ", ".join(short(m) for m in MODELS if m != MODEL)
    console.print(
        Panel.fit(
            "[bold yellow]Router de LLMs con LiteLLM[/bold yellow]\n"
            "[dim]Una sola interfaz para varios modelos: costo por llamada, fallback y estrategias de ruteo.[/dim]\n"
            f"[dim]Modelo: {short(MODEL)} (+ {others}) | {args.runs} corridas por fase[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    models = run_models(args.runs)
    direct, routed = run_fallback(args.runs)
    strategies = asyncio.run(run_strategies(args.runs))
    print_summary(args.runs, models, direct, routed, strategies)


if __name__ == "__main__":
    main()
