"""LLMs estocásticos: la misma reseña, N corridas, tres formas de pedir el sentimiento.

Compara cuánto varía la salida de un LLM según cuánto se restringe:
  A) libre: se pide el análisis en lenguaje natural.
  B) JSON pedido en el prompt: el formato y las etiquetas solo se *piden*.
  C) response_schema: la API fuerza un JSON con un enum (Literal) de etiquetas.
"""

import argparse
import json
import os
import re
import textwrap
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

MODEL = "gemini-2.5-flash"
# Temperatura fija en las tres estrategias: así la única variable es la restricción.
TEMPERATURE = 0.7
DEFAULT_RUNS = 20
LOG_DIR = Path(__file__).resolve().parent / "corridas"

REVIEW = (
    "El envío tardó dos semanas y la caja llegó golpeada, pero el producto "
    "funciona perfecto y el soporte respondió rápido."
)

Sentimiento = Literal["positivo", "negativo", "neutro"]
ETIQUETAS: tuple[str, ...] = get_args(Sentimiento)


class AnalisisResena(BaseModel):
    """Esquema que la estrategia C entrega a la API como response_schema."""

    sentimiento: Sentimiento
    entidades: list[str]


@dataclass(frozen=True)
class Estrategia:
    """Una forma de pedirle al modelo el mismo análisis.

    Attributes:
        nombre: Etiqueta que se muestra en consola y en la tabla.
        archivo: Nombre del log de respuestas dentro de LOG_DIR.
        prompt: Texto que se envía al modelo.
        esquema: Si no es None, la API restringe la salida a un JSON que cumple
            este modelo Pydantic (decodificación restringida, no una petición).
    """

    nombre: str
    archivo: str
    prompt: str
    esquema: type[BaseModel] | None = None


PROMPT_LIBRE = (
    "Extrae el sentimiento y las entidades clave de esta reseña de un cliente: "
    f"'{REVIEW}'"
)
PROMPT_JSON = (
    f"{PROMPT_LIBRE}\n"
    "Responde solo con un objeto JSON con las claves 'sentimiento' y 'entidades'. "
    f"'sentimiento' debe ser un string ({', '.join(ETIQUETAS)}). "
    "'entidades' debe ser una lista de strings."
)
ESTRATEGIAS = (
    Estrategia("A: libre", "respuestas-libre.md", PROMPT_LIBRE),
    Estrategia("B: JSON en el prompt", "respuestas-json-prompt.md", PROMPT_JSON),
    Estrategia(
        "C: response_schema (enum)",
        "respuestas-response-schema.md",
        PROMPT_LIBRE,
        AnalisisResena,
    ),
)

console = Console()


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos automáticos.

    Returns:
        Un genai.Client autenticado que reintenta hasta 5 veces, con backoff,
        los errores 429 y 5xx.

    Side effects:
        Lee GEMINI_API_KEY del entorno (load_dotenv ya cargó <repo>/.env).

    Edge cases:
        Si falta la key, muestra un panel de error y termina con código 1.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel.fit(
                "[bold red]Falta GEMINI_API_KEY.[/bold red]\n"
                "Agrégala a <repo>/.env (GEMINI_API_KEY=...) o expórtala en la terminal.",
                title="Error",
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


def call_gemini(
    client: genai.Client, prompt: str, esquema: type[BaseModel] | None = None
) -> str:
    """Envía un prompt al modelo y devuelve su texto.

    Args:
        client: Cliente de get_gemini_client().
        prompt: Texto a enviar.
        esquema: Si se entrega, la respuesta se restringe a JSON con ese esquema.

    Returns:
        El texto de la respuesta sin espacios en los extremos; "" si el modelo
        no devolvió texto (p. ej. bloqueo de seguridad).

    Side effects:
        Una llamada de red síncrona (más los reintentos del cliente).

    Edge cases:
        Propaga google.genai.errors.APIError si fallan todos los reintentos.
    """
    config = types.GenerateContentConfig(
        temperature=TEMPERATURE,
        response_mime_type="application/json" if esquema else None,
        response_schema=esquema,
        # Sin tools: desactivar AFC evita un warning del SDK en cada ejecución.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = client.models.generate_content(
        model=MODEL, contents=prompt, config=config
    )
    return (response.text or "").strip()


def display_exchange(estrategia: Estrategia, response: str) -> None:
    """Muestra un intercambio de muestra (entrada y respuesta) en paneles.

    Args:
        estrategia: Estrategia cuyo prompt (y esquema, si tiene) se muestra.
        response: Texto devuelto por el modelo o descripción del error.

    Side effects:
        Escribe en stdout mediante la consola global de rich.
    """
    input_elements = [
        Text.assemble(
            ("USUARIO: ", "bold blue"),
            (_wrap(estrategia.prompt, indent=9), "blue"),
        )
    ]
    if estrategia.esquema is not None:
        campos = ", ".join(
            f"{nombre}: {repr(campo.annotation).replace('typing.', '')}"
            for nombre, campo in estrategia.esquema.model_fields.items()
        )
        firma = f"{estrategia.esquema.__name__}({campos})"
        input_elements.append(
            Text.assemble(
                ("\nESQUEMA: ", "bold magenta"),
                (_wrap(f"response_schema={firma}", indent=9), "magenta"),
            )
        )
    console.print(
        Panel(
            Group(*input_elements),
            title="[bold bright_black]Entrada al modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print()
    console.print(
        Panel(
            Text.assemble(
                ("MODELO: ", "bold green"), (_wrap(response, indent=8), "italic")
            ),
            title="[bold bright_black]Respuesta del modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


def _wrap(text: str, indent: int) -> str:
    """Ajusta el texto a 82 columnas con sangría colgante."""
    return textwrap.fill(text, width=82, subsequent_indent=" " * indent)


def run_experiment(
    client: genai.Client, estrategia: Estrategia, runs: int
) -> list[str]:
    """Ejecuta el mismo pedido `runs` veces y recolecta las respuestas.

    Args:
        client: Cliente de get_gemini_client().
        estrategia: Qué prompt (y esquema) enviar.
        runs: Número total de corridas; la primera se muestra completa.

    Returns:
        Las respuestas de las corridas exitosas, en orden. Las corridas cuya
        llamada falló tras los reintentos se omiten (punto rojo en la consola).

    Side effects:
        `runs` llamadas de red síncronas; escribe progreso en stdout.
    """
    console.print(
        f"[bold cyan]-- Estrategia {estrategia.nombre} "
        "--------------------------------------[/bold cyan]"
    )
    console.print(f"[dim]Ejecutando {runs} corridas...[/dim]")

    responses: list[str] = []
    last_error = ""
    for run in range(1, runs + 1):
        start = time.monotonic()
        try:
            response: str | None = call_gemini(
                client, estrategia.prompt, estrategia.esquema
            )
        except errors.APIError as exc:
            response = None
            last_error = f"{exc.code} {exc.status}"
        elapsed = time.monotonic() - start

        if response is not None:
            responses.append(response)
        if run == 1:
            display_exchange(
                estrategia,
                response if response is not None else f"Error de API: {last_error}",
            )
            console.print("  [dim]Recolectando el resto de las respuestas:[/dim]")
            continue

        dot = "[green]o[/green]" if response is not None else "[red]o[/red]"
        console.print(
            f"  Corrida #{run:02d}: {dot} [dim]{elapsed:4.1f}s[/dim]",
            end="   ",
            highlight=False,
        )
        if run % 4 == 0:
            console.print()

    if runs % 4 != 0:
        console.print()
    if len(responses) < runs:
        console.print(
            f"  [red]{runs - len(responses)} corrida(s) fallaron tras los reintentos "
            f"(último error: {last_error}).[/red]"
        )
    console.print()
    return responses


def _parse_json(text: str) -> object | None:
    """Devuelve el JSON contenido en `text` (aceptando un bloque ```json), o None."""
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    try:
        return json.loads(match.group(1) if match else text)
    except json.JSONDecodeError:
        return None


def content_key(text: str) -> str:
    """Forma canónica de una respuesta, para decidir si dos respuestas son iguales.

    Dos respuestas cuentan como la misma si dicen lo mismo: el mismo JSON
    (ignorando espacios, orden de claves y el bloque ``` que lo envuelva) o el
    mismo texto (ignorando espacios y saltos de línea). Así el formato no infla
    la varianza de ninguna estrategia.
    """
    data = _parse_json(text)
    if data is not None:
        return json.dumps(data, ensure_ascii=False, sort_keys=True)
    return " ".join(text.split())


def sentiment_label(text: str) -> str | None:
    """Etiqueta de sentimiento de una respuesta JSON, o None si no hay una legible."""
    data = _parse_json(text)
    if isinstance(data, dict) and isinstance(data.get("sentimiento"), str):
        return str(data["sentimiento"])
    return None


def matches_schema(text: str) -> bool:
    """True si `text`, tal cual llegó, es un JSON válido según AnalisisResena."""
    try:
        AnalisisResena.model_validate_json(text)
    except ValidationError:
        return False
    return True


@dataclass(frozen=True)
class Metricas:
    """Métricas de una estrategia sobre sus corridas exitosas.

    Attributes:
        total: Corridas con respuesta.
        unique_count: Respuestas distintas según content_key.
        consistency_pct: % de corridas que dieron la respuesta más frecuente
            (0.0 si no hubo respuestas).
        sentimientos: Conteo de etiquetas de sentimiento legibles.
        schema_ok: Respuestas que cumplen AnalisisResena sin limpiarlas.
    """

    total: int
    unique_count: int
    consistency_pct: float
    sentimientos: Counter[str]
    schema_ok: int


def calculate_metrics(responses: list[str]) -> Metricas:
    """Calcula respuestas únicas, consistencia y distribución del sentimiento.

    Args:
        responses: Respuestas de una estrategia (puede estar vacía).

    Returns:
        Las Metricas de esas respuestas.
    """
    counts = Counter(content_key(r) for r in responses)
    most_common = counts.most_common(1)[0][1] if counts else 0
    labels = (sentiment_label(r) for r in responses)
    return Metricas(
        total=len(responses),
        unique_count=len(counts),
        consistency_pct=100 * most_common / len(responses) if responses else 0.0,
        sentimientos=Counter(label for label in labels if label is not None),
        schema_ok=sum(matches_schema(r) for r in responses),
    )


def log_responses_to_file(estrategia: Estrategia, responses: list[str]) -> Path:
    """Escribe el prompt y todas las respuestas de una estrategia en Markdown.

    Returns:
        La ruta del archivo escrito (LOG_DIR/estrategia.archivo).

    Side effects:
        Crea LOG_DIR si no existe y sobrescribe el archivo.
    """
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / estrategia.archivo
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# Prompt\n\n```text\n{estrategia.prompt}\n```\n\n# Respuestas\n\n")
        for i, response in enumerate(responses, 1):
            f.write(f"## Corrida {i}\n\n````text\n{response}\n````\n\n")
    return path


def _delta(value: float, base: float, lower_is_better: bool, fmt: str) -> str:
    """Formatea la diferencia contra la estrategia A con `fmt`, en verde si mejora."""
    diff = value - base
    if diff == 0:
        return "[dim](+/-0)[/dim]"
    color = "green" if (diff < 0) == lower_is_better else "red"
    return f"[{color}]({fmt.format(diff)})[/{color}]"


def _distribution(m: Metricas) -> str:
    """Conteo de sentimientos como texto; marca etiquetas que no están en el enum."""
    if not m.sentimientos:
        return "[dim]no medible\n(texto libre)[/dim]"
    parts = []
    for label, count in m.sentimientos.most_common():
        mark = "" if label in ETIQUETAS else " [red](fuera del enum)[/red]"
        parts.append(f"{label} {count}{mark}")
    return "\n".join(parts)


def print_summary(metrics: list[Metricas], runs: int) -> None:
    """Imprime la tabla comparativa y un veredicto calculado desde los datos.

    Args:
        metrics: Métricas de las estrategias A, B y C, en ese orden.
        runs: Corridas pedidas por estrategia.

    Side effects:
        Escribe en stdout mediante la consola global de rich.
    """
    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    console.print()

    base = metrics[0]
    table = Table(title="Varianza según la restricción", show_lines=True)
    table.add_column("Métrica", style="bold", min_width=26)
    for estrategia, color in zip(ESTRATEGIAS, ("cyan", "magenta", "green")):
        table.add_column(estrategia.nombre, justify="center", style=color)

    table.add_row(
        "Respuestas únicas",
        str(base.unique_count),
        *[
            f"{m.unique_count} "
            f"{_delta(m.unique_count, base.unique_count, True, '{:+.0f}')}"
            for m in metrics[1:]
        ],
    )
    table.add_row(
        "Consistencia (%)",
        f"{base.consistency_pct:.1f}%",
        *[
            f"{m.consistency_pct:.1f}% "
            f"{_delta(m.consistency_pct, base.consistency_pct, False, '{:+.1f}%')}"
            for m in metrics[1:]
        ],
    )
    table.add_row("Sentimiento (conteo)", *[_distribution(m) for m in metrics])
    table.add_row(
        "Cumple el esquema tal cual", *[f"{m.schema_ok}/{m.total}" for m in metrics]
    )
    table.add_row("Corridas exitosas", *[f"{m.total}/{runs}" for m in metrics])
    console.print(table)
    console.print()
    console.print(_verdict(metrics))
    console.print()


def _verdict(metrics: list[Metricas]) -> str:
    """Veredicto de una línea comparando la consistencia de B y C contra A."""
    a, b, c = (m.consistency_pct for m in metrics)
    detail = (
        f"consistencia: libre {a:.0f}% → JSON en prompt {b:.0f}%, "
        f"response_schema {c:.0f}%"
    )
    if min(b, c) > a:
        return (
            "[bold green]VEREDICTO: restringir la salida concentró la masa de "
            f"probabilidad ({detail}).[/bold green]"
        )
    if max(b, c) > a:
        return (
            "[bold yellow]VEREDICTO: solo una de las restricciones redujo la "
            f"varianza en esta corrida ({detail}).[/bold yellow]"
        )
    return (
        "[bold red]VEREDICTO: en esta corrida restringir no redujo la varianza "
        f"({detail}).[/bold red]"
    )


def main() -> None:
    """Corre las tres estrategias, guarda sus respuestas y muestra la comparación.

    Side effects:
        Llamadas de red a Gemini; escribe los logs en LOG_DIR y la salida en stdout.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"corridas por estrategia (default {DEFAULT_RUNS}; mínimo 2)",
    )
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs debe ser al menos 2 para comparar respuestas")

    client = get_gemini_client()
    console.print(
        Panel.fit(
            "[bold yellow]LLMs estocásticos: sentimiento libre vs restringido[/bold yellow]\n"
            "[dim]Misma reseña, mismas corridas: ¿cuánto varía la salida según cuánto "
            "la restringimos?[/dim]\n"
            f"[dim]Modelo: {MODEL} | {args.runs} corridas por estrategia[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    metrics: list[Metricas] = []
    for estrategia in ESTRATEGIAS:
        responses = run_experiment(client, estrategia, args.runs)
        log_responses_to_file(estrategia, responses)
        metrics.append(calculate_metrics(responses))

    print_summary(metrics, args.runs)
    console.print(
        f"[dim]Todas las respuestas quedaron en {LOG_DIR.name}/ "
        "(una por estrategia).[/dim]"
    )


if __name__ == "__main__":
    main()
