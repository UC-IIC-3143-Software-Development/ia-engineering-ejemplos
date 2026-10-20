"""Bot revisor de PRs guiado por reglas de negocio verificables.

Lee un archivo Python y lo revisa contra una lista CERRADA de reglas con ID
(montos con Decimal, IVA desde config, SQL parametrizado, sin credenciales,
sin N+1, ...). El modelo debe dar un veredicto por regla con líneas y cita
literal; el programa comprueba que cada regla fue evaluada y que la cita existe
en el código (descarta hallazgos inventados). Como un bot de CI, termina con
código 1 si hay reglas bloqueantes incumplidas.

Para contrastar, muestra también la respuesta al prompt vago típico ("eres un
ingeniero senior... clean code"): texto libre que no se puede verificar.
"""
import argparse
import os
import sys
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()
console = Console()

MODEL = "gemini-2.5-flash"
ARCHIVO_POR_DEFECTO = Path(__file__).parent / "pr_checkout.py"

# Reglas de negocio del equipo. Cada una es comprobable mirando el código: dice qué
# está permitido, qué está prohibido y dónde mirar.
REGLAS: list[dict] = [
    {"id": "NEG-01", "titulo": "Montos con Decimal", "bloqueante": True,
     "regla": "Todo monto de dinero (precio, subtotal, descuento, IVA, total) se representa con "
              "decimal.Decimal. Prohibido float, float() o literales con punto decimal para dinero."},
    {"id": "NEG-02", "titulo": "IVA desde configuración", "bloqueante": False,
     "regla": "La tasa de IVA se lee de config.IVA_CL. Prohibido escribir 0.19, 19 o 1.19 en el código."},
    {"id": "NEG-03", "titulo": "Tope de descuento 30 %", "bloqueante": True,
     "regla": "El descuento aplicado a un pedido se acota explícitamente a como máximo el 30 % del "
              "subtotal antes de calcular el total."},
    {"id": "SEG-01", "titulo": "Sin credenciales en el código", "bloqueante": True,
     "regla": "Ninguna API key, token, password o connection string con password aparece como "
              "literal; se leen con os.environ[...]."},
    {"id": "SEG-02", "titulo": "SQL parametrizado", "bloqueante": True,
     "regla": "Toda consulta SQL pasa los datos como parámetros (%s + tupla). Prohibido armar SQL "
              "con f-strings, concatenación o .format."},
    {"id": "SEG-03", "titulo": "Sin datos personales en logs", "bloqueante": True,
     "regla": "Email, RUT y número de tarjeta nunca se escriben en log.* ni print; si hace falta se "
              "usa enmascarar(valor)."},
    {"id": "PERF-01", "titulo": "Sin consultas dentro de loops", "bloqueante": True,
     "regla": "Prohibido ejecutar consultas a la base de datos dentro de un for/while (N+1); se "
              "traen o actualizan en una sola consulta (p.ej. WHERE id = ANY(%s))."},
    {"id": "PERF-02", "titulo": "Timeout en llamadas HTTP", "bloqueante": False,
     "regla": "Toda llamada HTTP saliente (requests.get/post/...) pasa timeout= explícito de a lo "
              "más 10 segundos."},
    {"id": "DAT-01", "titulo": "Stock y pedido en una transacción", "bloqueante": True,
     "regla": "Descontar stock y registrar el pedido ocurren en una misma transacción "
              "(with conn.transaction():); prohibido hacer commit entre ambos pasos."},
]

# Verdad-terreno de pr_checkout.py (solo se usa al revisar el archivo por defecto).
VERDAD = {"NEG-01": "no_cumple", "NEG-02": "no_cumple", "NEG-03": "cumple",
          "SEG-01": "no_cumple", "SEG-02": "no_cumple", "SEG-03": "no_cumple",
          "PERF-01": "no_cumple", "PERF-02": "cumple", "DAT-01": "no_cumple"}

SYSTEM_REGLAS = (
    "Eres un bot de revisión de pull requests. Tu única tarea es verificar, una por una, las "
    "reglas de negocio de la lista. No comentes nada que no esté en la lista (estilo, nombres, "
    "docstrings, arquitectura)."
)

SIN_AFC = types.AutomaticFunctionCallingConfig(disable=True)  # no usamos tools
MAX_LINEAS_VAGO = 45

PROMPT_VAGO = ("Eres un ingeniero senior experto en Python. Revisa este pull request aplicando "
               "clean code y buenas prácticas. Da tus comentarios.\n\n```python\n{codigo}\n```")


class ResultadoRegla(BaseModel):
    regla_id: str
    veredicto: Literal["cumple", "no_cumple", "no_aplica"]
    lineas: list[int]
    evidencia: str
    sugerencia: str


class Revision(BaseModel):
    resultados: list[ResultadoRegla]


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos ante 429/5xx.

    Returns:
        Un genai.Client autenticado con GEMINI_API_KEY (entorno o <repo>/.env).

    Edge cases / gotchas:
        Termina el programa con un mensaje si falta la key.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/bold red] falta GEMINI_API_KEY (en .env o exportada).")
        sys.exit(2)
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=5)))


def numerar(codigo: str) -> str:
    """Antepone el número de línea a cada línea, para que el modelo cite líneas exactas."""
    return "\n".join(f"{i:>3}| {linea}" for i, linea in enumerate(codigo.splitlines(), 1))


def prompt_reglas(codigo: str) -> str:
    """Arma el prompt de revisión: tarea, reglas con ID, formato de salida y casos borde."""
    reglas = "\n".join(f"- {r['id']} ({'BLOQUEANTE' if r['bloqueante'] else 'advertencia'}): "
                       f"{r['regla']}" for r in REGLAS)
    return f"""Tarea: verifica si el código del PR cumple CADA una de estas reglas de negocio.

Reglas:
{reglas}

Instrucciones:
1. Devuelve exactamente un resultado por regla, usando su ID.
2. veredicto: "no_cumple" si hay al menos una violación; "cumple" si el código hace lo que la
   regla exige; "no_aplica" si el código no toca lo que la regla regula.
3. lineas: números de línea (los del margen izquierdo) donde está la violación o el cumplimiento.
4. evidencia: copia LITERAL de una línea del código (sin el número de línea) que lo demuestre.
5. sugerencia: el cambio concreto para cumplir la regla; vacío si cumple o no aplica.

Código del PR (con números de línea):
```python
{numerar(codigo)}
```"""


def revisar_con_reglas(client: genai.Client, codigo: str) -> Revision:
    """Pide al modelo la revisión estructurada por reglas.

    Raises:
        google.genai.errors.APIError si la API falla tras los reintentos.
    """
    resp = client.models.generate_content(
        model=MODEL, contents=prompt_reglas(codigo),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_REGLAS, temperature=0, automatic_function_calling=SIN_AFC,
            response_mime_type="application/json", response_schema=Revision))
    return Revision.model_validate_json(resp.text or "{}")


def revisar_vago(client: genai.Client, codigo: str) -> str:
    """Revisión con el prompt vago típico; devuelve el texto libre del modelo."""
    resp = client.models.generate_content(
        model=MODEL, contents=PROMPT_VAGO.format(codigo=codigo),
        config=types.GenerateContentConfig(automatic_function_calling=SIN_AFC))
    return resp.text or ""


def evidencia_verificada(res: ResultadoRegla, lineas_codigo: list[str]) -> bool:
    """True si la cita (su primera línea) aparece literalmente en alguna línea del código.

    Edge cases / gotchas:
        No exige que coincida con `res.lineas`: el modelo a veces desplaza el número de
        línea en uno; lo que importa para descartar invenciones es que la cita exista.
    """
    cita = res.evidencia.strip().splitlines()[0].strip() if res.evidencia.strip() else ""
    return bool(cita) and any(cita in linea for linea in lineas_codigo)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bot revisor de PRs por reglas de negocio.")
    parser.add_argument("archivo", nargs="?", type=Path, default=ARCHIVO_POR_DEFECTO,
                        help="archivo .py a revisar (por defecto pr_checkout.py)")
    args = parser.parse_args()
    codigo = args.archivo.read_text(encoding="utf-8")
    lineas_codigo = codigo.splitlines()
    con_verdad = args.archivo.resolve() == ARCHIVO_POR_DEFECTO.resolve()
    client = get_gemini_client()

    console.print(Panel.fit(
        "[bold yellow]Bot revisor de PRs: reglas de negocio vs prompt vago[/bold yellow]\n"
        f"[dim]Archivo: {args.archivo.name} ({len(lineas_codigo)} líneas) | "
        f"{len(REGLAS)} reglas[/dim]\n[dim]Modelo: {MODEL} | 1 corrida por estrategia[/dim]",
        border_style="yellow"))

    tabla_reglas = Table(title="Reglas del equipo (lo que el bot debe comprobar)", show_lines=False)
    tabla_reglas.add_column("ID", style="bold")
    tabla_reglas.add_column("Regla")
    tabla_reglas.add_column("Tipo", justify="center")
    for r in REGLAS:
        tabla_reglas.add_row(r["id"], r["titulo"], "[red]bloqueante[/red]" if r["bloqueante"]
                             else "[yellow]advertencia[/yellow]")
    console.print(tabla_reglas)

    try:
        console.print(Rule("[bold cyan]A) Prompt vago: \"ingeniero senior + clean code\"[/bold cyan]"))
        t0 = time.time()
        vago = revisar_vago(client, codigo)
        lineas_vago = vago.splitlines()
        recorte = "\n".join(lineas_vago[:MAX_LINEAS_VAGO])
        if len(lineas_vago) > MAX_LINEAS_VAGO:
            recorte += f"\n\n*[... {len(lineas_vago) - MAX_LINEAS_VAGO} líneas más]*"
        console.print(Panel(Markdown(recorte),
                            title=f"Respuesta del modelo ({time.time() - t0:.1f}s)",
                            border_style="bright_black"))

        console.print(Rule("[bold magenta]B) Bot con reglas de negocio[/bold magenta]"))
        t0 = time.time()
        revision = revisar_con_reglas(client, codigo)
        console.print(f"[dim]Revisión estructurada recibida en {time.time() - t0:.1f}s[/dim]")
    except errors.APIError as e:
        console.print(f"[bold red]Error de la API de Gemini:[/bold red] {e}")
        sys.exit(2)

    por_id = {r.regla_id: r for r in revision.resultados}
    faltantes = [r["id"] for r in REGLAS if r["id"] not in por_id]

    tabla = Table(title="Resultado por regla", show_lines=True)
    tabla.add_column("ID", style="bold")
    tabla.add_column("Veredicto bot", justify="center")
    tabla.add_column("Líneas", justify="center")
    tabla.add_column("Evidencia (cita)", max_width=46)
    tabla.add_column("¿Cita real?", justify="center")
    if con_verdad:
        tabla.add_column("Esperado", justify="center")

    color = {"cumple": "green", "no_cumple": "red", "no_aplica": "dim"}
    bloqueos, aciertos, citas_ok, citas_total = [], 0, 0, 0
    detect_bot = violaciones = 0
    for r in REGLAS:
        res = por_id.get(r["id"])
        esperado = VERDAD.get(r["id"], "")
        if res is None:
            fila = [r["id"], "[bold red]SIN EVALUAR[/bold red]", "-", "-", "-"]
        else:
            ok_cita = evidencia_verificada(res, lineas_codigo)
            if res.veredicto == "no_cumple":
                citas_total += 1
                citas_ok += ok_cita
                if r["bloqueante"]:
                    bloqueos.append(res)
            fila = [r["id"], f"[{color[res.veredicto]}]{res.veredicto}[/{color[res.veredicto]}]",
                    ",".join(map(str, res.lineas)) or "-", res.evidencia.strip()[:120] or "-",
                    ("[green]sí[/green]" if ok_cita else "[red]no[/red]")
                    if res.veredicto == "no_cumple" else "[dim]n/a[/dim]"]
            aciertos += con_verdad and res.veredicto == esperado
        if con_verdad:
            fila.append(esperado)
            if esperado == "no_cumple":
                violaciones += 1
                detect_bot += bool(res and res.veredicto == "no_cumple")
        tabla.add_row(*fila)
    console.print(tabla)

    if bloqueos:
        comentario = "\n".join(
            f"- **{b.regla_id}** (líneas {', '.join(map(str, b.lineas))}): `{b.evidencia.strip()}`"
            f" → {b.sugerencia}" for b in bloqueos)
        console.print(Panel(Markdown(f"### 🤖 Cambios requeridos\n\n{comentario}"),
                            title="Comentario que el bot publicaría en el PR",
                            border_style="red"))

    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    resumen = Table(show_lines=True)
    resumen.add_column("Métrica", style="bold")
    resumen.add_column("A) Prompt vago", justify="center", style="cyan")
    resumen.add_column("B) Reglas de negocio", justify="center", style="magenta")
    resumen.add_row("Formato de salida", f"texto libre ({len(vago.split())} palabras)",
                    "JSON validado: 1 veredicto por regla")
    resumen.add_row("Reglas del equipo evaluadas", "no garantizado",
                    f"{len(REGLAS) - len(faltantes)}/{len(REGLAS)}")
    resumen.add_row("Citas de violación verificadas", "no verificable", f"{citas_ok}/{citas_total}")
    if con_verdad:
        resumen.add_row("Violaciones reales detectadas", "hay que leerlo a mano",
                        f"{detect_bot}/{violaciones}")
        resumen.add_row("Veredictos correctos", "n/a", f"{aciertos}/{len(REGLAS)}")
    resumen.add_row("Usable por CI (exit code)", "no", "sí")
    console.print(resumen)

    if faltantes:
        console.print(f"[bold red]VEREDICTO: revisión inválida, reglas sin evaluar: "
                      f"{', '.join(faltantes)}[/bold red]")
        sys.exit(1)
    if bloqueos:
        console.print(f"[bold red]VEREDICTO: PR BLOQUEADO, {len(bloqueos)} reglas bloqueantes "
                      f"incumplidas ({', '.join(b.regla_id for b in bloqueos)}).[/bold red]")
        sys.exit(1)
    console.print("[bold green]VEREDICTO: PR aprobado, cumple todas las reglas bloqueantes."
                  "[/bold green]")


if __name__ == "__main__":
    main()
