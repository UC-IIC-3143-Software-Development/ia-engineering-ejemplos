#!/usr/bin/env python3
"""
Prompt como código: registry versionado + arnés de regresión
============================================================
Concepto: el prompt decide el comportamiento del sistema, así que se versiona y
se prueba como código. Un cambio "razonable" puede arreglar unos casos y romper
otros en silencio; solo un eval caso a caso contra la versión en producción lo
muestra antes de que llegue a los usuarios.

Este prototipo:
  1. Guarda dos versiones de un prompt de triage en un registry ("nombre@vN").
  2. Corre los mismos 10 casos N veces contra cada versión.
  3. Compara caso a caso (arreglos y regresiones) y decide si v2 se promueve.
"""

import argparse
import difflib
import os
import textwrap
import time
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

load_dotenv()

MODEL = "gemini-2.5-flash"

console = Console(highlight=False)

# ─── Registry de prompts ──────────────────────────────────────────────────────
#
# Clave "nombre@vN" → template. Una versión publicada no se edita: cada cambio
# es una clave nueva, y el código de la aplicación pide el prompt por clave en
# vez de tenerlo hardcodeado en el call site.
#
# v2 nace de reclamos reales: cobros duplicados que llegaban como urgencia media
# y una cuenta hackeada que se derivó a "general". Cada regla nueva suena
# razonable por separado; el eval dice qué más cambió.

REGISTRY: dict[str, str] = {
    "triage_ticket@v1": textwrap.dedent("""\
        Eres el asistente de triage del soporte de una tienda online.
        Clasifica el mensaje del cliente con una urgencia y una categoría.

        Urgencia:
          alta  — caída del servicio, pérdida de datos, ventas que se pierden ahora
                  mismo o equipos completos que no pueden iniciar sesión.
          media — experiencia degradada, fallas parciales, reembolsos y cobros
                  incorrectos o duplicados.
          baja  — preguntas generales, copias de facturas, tokens o documentación
                  de la API para uso personal, dónde cambiar la contraseña,
                  sugerencias o felicitaciones.

        Categoría:
          facturacion — cobros, pagos, facturas, reembolsos o cambios de plan.
          tecnico     — errores, fallas, rendimiento, API, tokens o documentación técnica.
          general     — cuenta, perfil, contraseña, datos de despacho y todo lo demás.

        Mensaje del cliente:
        {mensaje}
        """),
    "triage_ticket@v2": textwrap.dedent("""\
        Eres el asistente de triage del soporte de una tienda online.
        Clasifica el mensaje del cliente con una urgencia y una categoría.

        Urgencia:
          alta  — caída del servicio, pérdida de datos, ventas que se pierden ahora
                  mismo o incidentes de seguridad.
          media — experiencia degradada, fallas parciales o solicitudes con plazo.
          baja  — preguntas generales, sugerencias o felicitaciones.

        Categoría:
          facturacion — cobros, pagos, facturas, reembolsos o cambios de plan.
          tecnico     — errores, fallas, rendimiento e incidentes de seguridad.
          general     — todo lo demás.

        Reglas adicionales:
          - Un cobro duplicado o no reconocido es urgencia alta (riesgo de contracargo).
          - Por seguridad, todo mensaje que mencione "contraseña", "cuenta", "acceso",
            "sesión", "API" o "token" DEBE ser urgencia alta y categoría tecnico,
            sin importar el contexto.
          - Pedir facturas para la contabilidad tiene plazo tributario: urgencia media.

        Mensaje del cliente:
        {mensaje}
        """),
}

PRODUCCION = "triage_ticket@v1"  # congelada: es la que atiende tráfico hoy
CANDIDATA = "triage_ticket@v2"  # debe pasar el eval para reemplazarla


def render_prompt(clave: str, mensaje: str) -> str:
    """Devuelve el prompt de una versión del registry con el mensaje insertado.

    Args:
        clave: versión con forma "nombre@vN"; debe existir en REGISTRY.
        mensaje: texto del cliente; reemplaza a {mensaje} en el template.

    Returns:
        El prompt listo para enviar al modelo.

    Edge cases:
        Lanza KeyError si la clave no existe: pedir una versión inexistente es un
        error de programación, no un caso que el caller deba manejar. Las llaves
        dentro de `mensaje` no se interpretan (solo se formatea el template).
    """
    return REGISTRY[clave].format(mensaje=mensaje)


# ─── Salida del modelo y suite de casos ───────────────────────────────────────


class Triage(BaseModel):
    """Clasificación de un mensaje; también es el schema que Gemini debe respetar."""

    urgencia: Literal["baja", "media", "alta"]
    categoria: Literal["facturacion", "tecnico", "general"]

    def __str__(self) -> str:
        return f"{self.urgencia}/{self.categoria}"


@dataclass(frozen=True)
class Caso:
    """Un mensaje de cliente con la clasificación que el negocio espera hoy."""

    id: int
    mensaje: str
    esperado: Triage


def _caso(id_: int, mensaje: str, urgencia: str, categoria: str) -> Caso:
    """Atajo para declarar la suite; valida urgencia/categoría contra el schema."""
    return Caso(
        id_,
        mensaje,
        Triage.model_validate({"urgencia": urgencia, "categoria": categoria}),
    )


# La suite es la especificación: describe el comportamiento que queremos ahora,
# no el que tenía v1. Por eso v1 también falla algunos casos.
CASOS: list[Caso] = [
    _caso(
        1,
        "Nadie de mi equipo puede iniciar sesión desde esta mañana y hoy tenemos que "
        "despachar pedidos.",
        "alta",
        "tecnico",
    ),
    _caso(2, "¿Cómo cambio mi foto de perfil?", "baja", "general"),
    _caso(
        3,
        "Necesito una copia de la factura de marzo para mi contador.",
        "baja",
        "facturacion",
    ),
    _caso(
        4,
        "¿Dónde encuentro el token de la API para un proyecto personal?",
        "baja",
        "tecnico",
    ),
    _caso(
        5,
        "El checkout tira error 500 y estamos perdiendo ventas ahora mismo.",
        "alta",
        "tecnico",
    ),
    _caso(
        6, "Me cobraron dos veces la misma compra en la tarjeta.", "alta", "facturacion"
    ),
    _caso(7, "La app está muy lenta al recorrer el catálogo.", "media", "tecnico"),
    _caso(
        8,
        "Quiero actualizar mi contraseña por seguridad, ¿dónde está esa opción?",
        "baja",
        "general",
    ),
    _caso(
        9,
        "Alguien entró a mi cuenta sin permiso y cambió la dirección de despacho.",
        "alta",
        "tecnico",
    ),
    _caso(
        10,
        "Aparece en mi tarjeta un cargo de su tienda que no reconozco.",
        "alta",
        "facturacion",
    ),
]


@dataclass(frozen=True)
class Corrida:
    """Una llamada al modelo.

    `obtenido` es None si la API falló tras los reintentos o si la respuesta no
    respetó el schema; en ese caso `texto` describe el problema.
    """

    obtenido: Triage | None
    texto: str
    segundos: float


@dataclass(frozen=True)
class ResultadoCaso:
    """Las N corridas de un caso contra una versión del prompt."""

    caso: Caso
    corridas: list[Corrida]

    @property
    def aciertos(self) -> int:
        """Corridas cuya clasificación coincide exactamente con la esperada."""
        return sum(c.obtenido == self.caso.esperado for c in self.corridas)

    @property
    def pasa(self) -> bool:
        """El caso pasa si acierta en la mayoría estricta de las corridas."""
        return self.aciertos * 2 > len(self.corridas)

    @property
    def inestable(self) -> bool:
        """Acierta en algunas corridas y falla en otras."""
        return 0 < self.aciertos < len(self.corridas)

    @property
    def respuesta_tipica(self) -> str:
        """La respuesta más frecuente entre corridas, p. ej. "alta/tecnico"."""
        conteo = Counter(
            str(c.obtenido) if c.obtenido else "error" for c in self.corridas
        )
        return conteo.most_common(1)[0][0]

    def primera_falla(self) -> Corrida | None:
        """La primera corrida que no coincide con lo esperado (None si todas aciertan)."""
        return next(
            (c for c in self.corridas if c.obtenido != self.caso.esperado), None
        )


# ─── Llamadas al modelo ───────────────────────────────────────────────────────


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos automáticos.

    Returns:
        Un genai.Client autenticado que reintenta errores 429/5xx con backoff
        (hasta 5 intentos por llamada).

    Side effects:
        Lee GEMINI_API_KEY del entorno (o de <repo>/.env vía python-dotenv).

    Edge cases:
        Si falta la key imprime un panel de error y termina con SystemExit(1).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            Panel(
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


def clasificar(client: genai.Client, prompt: str) -> Corrida:
    """Envía un prompt ya renderizado y devuelve la clasificación validada.

    Args:
        client: cliente de get_gemini_client().
        prompt: salida de render_prompt().

    Returns:
        Corrida con la clasificación, la respuesta cruda y la latencia. Nunca
        lanza por errores de la API: los reporta como Corrida con obtenido=None
        para que un caso fallido no aborte la suite.
    """
    inicio = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Triage,
                temperature=0.0,
                # Sin tools: desactivar AFC evita que el SDK imprima un warning a mitad del progreso.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except errors.APIError as exc:
        return Corrida(None, f"error de API: {exc}", time.perf_counter() - inicio)
    obtenido = response.parsed if isinstance(response.parsed, Triage) else None
    return Corrida(
        obtenido, response.text or "(respuesta vacía)", time.perf_counter() - inicio
    )


def evaluar_version(
    client: genai.Client, clave: str, runs: int, color: str
) -> list[ResultadoCaso]:
    """Corre todos los CASOS `runs` veces contra una versión del registry.

    Args:
        client: cliente de get_gemini_client().
        clave: versión del registry a evaluar.
        runs: corridas por caso (>= 1).
        color: color rich del encabezado de la sección.

    Returns:
        Un ResultadoCaso por caso, en el orden de CASOS.

    Side effects:
        Hace len(CASOS) * runs llamadas al modelo e imprime un punto por corrida
        (● verde = acierto, ○ rojo = falla; se distinguen también sin color) y el
        tiempo total del caso.
    """
    console.print(
        f"[bold {color}]── {etiqueta(clave)} ──────────────────────────────[/bold {color}]"
    )
    resultados: list[ResultadoCaso] = []
    for i, caso in enumerate(CASOS, start=1):
        console.print(f"  Caso #{caso.id:02d}: ", end="")
        prompt = render_prompt(clave, caso.mensaje)
        corridas: list[Corrida] = []
        for _ in range(runs):
            corrida = clasificar(client, prompt)
            corridas.append(corrida)
            acierto = corrida.obtenido == caso.esperado
            console.print("[green]●[/green]" if acierto else "[red]○[/red]", end="")
        segundos = sum(c.segundos for c in corridas)
        console.print(f" [dim]{segundos:5.1f}s[/dim]", end="   ")
        if i % 4 == 0:
            console.print()
        resultados.append(ResultadoCaso(caso, corridas))
    if len(CASOS) % 4:
        console.print()
    console.print()
    return resultados


# ─── Presentación ─────────────────────────────────────────────────────────────


def etiqueta(clave: str) -> str:
    """Clave del registry con su estado, p. ej. "triage_ticket@v1 (producción)"."""
    estado = "producción" if clave == PRODUCCION else "candidata"
    return f"{clave} ({estado})"


def mostrar_registry() -> None:
    """Imprime las versiones del registry y el diff línea a línea v1 → v2."""
    console.print(Rule("[bold]Registry de prompts[/bold]", style="white"))
    tabla = Table(show_edge=False, header_style="bold", padding=(0, 2))
    tabla.add_column("Clave")
    tabla.add_column("Estado")
    tabla.add_column("Líneas", justify="right")
    for clave, template in REGISTRY.items():
        estado = "producción (congelada)" if clave == PRODUCCION else "candidata"
        tabla.add_row(clave, estado, str(len(template.splitlines())))
    console.print(tabla)
    console.print()
    console.print(f"[bold]Diff {PRODUCCION} → {CANDIDATA}[/bold]")
    diff = difflib.unified_diff(
        REGISTRY[PRODUCCION].splitlines(),
        REGISTRY[CANDIDATA].splitlines(),
        lineterm="",
        n=1,
    )
    for linea in diff:
        if linea.startswith(("---", "+++", "@@")):
            continue
        color = {"+": "green", "-": "red"}.get(linea[:1], "dim")
        console.print(f"  [{color}]{escape(linea)}[/{color}]")
    console.print()


def mostrar_intercambio(prompt: str, mensaje: str, respuesta: str) -> None:
    """Imprime un intercambio completo: el prompt renderizado y la respuesta cruda."""
    entrada = Text(prompt.rstrip(), style="dim")
    entrada.highlight_words([mensaje], style="bold blue")
    console.print(
        Panel(
            entrada,
            title="[bold bright_black]Entrada al modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )
    console.print(
        Panel(
            Group(Text.assemble(("ASISTENTE: ", "bold green"), (respuesta, "italic"))),
            title="[bold bright_black]Respuesta del modelo[/bold bright_black]",
            border_style="bright_black",
            padding=(1, 2),
        )
    )


def celda(resultado: ResultadoCaso) -> str:
    """Celda PASA/FALLA con aciertos k/N; si falla, muestra la respuesta típica."""
    marcador = f"{resultado.aciertos}/{len(resultado.corridas)}"
    if resultado.pasa:
        return f"[bold green]PASA[/bold green] {marcador}"
    return f"[bold red]FALLA[/bold red] {marcador}\n[dim]{resultado.respuesta_tipica}[/dim]"


def motivo(esperado: Triage, obtenido: Triage | None) -> str:
    """Explica en qué campo(s) difiere una clasificación de la esperada."""
    if obtenido is None:
        return "sin respuesta válida"
    return "; ".join(
        f"{campo}: esperado '{getattr(esperado, campo)}', obtuvo '{getattr(obtenido, campo)}'"
        for campo in ("urgencia", "categoria")
        if getattr(esperado, campo) != getattr(obtenido, campo)
    )


def tabla_regresion(v1: list[ResultadoCaso], v2: list[ResultadoCaso]) -> Table:
    """Tabla caso a caso: PASA/FALLA de cada versión y el delta v1 → v2.

    v1 y v2 deben venir en el mismo orden (el de CASOS).
    """
    tabla = Table(title="Reporte de regresión (mayoría de corridas)", show_lines=True)
    tabla.add_column("#", style="bold", justify="right")
    tabla.add_column("Mensaje del cliente", max_width=36)
    tabla.add_column("Esperado", justify="center")
    tabla.add_column("v1", justify="center")
    tabla.add_column("v2", justify="center")
    tabla.add_column("Delta", justify="center")
    for r1, r2 in zip(v1, v2, strict=True):
        if r1.pasa and not r2.pasa:
            delta = "[bold red]REGRESIÓN ✗[/bold red]"
        elif not r1.pasa and r2.pasa:
            delta = "[bold green]ARREGLO ✓[/bold green]"
        else:
            delta = "[dim]igual[/dim]"
        tabla.add_row(
            str(r1.caso.id),
            r1.caso.mensaje,
            str(r1.caso.esperado),
            celda(r1),
            celda(r2),
            delta,
        )
    return tabla


def tabla_metricas(
    v1: list[ResultadoCaso], v2: list[ResultadoCaso], arreglos: int, regresiones: int
) -> Table:
    """Tabla de métricas agregadas por versión, más arreglos y regresiones de v2."""

    def fila(resultados: list[ResultadoCaso]) -> tuple[str, str, str, str]:
        corridas = [c for r in resultados for c in r.corridas]
        return (
            f"{sum(r.pasa for r in resultados)}/{len(resultados)}",
            f"{sum(r.aciertos for r in resultados)}/{len(corridas)}",
            str(sum(r.inestable for r in resultados)),
            f"{sum(c.segundos for c in corridas) / len(corridas):.1f}s",
        )

    tabla = Table(title="Métricas por versión", show_lines=True)
    tabla.add_column("Métrica", style="bold")
    tabla.add_column(etiqueta(PRODUCCION), justify="center")
    tabla.add_column(etiqueta(CANDIDATA), justify="center")
    nombres = [
        "Casos que pasan",
        "Llamadas correctas",
        "Casos inestables",
        "Latencia media por llamada",
    ]
    for nombre, a, b in zip(nombres, fila(v1), fila(v2), strict=True):
        tabla.add_row(nombre, a, b)
    tabla.add_row("Arreglos (v1 falla → v2 pasa)", "—", str(arreglos))
    tabla.add_row("Regresiones (v1 pasa → v2 falla)", "—", str(regresiones))
    return tabla


def veredicto(pasan_v1: int, pasan_v2: int, arreglos: int, regresiones: int) -> str:
    """Regla de promoción: v2 reemplaza a v1 solo si arregla algo y no rompe nada."""
    total = len(CASOS)
    if regresiones:
        oculto = ""
        if pasan_v2 >= pasan_v1:
            oculto = (
                f" El total ({pasan_v2}/{total} vs {pasan_v1}/{total}) lo esconde: "
                "solo la comparación caso a caso lo muestra."
            )
        return (
            f"[bold red]VEREDICTO: NO PROMOVER {CANDIDATA}. Arregla {arreglos} caso(s) pero rompe "
            f"{regresiones} que {PRODUCCION} resolvía; {PRODUCCION} sigue en producción."
            f"{oculto}[/bold red]"
        )
    if arreglos:
        return (
            f"[bold green]VEREDICTO: PROMOVER {CANDIDATA}. Arregla {arreglos} caso(s) "
            f"sin regresiones ({pasan_v2}/{total} vs {pasan_v1}/{total}).[/bold green]"
        )
    return (
        f"[bold yellow]VEREDICTO: SIN CAMBIO. {CANDIDATA} no arregla ningún caso; "
        f"se mantiene {PRODUCCION}.[/bold yellow]"
    )


def mostrar_detalle(pares: list[tuple[ResultadoCaso, ResultadoCaso]]) -> None:
    """Muestra el primer par en detalle (entrada y respuesta de v2) y el resto compacto."""
    for i, (r1, r2) in enumerate(pares):
        caso = r1.caso
        falla = r2.primera_falla()
        obtenido = falla.obtenido if falla else None
        console.print(
            f'[bold]Caso #{caso.id:02d}[/bold] "{caso.mensaje}"\n'
            f"  [dim]esperado:[/dim] {caso.esperado}   "
            f"[dim]v1:[/dim] {r1.respuesta_tipica} (aciertos {r1.aciertos}/{len(r1.corridas)})   "
            f"[dim]v2:[/dim] {r2.respuesta_tipica} (aciertos {r2.aciertos}/{len(r2.corridas)})\n"
            f"  [bold red]Motivo:[/bold red] {motivo(caso.esperado, obtenido)}"
        )
        if i == 0 and falla:
            console.print()
            mostrar_intercambio(
                render_prompt(CANDIDATA, caso.mensaje), caso.mensaje, falla.texto
            )
        console.print()


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Evalúa v1 y v2 del registry sobre la suite, compara caso a caso y decide."""
    parser = argparse.ArgumentParser(
        description="Prompt como código: registry + arnés de regresión."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="corridas por caso y versión (default: 3; usa 1 en clase)",
    )
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs debe ser >= 1")
    runs: int = args.runs

    console.print(
        Panel.fit(
            "[bold yellow]Prompt como código: registry + arnés de regresión[/bold yellow]\n"
            f"[dim]Los mismos {len(CASOS)} casos contra {PRODUCCION} (producción) y "
            f"{CANDIDATA} (candidata).[/dim]\n"
            f"[dim]Modelo: {MODEL} | {runs} corrida{'s' if runs != 1 else ''} por caso y versión[/dim]",
            border_style="yellow",
        )
    )
    console.print()

    client = get_gemini_client()
    mostrar_registry()

    v1 = evaluar_version(client, PRODUCCION, runs, "cyan")
    v2 = evaluar_version(client, CANDIDATA, runs, "magenta")

    pares = list(zip(v1, v2, strict=True))
    regresiones = [(r1, r2) for r1, r2 in pares if r1.pasa and not r2.pasa]
    arreglos = [(r1, r2) for r1, r2 in pares if not r1.pasa and r2.pasa]
    pasan_v1 = sum(r.pasa for r in v1)
    pasan_v2 = sum(r.pasa for r in v2)

    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    console.print()
    console.print(tabla_regresion(v1, v2))
    console.print()
    console.print(tabla_metricas(v1, v2, len(arreglos), len(regresiones)))
    console.print()

    if regresiones:
        console.print(Rule("[bold red]Detalle de regresiones[/bold red]", style="red"))
        console.print()
        mostrar_detalle(regresiones)
    else:
        console.print(Rule("[bold]Intercambio de muestra[/bold]", style="white"))
        console.print()
        muestra = v2[0]
        mostrar_intercambio(
            render_prompt(CANDIDATA, muestra.caso.mensaje),
            muestra.caso.mensaje,
            muestra.corridas[0].texto,
        )
        console.print()

    console.print(veredicto(pasan_v1, pasan_v2, len(arreglos), len(regresiones)))
    console.print()


if __name__ == "__main__":
    main()
