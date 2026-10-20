"""Tokens y costo de un prompt con LiteLLM.

Ejecuta el MISMO prompt con varios modelos Gemini a través de LiteLLM (una sola
interfaz: litellm.completion) y muestra por pantalla, para cada ejecución:
tokens de entrada, de salida y de razonamiento, latencia y costo en USD
(litellm.completion_cost, con la tabla de precios de litellm.model_cost).
Proyecta además el costo a 1.000 y 1.000.000 de ejecuciones.
"""
import argparse
import os
import sys
import time

import litellm
import openai
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()
litellm.suppress_debug_info = True
console = Console()

# (etiqueta, modelo LiteLLM "proveedor/modelo", parámetros extra). Agregar otro proveedor
# es otra fila, p.ej. ("Claude", "anthropic/claude-sonnet-5", {}) con ANTHROPIC_API_KEY.
ESCENARIOS: list[tuple[str, str, dict]] = [
    ("3.5 Flash-Lite", "gemini/gemini-3.5-flash-lite", {}),
    ("2.5 Flash (razonamiento por defecto)", "gemini/gemini-2.5-flash", {}),
    ("2.5 Flash (razonamiento apagado)", "gemini/gemini-2.5-flash", {"reasoning_effort": "disable"}),
    ("3.8 Flash", "gemini/gemini-3.8-flash", {}),
    ("3.1 Pro (preview)", "gemini/gemini-3.1-pro-preview", {}),
]

PROMPT_POR_DEFECTO = (
    "Eres el asistente de soporte de una tienda online. Clasifica este ticket en una de: "
    "facturacion, envio, producto_defectuoso, otro. Luego redacta una respuesta de 2 frases "
    "para el cliente.\n\nTicket: \"Compré unas zapatillas hace 10 días, me llegaron con la "
    "suela despegada y además me cobraron el envío dos veces.\""
)


def ejecutar(modelo: str, prompt: str, extra: dict) -> dict:
    """Ejecuta el prompt una vez y devuelve texto, uso de tokens, latencia y costo.

    Args:
        modelo: id LiteLLM "proveedor/modelo" (p.ej. "gemini/gemini-2.5-flash").
        prompt: texto del usuario.
        extra: parámetros adicionales para litellm.completion (p.ej. reasoning_effort).

    Returns:
        dict con texto, entrada, salida, razonamiento, segundos y costo (None si LiteLLM
        no tiene precio para ese modelo).

    Raises:
        openai.APIError (y subclases): LiteLLM traduce el error de cualquier proveedor a
        las excepciones estándar de OpenAI (NotFoundError, RateLimitError, ...).
    """
    t0 = time.time()
    resp = litellm.completion(model=modelo, messages=[{"role": "user", "content": prompt}],
                              num_retries=2, **extra)
    segundos = time.time() - t0
    uso = resp.usage
    detalle = uso.completion_tokens_details
    try:
        costo: float | None = litellm.completion_cost(completion_response=resp)
    except litellm.exceptions.NotFoundError:
        costo = None
    return {"texto": resp.choices[0].message.content or "", "entrada": uso.prompt_tokens,
            "salida": uso.completion_tokens,
            "razonamiento": (detalle.reasoning_tokens or 0) if detalle else 0,
            "segundos": segundos, "costo": costo}


def usd(valor: float | None) -> str:
    """Formatea USD con precisión suficiente para montos de fracciones de centavo."""
    if valor is None:
        return "sin precio"
    return f"${valor:,.6f}" if valor < 1 else f"${valor:,.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Tokens y costo de un prompt con LiteLLM.")
    parser.add_argument("--prompt", default=PROMPT_POR_DEFECTO, help="prompt a medir")
    args = parser.parse_args()
    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]Error:[/bold red] falta GEMINI_API_KEY (en .env o exportada).")
        sys.exit(2)

    console.print(Panel.fit(
        "[bold yellow]LiteLLM: tokens y costo de un prompt[/bold yellow]\n"
        "[dim]Mismo prompt, misma llamada (litellm.completion), distintos modelos.[/dim]\n"
        f"[dim]Modelos: {len(ESCENARIOS)} escenarios | 1 ejecución cada uno[/dim]",
        border_style="yellow"))
    console.print(Panel(args.prompt, title="Entrada al modelo", border_style="bright_black"))

    precios = Table(title="Precios según LiteLLM (USD por millón de tokens)")
    precios.add_column("Modelo", style="bold")
    precios.add_column("Entrada", justify="right")
    precios.add_column("Salida (incluye razonamiento)", justify="right")
    for modelo in dict.fromkeys(m for _, m, _ in ESCENARIOS):
        info = litellm.model_cost.get(modelo, {})
        precios.add_row(modelo, usd(info.get("input_cost_per_token", 0) * 1e6),
                        usd(info.get("output_cost_per_token", 0) * 1e6))
    console.print(precios)

    resultados: list[tuple[str, dict]] = []
    for etiqueta, modelo, extra in ESCENARIOS:
        try:
            r = ejecutar(modelo, args.prompt, extra)
        except openai.APIError as e:  # errores de cualquier proveedor, ya estandarizados
            console.print(f"  [red]o[/red] {etiqueta}: {type(e).__name__} (se omite)")
            continue
        resultados.append((etiqueta, r))
        console.print(f"  [green]o[/green] {etiqueta} [dim]{r['segundos']:4.1f}s · "
                      f"{r['entrada'] + r['salida']} tokens · {usd(r['costo'])}[/dim]")
    if not resultados:
        console.print("[bold red]VEREDICTO: ninguna ejecución terminó.[/bold red]")
        sys.exit(1)

    etiqueta_muestra, muestra = resultados[0]
    console.print(Panel(Markdown(muestra["texto"]), border_style="bright_black",
                        title=f"Respuesta del modelo ({etiqueta_muestra})"))

    console.print(Rule("[bold yellow]Resumen: uso de tokens y costo[/bold yellow]", style="yellow"))
    tabla = Table(show_lines=True)
    tabla.add_column("Escenario", style="bold")
    tabla.add_column("Tokens entrada", justify="right")
    tabla.add_column("Tokens salida\n(texto + razon.)", justify="right")
    tabla.add_column("De ellos\nrazonamiento", justify="right")
    tabla.add_column("Latencia", justify="right")
    tabla.add_column("Costo\n1 ejecución", justify="right", style="magenta")
    tabla.add_column("Costo\n1.000 ejec.", justify="right")
    tabla.add_column("Costo\n1 millón", justify="right", style="cyan")
    for etiqueta, r in resultados:
        costo = r["costo"]
        tabla.add_row(etiqueta, str(r["entrada"]), str(r["salida"]),
                      f"{r['razonamiento']} ({r['razonamiento'] / max(r['salida'], 1):.0%})",
                      f"{r['segundos']:.1f}s", usd(costo),
                      usd(costo * 1_000 if costo is not None else None),
                      usd(costo * 1_000_000 if costo is not None else None))
    console.print(tabla)
    total = sum(r["costo"] or 0 for _, r in resultados)
    console.print(f"[dim]Costo total de esta demo: {usd(total)}[/dim]")

    con_precio = [(e, r) for e, r in resultados if r["costo"]]
    if len(con_precio) >= 2:
        barato = min(con_precio, key=lambda x: x[1]["costo"])
        caro = max(con_precio, key=lambda x: x[1]["costo"])
        console.print(
            f"[bold green]VEREDICTO: el mismo prompt cuesta {caro[1]['costo'] / barato[1]['costo']:.0f}x "
            f"más con '{caro[0]}' que con '{barato[0]}'. Los tokens de salida (incluido el "
            "razonamiento) dominan el costo: medir antes de elegir modelo.[/bold green]")


if __name__ == "__main__":
    main()
