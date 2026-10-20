"""Helper único para hablar con el LLM (Gemini o Claude) desde los ejemplos.

Contrato:
    ask(prompt, system=None, model=None) -> str
    ask_json(prompt, schema, system=None, model=None) -> instancia validada de `schema`
    model=None usa el default del backend (DEFAULT_MODEL).

Backend (elegido automáticamente, o forzado con LLM_BACKEND=gemini|sdk|cli|fake):
  - gemini: hay GEMINI_API_KEY (en el entorno o en <repo>/.env). Requiere
            `pip install google-genai`.
  - sdk   : hay ANTHROPIC_API_KEY y el paquete `anthropic` importable.
  - cli   : `claude -p` (Claude Code autenticado). Sin herramientas, sin sesión.
  - fake  : respuestas fijas para demostrar el flujo sin red.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

DEFAULT_MODEL = {"gemini": "gemini-3.8-flash", "sdk": "claude-opus-5",
                 "cli": "claude-opus-5", "fake": "fake"}
T = TypeVar("T", bound=BaseModel)


def _load_env_file(path: Path = Path(__file__).resolve().parent.parent / ".env") -> None:
    """Carga líneas CLAVE=valor de <repo>/.env sin pisar variables ya definidas.

    Así la API key vive fuera del código (.env está en .gitignore) y no hay que
    exportarla en cada terminal.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file()


def _backend() -> str:
    forced = os.environ.get("LLM_BACKEND")
    if forced:
        return forced
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # noqa: F401
            return "sdk"
        except ImportError:
            pass
    return "cli"


# ---------- GEMINI (google-genai) ----------
def _gemini_ask(prompt: str, system: str | None, model: str, **config: object) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client()  # en variable: si se recolecta, cierra su conexión HTTP
    resp = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            **config))
    if resp.text is None:  # bloqueo de seguridad o respuesta vacía
        raise RuntimeError(f"Gemini no devolvió texto: {resp.prompt_feedback or resp.candidates}")
    return resp.text.strip()


def _gemini_ask_json(prompt: str, schema: type[T], system: str | None, model: str) -> T:
    text = _gemini_ask(prompt, system, model,
                       response_mime_type="application/json", response_schema=schema)
    return schema.model_validate_json(text)


# ---------- SDK ----------
def _sdk_ask(prompt: str, system: str | None, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    kwargs = {"model": model, "max_tokens": 1024,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def _sdk_ask_json(prompt: str, schema: type[T], system: str | None, model: str) -> T:
    import anthropic

    client = anthropic.Anthropic()
    kwargs = {"model": model, "max_tokens": 1024,
              "messages": [{"role": "user", "content": prompt}],
              "output_config": {"format": {"type": "json_schema",
                                           "schema": schema.model_json_schema()}}}
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return schema.model_validate_json(text)


# ---------- CLI (claude -p) ----------
def _cli_ask(prompt: str, system: str | None, model: str) -> str:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}  # evita anidamiento
    cmd = ["claude", "-p", "--output-format", "text", "--model", model, "--tools", ""]
    if system:
        cmd += ["--append-system-prompt", system]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, env=env, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI falló ({proc.returncode}): {proc.stderr.strip()[:500]}")
    return proc.stdout.strip()


def _extract_json(text: str) -> str:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no se encontró JSON en: {text[:200]!r}")
    return m.group(0)


def _cli_ask_json(prompt: str, schema: type[T], system: str | None, model: str) -> T:
    wrapped = (f"{prompt}\n\nResponde SOLO con JSON válido (sin prosa, sin ```), "
               f"siguiendo exactamente este esquema:\n{json.dumps(schema.model_json_schema())}")
    return schema.model_validate_json(_extract_json(_cli_ask(wrapped, system, model)))


# ---------- FAKE ----------
def _fake_ask(prompt: str, system: str | None, model: str) -> str:
    return "[fake] respuesta simulada"


def _fake_ask_json(prompt: str, schema: type[T], system: str | None, model: str) -> T:
    # Construye un ejemplo válido a partir de defaults/tipos simples del esquema.
    data = {}
    for name, field in schema.model_fields.items():
        ann = field.annotation
        args = getattr(ann, "__args__", ())
        if args and all(isinstance(a, str) for a in args):
            data[name] = args[0]
        elif ann is int:
            data[name] = 0
        elif ann is float:
            data[name] = 0.0
        elif ann is bool:
            data[name] = True
        elif ann is list or getattr(ann, "__origin__", None) is list:
            data[name] = []
        else:
            data[name] = "fake"
    return schema.model_validate(data)


# ---------- API pública ----------
def ask(prompt: str, system: str | None = None, model: str | None = None) -> str:
    """Devuelve la respuesta de texto del modelo para `prompt`."""
    backend = _backend()
    fn = {"gemini": _gemini_ask, "sdk": _sdk_ask, "cli": _cli_ask, "fake": _fake_ask}[backend]
    return fn(prompt, system, model or DEFAULT_MODEL[backend])


def ask_json(prompt: str, schema: type[T], system: str | None = None,
             model: str | None = None) -> T:
    """Devuelve una instancia validada de `schema` (Pydantic) construida por el modelo."""
    backend = _backend()
    fn = {"gemini": _gemini_ask_json, "sdk": _sdk_ask_json, "cli": _cli_ask_json,
          "fake": _fake_ask_json}[backend]
    return fn(prompt, schema, system, model or DEFAULT_MODEL[backend])


if __name__ == "__main__":
    print(f"backend: {_backend()} ({DEFAULT_MODEL[_backend()]})")
    print(ask("Responde solo: OK"))
