"""LiteLLM en producción: reintentos, rate limit, cooldown y fallback, con salida repetible.

Un solo litellm.Router con la configuración que se usa en producción. Llegan 5 tickets al
grupo "soporte" (Gemini 3.5 Flash-Lite, con una cuota propia de 2 requests por minuto) y el
Router decide en cada uno: reintentar un 429 con backoff, respetar la cuota, sacar el
deployment de rotación (cooldown) y derivar al grupo "respaldo" (Gemini 3.8 Flash).

Repetible: sin --en-vivo, cada deployment reproduce su respuesta grabada en grabacion.json
(mock_response en su litellm_params): sin red, sin API key y sin costo. El 429 del ticket 1
lo simula LiteLLM (mock_testing_rate_limit_error), también en vivo.
"""

import os

# Precios de la tabla que trae el litellm instalado. Sin esto, cada import la descarga de
# GitHub: la corrida deja de ser offline y el costo puede cambiar de un día para otro.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import argparse
import asyncio
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Any, NoReturn

import litellm
import openai  # lo instala litellm: sus excepciones son las "estandarizadas"
from dotenv import load_dotenv
from litellm import ModelResponse
from litellm.router import Router
from litellm.types.llms.openai import AllMessageValues
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

load_dotenv()
litellm.suppress_debug_info = True  # sin el banner "Give Feedback / Get Help"
# Errores sin la configuración interna del Router (grupos, fallbacks, timeouts).
litellm.expose_router_debug_in_errors = False
# Una respuesta grabada (dict) en litellm_params dispara un aviso de Pydantic al crear el Router.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
console = Console()

GRABACION = Path(__file__).with_name("grabacion.json")
MENSAJES: list[AllMessageValues] = [
    {
        "role": "system",
        "content": "Eres el asistente de soporte de una tienda online. Clasifica el ticket "
        "en una de: facturacion, envio, producto_defectuoso, otro. Responde en una línea "
        "con el formato 'categoria: respuesta de una frase para el cliente'.",
    },
    {
        "role": "user",
        "content": "Me cobraron el envío dos veces y el pedido todavía no llega.",
    },
]
# La configuración de producción: un deployment por grupo (modelo + key + límites). El id
# fijo lo identifica en la traza y en la grabación. Es lo mismo que iría en el config.yaml
# del LiteLLM Proxy.
MODEL_LIST: list[dict[str, Any]] = [
    {
        "model_name": "soporte",
        "model_info": {"id": "flash-lite"},
        "litellm_params": {
            "model": "gemini/gemini-3.5-flash-lite",
            "api_key": "os.environ/GEMINI_API_KEY",  # el secreto sale del entorno
            "rpm": 2,  # cuota propia: máx. 2 requests por minuto a este deployment
        },
    },
    {
        "model_name": "respaldo",
        "model_info": {"id": "flash"},
        "litellm_params": {
            "model": "gemini/gemini-3.8-flash",
            "api_key": "os.environ/GEMINI_API_KEY",
        },
    },
]
TICKETS: list[tuple[str, dict[str, Any]]] = [
    (
        "429 simulado del proveedor: el Router espera y reintenta",
        {"mock_testing_rate_limit_error": True},
    ),
    ("Llamada normal", {}),
    ("Cuota propia agotada: al respaldo, sin llamar al proveedor", {}),
    ("Segundo rechazo: flash-lite sale de rotación (cooldown)", {}),
    ("flash-lite en cooldown: directo al respaldo", {}),
]


def crear_router(grabaciones: dict[str, Any] | None) -> Router:
    """Crea el Router con la configuración de producción.

    Args:
        grabaciones: respuestas grabadas por id de deployment (ver leer_grabaciones). Si se
            entregan, cada deployment reproduce la suya en vez de llamar a la API; el resto
            de la configuración es idéntico en los dos modos.
    """
    model_list = MODEL_LIST
    if grabaciones is not None:
        model_list = [
            {
                **d,
                "litellm_params": {
                    **d["litellm_params"],
                    "mock_response": grabaciones[d["model_info"]["id"]]["respuesta"],
                },
            }
            for d in MODEL_LIST
        ]
    return Router(
        model_list=model_list,
        # Si "soporte" falla o no puede atender, responde "respaldo".
        fallbacks=[{"soporte": ["respaldo"]}],
        # 429, 5xx y timeouts se reintentan tras 0.5 s·2^n + jitter (0-0.75 s), o lo que
        # pida el header Retry-After (hasta 60 s). El 429 de la cuota propia (rpm) no: va
        # directo al fallback. 400, 401 y 404 no se reintentan.
        num_retries=1,
        # Más de 1 falla (429, 401, 404, timeout o 5xx; no un 400 ni un error de conexión),
        # cada una a menos de cooldown_time de la anterior, y el deployment sale de rotación
        # por cooldown_time segundos.
        allowed_fails=1,
        cooldown_time=60,
        timeout=30,  # segundos por intento; el default del Router es 6000
        # Sin este check, rpm no se hace cumplir por minuto.
        optional_pre_call_checks=["enforce_model_rate_limits"],
    )


def leer_grabaciones() -> dict[str, Any] | None:
    """Devuelve las grabaciones por id de deployment, o None si no sirven.

    No sirven si falta el archivo o alguna grabación, o si se hicieron con otros
    MENSAJES u otro modelo: reproducirlas mostraría la respuesta a otro prompt.
    """
    try:
        grabaciones: dict[str, Any] = json.loads(GRABACION.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # ValueError: JSON inválido o no es UTF-8
        return None
    for d in MODEL_LIST:
        grabacion = grabaciones.get(d["model_info"]["id"], {})
        if (
            grabacion.get("modelo") != d["litellm_params"]["model"]
            or grabacion.get("mensajes") != MENSAJES
        ):
            return None
    return grabaciones


async def atender(
    router: Router, extra: dict[str, Any]
) -> tuple[ModelResponse, list[Any]]:
    """Envía un ticket al grupo "soporte".

    Returns:
        (respuesta, intentos fallidos en "soporte"). Cada intento fallido trae
        model_group, deployment_id (None si lo rechazó el propio Router), exception_type
        y exception_string. Si a un reintento le sigue un fallback, la última falla
        aparece dos veces.

    Raises:
        openai.APIError: si fallan "soporte" y "respaldo" (el error original de "soporte").
        litellm.RouterRateLimitError: si no queda ningún deployment disponible.
    """
    traza: dict[str, Any] = {}  # el Router anota aquí las fallas en "soporte"
    # acompletion (async) y no completion: en 1.103 el sync, sobre la cuota, espera 60 s
    # y reintenta el mismo deployment en vez de ir al respaldo.
    resp = await router.acompletion(
        model="soporte", messages=MENSAJES, metadata=traza, **extra
    )
    return resp, list(traza.get("previous_models", ()))


async def atender_tickets(router: Router) -> list[ModelResponse]:
    """Atiende TICKETS en orden e imprime, por ticket, los intentos y quién respondió."""
    respuestas = []
    for n, (situacion, extra) in enumerate(TICKETS, start=1):
        resp, fallidos = await atender(router, extra)
        console.print(f"[bold]Ticket {n}[/bold] · {situacion}")
        for intento in fallidos:
            quien = intento["deployment_id"] or "router"
            tipo = intento["exception_type"]
            motivo = intento["exception_string"].removeprefix(f"litellm.{tipo}: ")
            linea = Text.assemble(
                ("  x ", "red"),
                f"{intento['model_group']}/{quien}: {tipo} ",
                (motivo, "dim"),
            )
            linea.truncate(console.width, overflow="ellipsis")
            console.print(linea)
        cabeceras = resp._hidden_params["additional_headers"]
        console.print(
            f"  [green]ok[/green] {cabeceras['x-litellm-model-group']}/"
            f"{resp._hidden_params['model_id']} [dim]· "
            f"reintentos={cabeceras['x-litellm-attempted-retries']} · "
            f"fallbacks={cabeceras['x-litellm-attempted-fallbacks']} · "
            f"{resp.usage.prompt_tokens}/{resp.usage.completion_tokens} tokens · "
            f"{usd(resp._hidden_params['response_cost'])}[/dim]"
        )
        texto = Text(f"    {resp.choices[0].message.content}", style="italic")
        texto.truncate(console.width, overflow="ellipsis")
        console.print(texto)
        respuestas.append(resp)
    return respuestas


def usd(valor: float) -> str:
    """Formatea USD con precisión suficiente para fracciones de centavo.

    LiteLLM reporta 0 para un modelo que no está en su tabla de precios: "sin precio".
    """
    return f"${valor:,.6f}" if valor else "sin precio"


def salir(mensaje: str) -> NoReturn:
    """Muestra un error sin traceback y termina con código 1."""
    console.print(Text.assemble(("Error: ", "bold red"), mensaje))
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--en-vivo",
        action="store_true",
        help="llama a Gemini y regraba grabacion.json (requiere GEMINI_API_KEY)",
    )
    en_vivo: bool = parser.parse_args().en_vivo

    grabaciones = None
    if not en_vivo:
        grabaciones = leer_grabaciones()
        if grabaciones is None:
            salir(
                f"{GRABACION.name} falta o no corresponde a MENSAJES y MODEL_LIST (¿cambiaste "
                f"el prompt o un modelo?). Recupérala con `git checkout {GRABACION.name}` o "
                "regrábala con --en-vivo."
            )
    elif not os.environ.get("GEMINI_API_KEY"):
        salir("--en-vivo necesita GEMINI_API_KEY (en <repo>/.env o exportada).")

    modo = "en vivo (llama a Gemini y regraba)" if en_vivo else "repetible (grabación)"
    console.print(
        Panel.fit(
            "[bold yellow]LiteLLM en producción: reintentos, rate limit, cooldown y "
            "fallback[/bold yellow]\n"
            "[dim]5 tickets al grupo soporte (flash-lite, cuota 2 rpm). "
            "Respaldo: flash.[/dim]\n"
            f"[dim]Modo: {modo}[/dim]",
            border_style="yellow",
        )
    )
    try:
        respuestas = asyncio.run(atender_tickets(crear_router(grabaciones)))
    except (openai.APIError, litellm.RouterRateLimitError) as e:
        tipo = type(e).__name__
        # LiteLLM antepone "litellm.<tipo>: " (a veces dos veces) y Gemini manda el motivo
        # en un JSON de varias líneas: se aplana en una.
        motivo = re.sub(rf"^(litellm\.{tipo}: )+", "", " ".join(str(e).split()))
        salir(f"{tipo}: {motivo[:200]}")

    if en_vivo:  # una sola escritura; guarda la última respuesta de cada deployment
        nuevas = {
            r._hidden_params["model_id"]: {
                "modelo": r._hidden_params["litellm_model_name"],
                "mensajes": MENSAJES,
                "respuesta": r.model_dump(),
            }
            for r in respuestas
        }
        faltan = {d["model_info"]["id"] for d in MODEL_LIST} - nuevas.keys()
        if faltan:
            salir(
                f"{', '.join(sorted(faltan))} no respondió: {GRABACION.name} no se regrabó."
            )
        GRABACION.write_text(
            json.dumps(nuevas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    cabeceras = [r._hidden_params["additional_headers"] for r in respuestas]
    reintentos = sum(int(c["x-litellm-attempted-retries"]) for c in cabeceras)
    al_respaldo = sum(int(c["x-litellm-attempted-fallbacks"]) > 0 for c in cabeceras)
    total = usd(sum(r._hidden_params["response_cost"] for r in respuestas))
    costo = (
        total
        if en_vivo
        else f"$0 en esta corrida (las respuestas grabadas cuestan {total} en vivo)"
    )
    console.print(
        f"\n[bold green]VEREDICTO: {len(respuestas)}/{len(TICKETS)} tickets respondidos · "
        f"reintentos: {reintentos} · al respaldo: {al_respaldo}\nCosto: {costo}.[/bold green]"
    )


if __name__ == "__main__":
    main()
