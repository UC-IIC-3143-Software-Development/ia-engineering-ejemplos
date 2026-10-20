#!/usr/bin/env python3
"""
Prototipo: salidas estructuradas — pedir JSON vs modo estructurado
==================================================================
El MISMO prompt se envía con tres configuraciones de llamada:

  A. JSON en el prompt  — solo se pide "devuelve un JSON con ..." en el texto.
  B. JSON mode          — response_mime_type="application/json".
  C. Modo estructurado  — JSON mode + response_schema=<modelo Pydantic>.

Cada respuesta pasa por el mismo pipeline: json.loads directo, json.loads tras
limpiar (quitar ``` y prosa), validación contra el contrato Pydantic y un eval
contra la salida esperada del caso. Se anotan los gotchas vistos en el camino.

Regla de diseño del contrato:
  - una etiqueta de un set fijo -> enum (Literal)        -> Ticket
  - datos con varios campos     -> modelo Pydantic plano -> Pedido

La Fase 2 rompe el contrato a propósito (un "prompt v2" sin esquema) para
mostrar la ValidationError que se atrapa en el borde, antes del sistema
downstream.

Concepto: pedir JSON en el prompt es una sugerencia; response_schema es un
contrato. El esquema garantiza la forma, no los valores: eso lo cubren los evals.
"""

import argparse
import inspect
import json
import os
import re
import textwrap
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal, get_origin

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import ErrorDetails
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

console = Console()

MODEL = "gemini-2.5-flash"
DEFAULT_RUNS = 10
LOG_DIR = Path(__file__).resolve().parent / "respuestas"


# ── Contratos ─────────────────────────────────────────────────────────────────


class Ticket(BaseModel):
    """Una etiqueta de un set fijo -> enum."""

    categoria: Literal["facturacion", "soporte_tecnico", "ventas", "otro"]


class Pedido(BaseModel):
    """Varios campos -> modelo Pydantic plano (sin anidar)."""

    cliente: str
    items: list[str]
    total: float
    moneda: Literal["CLP", "USD"]
    fecha_entrega: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


# ── Prompts (idénticos para las tres estrategias) ─────────────────────────────

# Escritos como se suele pedir en la práctica: el formato va descrito en prosa.
TICKET_PROMPT = (
    "Te paso un ticket de soporte. ¿Me lo clasificas en JSON? Usa la clave "
    '"categoria" con uno de estos valores: facturacion, soporte_tecnico, ventas u otro.'
    "\n\nTicket: {texto}"
)

PEDIDO_PROMPT = (
    "Te paso un pedido de un cliente. ¿Me extraes los datos en JSON? Necesito "
    "cliente, items (lista de productos), total (número), moneda (CLP o USD) y "
    "fecha_entrega (YYYY-MM-DD).\n\nPedido: {texto}"
)

# Fase 2: alguien "mejora" el prompt y cambia la forma de la salida sin tocar
# el código que la consume. Es el equivalente al especialista v2 roto.
PEDIDO_PROMPT_V2 = (
    "Te paso un pedido de un cliente. ¿Me extraes los datos en JSON? Necesito "
    "cliente, productos (un solo texto separado por comas), monto (tal como "
    "aparece en el pedido, con símbolo) y fecha (tal como aparece en el texto)."
    "\n\nPedido: {texto}"
)


# ── Set de evals: entrada + salida esperada ───────────────────────────────────


@dataclass(frozen=True)
class Case:
    """Un caso del set de evals.

    Attributes:
        case_id: Etiqueta corta que se muestra en la columna de puntos.
        label: Qué prueba el caso (para la tabla de evals).
        contract: Modelo Pydantic que la respuesta debe cumplir.
        texto: Texto del cliente que se inserta en el prompt.
        template: Prompt con un marcador {texto}.
        expected: Campos que compara el eval y su valor esperado. Los floats
            se comparan con tolerancia 0.01; los str sin distinguir mayúsculas;
            None exige null. `items` es redacción libre y no se evalúa.
    """

    case_id: str
    label: str
    contract: type[BaseModel]
    texto: str
    template: str
    expected: dict[str, str | float | None]

    @property
    def prompt(self) -> str:
        """Prompt final enviado al modelo."""
        return self.template.format(texto=self.texto)


def ticket(case_id: str, label: str, texto: str, categoria: str) -> Case:
    """Crea un caso de clasificación (contrato Ticket)."""
    return Case(case_id, label, Ticket, texto, TICKET_PROMPT, {"categoria": categoria})


def pedido(
    case_id: str,
    label: str,
    texto: str,
    cliente: str,
    total: float,
    moneda: str,
    fecha: str | None,
) -> Case:
    """Crea un caso de extracción (contrato Pedido)."""
    expected: dict[str, str | float | None] = {
        "cliente": cliente,
        "total": total,
        "moneda": moneda,
        "fecha_entrega": fecha,
    }
    return Case(case_id, label, Pedido, texto, PEDIDO_PROMPT, expected)


CASES: list[Case] = [
    ticket(
        "T1", "cobro doble",
        "Me cobraron dos veces la suscripción de este mes, necesito que "
        "reviertan un cargo.",
        "facturacion",
    ),
    ticket(
        "T2", "app se cierra",
        "La app se cierra sola cada vez que intento subir una foto de perfil "
        "desde el iPhone.",
        "soporte_tecnico",
    ),
    ticket(
        "T3", "plan empresa",
        "¿Tienen un plan empresa para 50 personas? Necesitamos una cotización formal.",
        "ventas",
    ),
    ticket(
        "T4", "felicitación",
        "Solo quería felicitar a la ejecutiva que me atendió ayer, fue muy amable.",
        "otro",
    ),
    pedido(
        "P1", "$34.990 (punto de miles)",
        "Pedido de María Pérez: 2 poleras negras talla M y 1 gorro de lana. "
        "Total a pagar $34.990 pesos chilenos. Entregar el 15 de octubre de 2026.",
        "María Pérez", 34990.0, "CLP", "2026-10-15",
    ),
    pedido(
        "P2", "USD, nombre en inglés",
        "Hola, soy John Smith. Quiero 3 tazas de cerámica a USD 12 cada una, "
        "USD 36 en total. Envío para el 2 de noviembre de 2026.",
        "John Smith", 36.0, "USD", "2026-11-02",
    ),
    pedido(
        "P3", "'650 mil', fecha dd/mm/aaaa",
        "Para Camila Rojas: 1 notebook y 2 mouse inalámbricos. Son 650 mil pesos. "
        "Despacho 01/12/2026.",
        "Camila Rojas", 650000.0, "CLP", "2026-12-01",
    ),
    pedido(
        "P4", "US$ 1.250,50 (coma decimal)",
        "Cliente: Pedro González. Compra de 5 licencias de software por "
        "US$ 1.250,50 en total. Activación el viernes 4 de diciembre de 2026.",
        "Pedro González", 1250.5, "USD", "2026-12-04",
    ),
    # Caso trampa: el texto no trae fecha, pero el contrato la exige.
    pedido(
        "P5", "sin fecha (trampa)",
        "Pedido de Diego Fuentes: 4 cuadernos universitarios y 1 estuche, total "
        "$12.000. Lo retira él mismo en tienda, todavía no sabe qué día.",
        "Diego Fuentes", 12000.0, "CLP", None,
    ),
]

SAMPLE_CASE = CASES[4]  # P1: el intercambio de muestra de cada estrategia


# ── Estrategias ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Strategy:
    """Una configuración de llamada; el prompt es el mismo en las tres."""

    key: str
    name: str
    json_mode: bool
    use_schema: bool

    def config(self, contract: type[BaseModel]) -> types.GenerateContentConfig:
        """Config de generate_content para esta estrategia.

        Args:
            contract: Modelo Pydantic del caso; solo se envía si use_schema.

        Returns:
            La config lista para la llamada. AFC queda desactivado porque no
            hay tools (evita un aviso irrelevante del SDK).
        """
        return types.GenerateContentConfig(
            response_mime_type="application/json" if self.json_mode else None,
            response_schema=contract if self.use_schema else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def describe(self, contract: type[BaseModel]) -> str:
        """Resumen legible de la config, para el panel de entrada."""
        parts = []
        if self.json_mode:
            parts.append('response_mime_type="application/json"')
        if self.use_schema:
            parts.append(f"response_schema={contract.__name__}")
        return ", ".join(parts) or "(sin configuración de salida: solo el prompt)"


STRATEGIES = [
    Strategy("A", "JSON en el prompt", json_mode=False, use_schema=False),
    Strategy("B", "JSON mode", json_mode=True, use_schema=False),
    Strategy("C", "Modo estructurado", json_mode=True, use_schema=True),
]


# ── Pipeline de parseo, validación y eval ─────────────────────────────────────

GOTCHAS = {
    "fence": "Bloque ``` alrededor del JSON",
    "prosa": "Prosa antes/después del JSON",
    "omitido": "Campo omitido o null",
    "anidado": "Anidó objetos en un contrato plano",
    "enum": "Valor fuera del enum",
    "tipo": "Otro tipo o formato incorrecto",
}

FENCE_RE = re.compile(r"```(?:json)?")


@dataclass(frozen=True)
class Outcome:
    """Una respuesta del modelo ya pasada por el pipeline.

    Cada etapa implica la anterior: correct => valid => json_clean.
    `failure` es un motivo corto (None si pasó el eval).
    """

    text: str
    seconds: float
    api_error: bool
    json_direct: bool
    json_clean: bool
    valid: bool
    correct: bool
    gotchas: frozenset[str]
    failure: str | None


def try_json(text: str) -> tuple[bool, object]:
    """Intenta json.loads sin lanzar.

    Returns:
        (True, valor) si el texto es JSON válido; (False, None) si no.
    """
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, None


def gotcha_of(err: ErrorDetails) -> str | None:
    """Clasifica un error de Pydantic en una clave de GOTCHAS.

    Returns:
        None para "missing" y valores null: esos los cuenta grade() como
        "omitido" mirando el JSON, no el error.
    """
    if err["type"] == "missing" or err["input"] is None:
        return None
    if err["type"] == "literal_error":
        return "enum"
    return "anidado" if isinstance(err["input"], (dict, list)) else "tipo"


def describe_error(err: ErrorDetails) -> str:
    """Motivo corto de un error de Pydantic, p. ej. "total: tipo (str)".

    Args:
        err: Un elemento de ValidationError.errors().
    """
    loc = ".".join(str(part) for part in err["loc"])
    kind, value = err["type"], err["input"]
    if kind == "missing":
        return f"{loc}: falta"
    if value is None:
        return f"{loc}: null"
    if kind == "literal_error":
        return f"{loc}: fuera del enum ({value!r})"
    if kind == "string_pattern_mismatch":
        return f"{loc}: formato ({value!r})"
    if isinstance(value, (dict, list)):
        return f"{loc}: anidado ({type(value).__name__})"
    return f"{loc}: tipo ({type(value).__name__})"


def describe_validation(exc: ValidationError) -> str:
    """Primer error de cada campo de nivel superior, unidos con " · "."""
    by_field: dict[object, str] = {}
    for err in exc.errors():
        by_field.setdefault(err["loc"][0], describe_error(err))
    return " · ".join(by_field.values())


def eval_mismatch(obj: BaseModel, expected: dict[str, str | float | None]) -> str | None:
    """Compara una salida válida con la esperada.

    Returns:
        None si todos los campos coinciden; si no, el primer campo distinto
        con el valor observado, p. ej. "total=34.99".
    """
    for name, want in expected.items():
        got = getattr(obj, name)
        if want is None:
            same = got is None
        elif isinstance(want, float):
            same = abs(float(got) - want) < 0.01
        else:
            same = str(got).strip().casefold() == want.casefold()
        if not same:
            return f"{name}={got!r}"
    return None


def grade(text: str, case: Case, seconds: float) -> Outcome:
    """Pasa una respuesta cruda por el pipeline completo.

    Args:
        text: Texto tal como lo devolvió el modelo.
        case: Caso con el contrato y la salida esperada.
        seconds: Latencia de la llamada (solo se registra).

    Returns:
        El Outcome con cada etapa y los gotchas detectados.

    Edge cases:
        Un valor null en un campo requerido cuenta como "omitido", no como
        "tipo", aunque Pydantic lo reporte como error de tipo.
    """
    gotchas: set[str] = set()
    if "```" in text:
        gotchas.add("fence")
    body = FENCE_RE.sub("", text).strip()
    if body and not (body.startswith("{") and body.endswith("}")):
        gotchas.add("prosa")

    json_direct, _ = try_json(text)
    start, end = body.find("{"), body.rfind("}")
    json_clean, data = try_json(body[start : end + 1]) if 0 <= start < end else (False, None)

    def outcome(valid: bool, correct: bool, failure: str | None) -> Outcome:
        return Outcome(
            text, seconds, False, json_direct, json_clean, valid, correct,
            frozenset(gotchas), failure,
        )

    if not json_clean:
        return outcome(False, False, "no hay JSON parseable")
    if isinstance(data, dict) and any(
        data.get(name) is None for name in case.contract.model_fields
    ):
        gotchas.add("omitido")

    try:
        obj = case.contract.model_validate(data)
    except ValidationError as exc:
        gotchas.update(g for g in map(gotcha_of, exc.errors()) if g)
        return outcome(False, False, describe_validation(exc))

    mismatch = eval_mismatch(obj, case.expected)
    return outcome(True, mismatch is None, mismatch)


# ── Llamadas al modelo ────────────────────────────────────────────────────────


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos para 429/5xx.

    Returns:
        Un genai.Client autenticado con GEMINI_API_KEY.

    Side effects:
        Lee GEMINI_API_KEY del entorno (o de <repo>/.env vía python-dotenv).

    Edge cases:
        Si falta la key imprime un panel de error y termina con SystemExit(1).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel.fit(
                "[bold red]Error:[/bold red] GEMINI_API_KEY no está definida.\n"
                "Agrégala a <repo>/.env (GEMINI_API_KEY=...) o expórtala en la terminal.",
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


def call_model(
    client: genai.Client, prompt: str, config: types.GenerateContentConfig
) -> tuple[str, float]:
    """Una llamada a generate_content.

    Returns:
        (texto, segundos). El texto es "" si el modelo no devolvió texto.

    Raises:
        google.genai.errors.APIError: si la API falla tras los reintentos.
    """
    start = time.perf_counter()
    response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
    return response.text or "", time.perf_counter() - start


def run_case(client: genai.Client, strategy: Strategy, case: Case) -> Outcome:
    """Llama al modelo para un caso con una estrategia y califica la respuesta.

    Side effects:
        Una llamada de red a la API de Gemini.

    Edge cases:
        Un APIError no se propaga: se registra como Outcome con api_error=True
        (punto rojo) para que una falla puntual no aborte la demo.
    """
    try:
        text, seconds = call_model(client, case.prompt, strategy.config(case.contract))
    except errors.APIError as exc:
        return Outcome(
            f"Error de API: {exc}", 0.0, True, False, False, False, False,
            frozenset(), "error de API",
        )
    return grade(text, case, seconds)


# ── Presentación ──────────────────────────────────────────────────────────────


def wrap(text: str, indent: int) -> str:
    """Ajusta cada línea a 82 columnas conservando los saltos de línea."""
    pad = " " * indent
    lines = [
        textwrap.fill(line, width=82, subsequent_indent=pad) if line.strip() else ""
        for line in text.splitlines() or [""]
    ]
    return ("\n" + pad).join(lines)


def display_exchange(prompt: str, config_desc: str, response: str) -> None:
    """Imprime un intercambio de muestra (entrada + config, respuesta cruda).

    Side effects:
        Escribe dos paneles de rich en stdout.
    """
    console.print(
        Panel(
            Group(
                Text.assemble(("USER: ", "bold blue"), (wrap(prompt, 6), "blue")),
                Text(),
                Text.assemble(("CONFIG: ", "bold magenta"), (config_desc, "magenta")),
            ),
            title="[bold bright_black]Entrada al modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print(
        Panel(
            Text.assemble(("ASSISTANT: ", "bold green"), (wrap(response, 11), "italic")),
            title="[bold bright_black]Respuesta del modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
            highlight=False,
        )
    )
    console.print()


def dot(outcome: Outcome) -> str:
    """Punto de progreso: verde pasa el eval, amarillo cumple contrato, rojo no."""
    color = "green" if outcome.correct else "yellow" if outcome.valid else "red"
    return f"[{color}]●[/{color}]"


def log_responses(strategy: Strategy, results: list[list[Outcome]]) -> Path:
    """Guarda todas las respuestas crudas de una estrategia en Markdown.

    Returns:
        La ruta del archivo escrito.

    Side effects:
        Crea respuestas/ junto a este script y sobrescribe
        respuestas/estrategia-<X>.md.
    """
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"estrategia-{strategy.key}.md"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# Estrategia {strategy.key}: {strategy.name}\n\n")
        for run, outcomes in enumerate(results, 1):
            for case, o in zip(CASES, outcomes):
                status = "OK" if o.correct else o.failure
                f.write(f"## Corrida {run} · {case.case_id} · {status}\n\n")
                f.write(f"```text\n{o.text}\n```\n\n")
    return path


def run_strategy(
    client: genai.Client, strategy: Strategy, runs: int
) -> list[list[Outcome]]:
    """Corre el set de evals `runs` veces con una estrategia.

    Dentro de cada corrida los casos se llaman en paralelo; las corridas van
    en secuencia.

    Returns:
        Una lista por corrida con un Outcome por caso, en el orden de CASES.

    Side effects:
        runs × len(CASES) llamadas de red; imprime el intercambio de muestra,
        un renglón de puntos por corrida y escribe el log de respuestas.
    """
    console.print(
        f"[bold cyan]-- Estrategia {strategy.key}: {strategy.name} "
        "--------------------------------------[/bold cyan]"
    )
    console.print(f"[dim]{runs} corridas × {len(CASES)} casos...[/dim]")

    results: list[list[Outcome]] = []
    header = "".join(f"{case.case_id:<3}" for case in CASES)
    with ThreadPoolExecutor(max_workers=len(CASES)) as pool:
        for run in range(1, runs + 1):
            start = time.perf_counter()
            outcomes = list(pool.map(partial(run_case, client, strategy), CASES))
            elapsed = time.perf_counter() - start
            results.append(outcomes)

            if run == 1:
                sample = outcomes[CASES.index(SAMPLE_CASE)]
                display_exchange(
                    SAMPLE_CASE.prompt, strategy.describe(SAMPLE_CASE.contract), sample.text
                )
                console.print(f"  [dim]{'Caso:':<13}{header}[/dim]")

            dots = "".join(f"{dot(o)}  " for o in outcomes)
            console.print(
                f"  Corrida #{run:02d}: {dots}[dim]{elapsed:4.1f}s[/dim]", highlight=False
            )

    path = log_responses(strategy, results)
    console.print(f"  [dim]Respuestas crudas en {LOG_DIR.name}/{path.name}[/dim]")
    console.print()
    return results


def type_label(field: FieldInfo) -> str:
    """Tipo esperado de un campo en forma legible (incluye el pattern si hay)."""
    ann = field.annotation
    if get_origin(ann) is None and isinstance(ann, type):
        label = ann.__name__
    else:
        label = str(ann).replace("typing.", "")
    patterns = [p for p in (getattr(m, "pattern", None) for m in field.metadata) if p]
    return f"{label} {patterns[0]}" if patterns else label


def display_validation_failure(
    error: ValidationError, raw: dict[str, object], contract: type[BaseModel]
) -> None:
    """Imprime el mapeo campo a campo y la lista de errores de Pydantic.

    Args:
        error: La ValidationError atrapada.
        raw: El dict que se intentó validar.
        contract: El modelo Pydantic esperado.

    Side effects:
        Escribe una tabla y una lista de errores en stdout.
    """
    console.print(Rule("[bold red]Contrato roto — ValidationError[/bold red]", style="red"))
    console.print()

    errors_by_field: dict[str, str] = {}
    for err in error.errors():
        errors_by_field.setdefault(str(err["loc"][0]), err["msg"])

    table = Table(title=f"Mapeo de campos de {contract.__name__}", show_lines=True)
    table.add_column("Campo", style="bold")
    table.add_column("Estado", justify="center")
    table.add_column("Esperado", style="dim")
    table.add_column("Recibido / detalle", style="dim", max_width=46)

    for name, field in contract.model_fields.items():
        if name not in raw:
            status, detail = "[red]FALTA[/red]", "—"
        elif name in errors_by_field:
            status, detail = "[red]INVÁLIDO[/red]", f"{raw[name]!r}: {errors_by_field[name]}"
        else:
            status, detail = "[green]OK[/green]", repr(raw[name])
        table.add_row(name, status, type_label(field), detail)
    for extra in (key for key in raw if key not in contract.model_fields):
        table.add_row(extra, "[yellow]EXTRA[/yellow]", "—", repr(raw[extra]))

    console.print(table)
    console.print()
    console.print("[bold red]Errores de Pydantic:[/bold red]")
    for err in error.errors():
        loc = " -> ".join(str(part) for part in err["loc"])
        console.print(f"  [dim]•[/dim] [bold]{loc}[/bold]: [red]{err['msg']}[/red]")
    console.print()


def run_contract_break(client: genai.Client) -> None:
    """Fase 2: un prompt v2 cambia la forma de la salida y el contrato lo atrapa.

    Llama al prompt v2 en JSON mode (sin esquema) y valida contra Pedido;
    luego repite el mismo prompt v2 con response_schema=Pedido.

    Side effects:
        Dos llamadas de red; imprime paneles, la tabla de ValidationError y
        el resultado con esquema.
    """
    console.print(Rule("[bold]Fase 2 — Contrato roto: prompt v2 sin esquema[/bold]", style="white"))
    console.print()
    console.print(
        "[dim]Alguien \"mejora\" el prompt de extracción: ahora pide 'productos', "
        "'monto' y 'fecha'. El código que consume la salida sigue esperando Pedido.[/dim]\n"
    )
    prompt = PEDIDO_PROMPT_V2.format(texto=SAMPLE_CASE.texto)
    json_mode, structured = STRATEGIES[1], STRATEGIES[2]

    try:
        text, _ = call_model(client, prompt, json_mode.config(Pedido))
    except errors.APIError as exc:
        console.print(f"[bold red]Error de API en la Fase 2:[/bold red] {exc}")
        return
    display_exchange(prompt, json_mode.describe(Pedido), text)

    console.print("[bold yellow]  Validando la respuesta contra el contrato Pedido...[/bold yellow]\n")
    ok, raw = try_json(text)
    if not ok or not isinstance(raw, dict):
        console.print("[bold red]La respuesta v2 ni siquiera es un objeto JSON.[/bold red]\n")
    else:
        try:
            Pedido.model_validate(raw)
            console.print("[bold yellow]El prompt v2 no rompió el contrato en esta corrida.[/bold yellow]\n")
        except ValidationError as exc:
            display_validation_failure(exc, raw, Pedido)
            console.print(
                "[bold green]✓ El contrato detuvo la respuesta v2 en el borde: "
                "nada llegó al sistema downstream.[/bold green]\n"
            )

    try:
        text, _ = call_model(client, prompt, structured.config(Pedido))
    except errors.APIError as exc:
        console.print(f"[bold red]Error de API en la Fase 2:[/bold red] {exc}")
        return
    try:
        fixed = Pedido.model_validate_json(text)
        console.print(
            "[bold]Mismo prompt v2 con response_schema=Pedido:[/bold] "
            "[green]cumple el contrato[/green] "
            f"[dim]{fixed.model_dump_json()}[/dim]\n",
            highlight=False,
        )
    except ValidationError as exc:
        console.print(
            "[bold]Mismo prompt v2 con response_schema=Pedido:[/bold] "
            f"[red]tampoco cumple ({describe_validation(exc)})[/red]\n"
        )


# ── Resumen ───────────────────────────────────────────────────────────────────


def rate_cell(hits: int, total: int, with_pct: bool = True) -> str:
    """Celda "k/n (p%)" (o "k/n") coloreada: verde 100 %, amarillo >= 50 %, rojo < 50 %."""
    pct = 100 * hits / total
    color = "green" if hits == total else "yellow" if pct >= 50 else "red"
    text = f"{hits}/{total} ({pct:.0f}%)" if with_pct else f"{hits}/{total}"
    return f"[{color}]{text}[/{color}]"


def count_cell(count: int) -> str:
    """Celda de conteo de gotchas: tenue si es cero, roja si no."""
    return "[dim]0[/dim]" if count == 0 else f"[red]{count}[/red]"


def print_metrics_table(flat: dict[str, list[Outcome]]) -> None:
    """Tabla de métricas A/B/C sobre todas las respuestas de cada estrategia.

    Args:
        flat: Por clave de estrategia, todos sus Outcomes (corridas × casos).

    Side effects:
        Escribe la tabla en stdout.
    """
    table = Table(title="Pedir JSON vs modo estructurado", show_lines=True)
    table.add_column("Métrica", style="bold", min_width=30)
    for s in STRATEGIES:
        table.add_column(f"{s.key}: {s.name}", justify="center")

    stages = [
        ("JSON válido directo (json.loads)", lambda o: o.json_direct),
        ("JSON válido tras limpiar ``` y prosa", lambda o: o.json_clean),
        ("Cumple el contrato (Pydantic)", lambda o: o.valid),
        ("Pasa el eval (salida esperada)", lambda o: o.correct),
    ]
    for label, stage in stages:
        table.add_row(
            label,
            *(rate_cell(sum(stage(o) for o in flat[s.key]), len(flat[s.key])) for s in STRATEGIES),
        )
    for key, label in GOTCHAS.items():
        table.add_row(
            f"Gotcha: {label}",
            *(count_cell(sum(key in o.gotchas for o in flat[s.key])) for s in STRATEGIES),
        )
    table.add_row(
        "Errores de API",
        *(count_cell(sum(o.api_error for o in flat[s.key])) for s in STRATEGIES),
    )
    table.add_row(
        "Latencia promedio por llamada",
        *(
            f"{sum(o.seconds for o in flat[s.key]) / len(flat[s.key]):.1f}s"
            for s in STRATEGIES
        ),
    )
    console.print(table)
    console.print()


def expected_label(value: str | float | None) -> str:
    """Valor esperado tal como se muestra en la tabla de evals."""
    if value is None:
        return "sin fecha (null)"
    return f"{value:g}" if isinstance(value, float) else value


def print_evals_table(all_results: dict[str, list[list[Outcome]]], runs: int) -> None:
    """Tabla del set de evals: aciertos por caso y estrategia, y su fallo típico.

    Args:
        all_results: Por clave de estrategia, sus resultados por corrida.
        runs: Número de corridas (denominador de cada celda).

    Side effects:
        Escribe la tabla en stdout.
    """
    table = Table(title="Evals: set de casos con salida esperada", show_lines=True)
    table.add_column("Caso", style="bold", max_width=16)
    table.add_column("Esperado", max_width=24)
    for s in STRATEGIES:
        table.add_column(s.key, justify="center")
    table.add_column("Fallo más frecuente por estrategia", style="dim")

    for i, case in enumerate(CASES):
        per_strategy = {s.key: [run[i] for run in all_results[s.key]] for s in STRATEGIES}
        worst = []
        for key, outcomes in per_strategy.items():
            failures = Counter(o.failure for o in outcomes if not o.correct)
            if failures:
                reason, count = failures.most_common(1)[0]
                worst.append(f"{key}: {reason} (×{count})")
        table.add_row(
            f"{case.case_id} {case.label}",
            " · ".join(expected_label(v) for v in case.expected.values()),
            *(
                rate_cell(sum(o.correct for o in per_strategy[s.key]), runs, with_pct=False)
                for s in STRATEGIES
            ),
            "\n".join(worst) or "—",
        )
    console.print(table)
    console.print()


def verdict(flat: dict[str, list[Outcome]]) -> list[str]:
    """Líneas de veredicto calculadas desde los datos (contrato y evals).

    Returns:
        Dos líneas con markup de rich: cumplimiento del contrato y evals.
    """

    def pct(key: str, stage: str) -> float:
        outcomes = flat[key]
        return 100 * sum(getattr(o, stage) for o in outcomes) / len(outcomes)

    a, b, c = (pct(s.key, "valid") for s in STRATEGIES)
    direct_a = pct("A", "json_direct")
    if c > max(a, b):
        line1 = (
            f"[bold green]VEREDICTO: el modo estructurado cumplió el contrato en {c:.0f}% "
            f"de las respuestas; JSON mode {b:.0f}% y JSON en el prompt {a:.0f}% "
            f"(json.loads directo sobre A: {direct_a:.0f}%).[/bold green]"
        )
    elif c == max(a, b):
        line1 = (
            f"[bold yellow]VEREDICTO: en esta corrida C empató con la mejor alternativa "
            f"en cumplimiento del contrato ({c:.0f}%; A {a:.0f}%, B {b:.0f}%). "
            f"json.loads directo sobre A: {direct_a:.0f}%.[/bold yellow]"
        )
    else:
        line1 = (
            f"[bold red]VEREDICTO: inesperado: C cumplió el contrato en {c:.0f}% "
            f"vs A {a:.0f}% y B {b:.0f}%.[/bold red]"
        )

    ea, eb, ec = (pct(s.key, "correct") for s in STRATEGIES)
    wrong_c = sum(o.valid and not o.correct for o in flat["C"])
    tail = (
        f"{wrong_c} respuestas de C cumplieron el contrato y aun así fallaron el eval: "
        "el esquema garantiza la forma, no los valores."
        if wrong_c
        else "todas las respuestas de C que cumplieron el contrato pasaron el eval."
    )
    line2 = f"[bold]Evals: A {ea:.0f}% · B {eb:.0f}% · C {ec:.0f}% — {tail}[/bold]"
    return [line1, line2]


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Corre la Fase 1 (A/B/C sobre el set de evals), la Fase 2 y el resumen.

    Side effects:
        (3 × runs × len(CASES) + 2) llamadas de red; escribe respuestas/*.md
        y la salida formateada en stdout.
    """
    parser = argparse.ArgumentParser(
        description="Salidas estructuradas: pedir JSON vs modo estructurado."
    )
    parser.add_argument(
        "--runs", type=int, default=DEFAULT_RUNS,
        help=f"corridas del set de evals por estrategia (default {DEFAULT_RUNS})",
    )
    args = parser.parse_args()
    runs = max(1, args.runs)
    client = get_gemini_client()

    console.print(
        Panel.fit(
            "[bold yellow]Salidas estructuradas: pedir JSON vs modo estructurado[/bold yellow]\n"
            "[dim]Mismo prompt, tres configuraciones de llamada; contrato Pydantic y evals "
            "con salida esperada.[/dim]\n"
            f"[dim]Modelo: {MODEL} | {runs} corridas × {len(CASES)} casos × "
            f"{len(STRATEGIES)} estrategias[/dim]",
            border_style="yellow",
        )
    )
    console.print()
    console.print(
        Panel(
            Text(inspect.getsource(Ticket) + "\n" + inspect.getsource(Pedido)),
            title="[bold bright_black]Contratos: enum (Literal) y Pydantic plano[/bold bright_black]",
            border_style="bright_black",
            padding=(0, 2),
            expand=False,
        )
    )
    console.print()

    console.print(Rule("[bold]Fase 1 — Mismo prompt, tres modos de llamada[/bold]", style="white"))
    console.print(
        "[dim]Puntos: [green]●[/green] cumple contrato y pasa el eval · "
        "[yellow]●[/yellow] cumple contrato, valor incorrecto · "
        "[red]●[/red] no parsea o rompe el contrato[/dim]\n"
    )
    all_results = {s.key: run_strategy(client, s, runs) for s in STRATEGIES}
    flat = {key: [o for run in res for o in run] for key, res in all_results.items()}

    run_contract_break(client)

    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    console.print()
    print_metrics_table(flat)
    print_evals_table(all_results, runs)
    for line in verdict(flat):
        console.print(line)
    console.print()


if __name__ == "__main__":
    main()
