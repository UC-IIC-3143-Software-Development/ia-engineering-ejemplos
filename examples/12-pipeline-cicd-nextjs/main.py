"""
Pipeline CI/CD reproducible generado con un prompt controlado
=============================================================
Concepto: para que un LLM escriba un pipeline que funcione a la primera, el
prompt le entrega los hechos que no conoce (scripts del proyecto, versión de
Node, acciones permitidas fijadas por SHA) y reglas con ID que el programa
comprueba por código. El modelo no elige versiones: las copia.

Este prototipo:
  1. Lee los hechos del proyecto Next.js "hola mundo" de proyecto/.
  2. Pide el workflow de GitHub Actions con un prompt vago y con el prompt
     controlado (misma salida estructurada; B agrega system prompt y
     temperature=0).
  3. Comprueba ambos YAML contra las mismas reglas.
  4. Si el controlado cumple las reglas bloqueantes, copia el proyecto y su
     .github/workflows/ci-cd.yml a --destino, listo para subir a GitHub.
     Si no, no escribe nada y termina con código 1, como un check de CI.
"""

import argparse
import json
import os
import posixpath
import re
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

load_dotenv()
console = Console(highlight=False)

MODEL = "gemini-2.5-flash"
AQUI = Path(__file__).parent
PROYECTO = AQUI / "proyecto"
DESTINO_POR_DEFECTO = AQUI / "salida" / "hola-nextjs-cicd"
RUTA_WORKFLOW = ".github/workflows/ci-cd.yml"
MAX_LINEAS_VAGO = 40

# Acciones permitidas, fijadas por SHA de commit: un tag (v7) se puede mover, un SHA no.
# Resueltas el 2026-09-30 con `gh api repos/<repo>/commits/<tag> --jq .sha`.
ACCIONES: dict[str, tuple[str, str]] = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "actions/setup-node": ("820762786026740c76f36085b0efc47a31fe5020", "v7.0.0"),
    "actions/configure-pages": ("45bfe0192ca1faeb007ade9deae92b16b8254a0d", "v6.0.0"),
    "actions/upload-pages-artifact": (
        "fc324d3547104276b827a68afc52ff2a11cc49c9",
        "v5.0.0",
    ),
    "actions/deploy-pages": ("368f82528645a54fb793d4d04e342629a3f51346", "v5.0.1"),
}

PROMPT_VAGO = (
    "Crea un workflow de GitHub Actions con CI/CD para mi proyecto Next.js: que revise "
    "el código, corra los tests y lo publique en GitHub Pages."
)

SYSTEM_CONTROLADO = (
    "Eres un generador de workflows de GitHub Actions. Escribes el workflow pedido usando "
    "solo los hechos, las acciones y los scripts que te entregan; si algo no está en el "
    "contexto, no lo agregas."
)


@dataclass(frozen=True)
class Proyecto:
    """Hechos del proyecto que el prompt entrega al modelo y que las reglas verifican."""

    version_node: str
    version_next: str
    scripts: dict[str, str]


def leer_proyecto() -> Proyecto:
    """Lee la versión de Node (.nvmrc), la de Next y los scripts de package.json."""
    paquete = json.loads((PROYECTO / "package.json").read_text(encoding="utf-8"))
    return Proyecto(
        version_node=(PROYECTO / ".nvmrc").read_text(encoding="utf-8").strip(),
        version_next=paquete["dependencies"]["next"],
        scripts=paquete["scripts"],
    )


# ─── Lectura defensiva del workflow ───────────────────────────────────────────
# El YAML viene de un modelo: cualquier clave puede faltar o tener otra forma.

Workflow = dict[str, Any]
SOLO_MAIN = "github.ref=='refs/heads/main'"  # condición "solo en main", ya normalizada


def _dict(valor: object) -> dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def _jobs(wf: Workflow) -> dict[str, dict[str, Any]]:
    return {str(nombre): _dict(job) for nombre, job in _dict(wf.get("jobs")).items()}


def _pasos(job: dict[str, Any]) -> list[dict[str, Any]]:
    pasos = job.get("steps")
    return [_dict(p) for p in pasos] if isinstance(pasos, list) else []


def _usa(paso: dict[str, Any], accion: str) -> bool:
    return str(paso.get("uses", "")).startswith(f"{accion}@")


def _comandos(job: dict[str, Any]) -> list[str]:
    """Comandos de los `run:` del job, en orden: una línea con && || o ; cuenta como varios."""
    return [
        comando.strip()
        for paso in _pasos(job)
        for comando in re.split(r"&&|\|\||;|\n", str(paso.get("run", "")))
        if comando.strip()
    ]


def _ruta(valor: object) -> str:
    """Normaliza una ruta relativa para compararla: ./out/ y out son la misma."""
    return posixpath.normpath(str(valor))


def _expresion(valor: object) -> str:
    """Normaliza una expresión (`if:`, `env:`) para compararla: sin ${{ }} ni espacios."""
    return re.sub(r"\s+|\$\{\{|\}\}", "", str(valor or ""))


def _posicion(comandos: list[str], comando: str) -> int:
    """Índice del primer comando igual a `comando` (admite flags extra); -1 si no está."""
    return next(
        (
            i
            for i, c in enumerate(comandos)
            if c == comando or c.startswith(f"{comando} ")
        ),
        -1,
    )


# ─── Reglas: cada una se comprueba por código ─────────────────────────────────
# Una verificación devuelve None si el workflow cumple, o el motivo si no.


def verificar_disparadores(wf: Workflow, _: Proyecto) -> str | None:
    on = wf.get("on")
    if not isinstance(on, dict):  # `on: push` y `on: [push, pull_request]`: sin ramas
        on = {str(e): None for e in (on if isinstance(on, list) else [on])}
    faltan = [e for e in ("push", "pull_request", "workflow_dispatch") if e not in on]
    if faltan:
        return f"faltan disparadores: {', '.join(faltan)}"
    for evento in ("push", "pull_request"):
        if _dict(on[evento]).get("branches") != ["main"]:
            return f"{evento} no está limitado a branches: [main]"
    return None


def verificar_entorno(wf: Workflow, _: Proyecto) -> str | None:
    for nombre, job in _jobs(wf).items():
        if job.get("runs-on") != "ubuntu-24.04":
            return f"job {nombre}: runs-on {job.get('runs-on')!r}, no ubuntu-24.04"
    setups = [
        _dict(p.get("with"))
        for job in _jobs(wf).values()
        for p in _pasos(job)
        if _usa(p, "actions/setup-node")
    ]
    if not setups:
        return "no usa actions/setup-node"
    if any(
        _ruta(w.get("node-version-file")) != ".nvmrc" or "node-version" in w
        for w in setups
    ):
        return "setup-node no toma la versión de .nvmrc (node-version-file)"
    return None


def verificar_npm_ci(wf: Workflow, _: Proyecto) -> str | None:
    comandos = [c for job in _jobs(wf).values() for c in _comandos(job)]
    prohibido = next(
        (c for c in comandos if re.match(r"(npm (install|i|add)|yarn|pnpm|bun)\b", c)),
        None,
    )  # _comandos ya separó `npm ci || npm install` en dos comandos
    if prohibido:
        return f"usa `{prohibido}`"
    if _posicion(comandos, "npm ci") == -1:
        return "no instala con npm ci"
    return None


def verificar_acciones(wf: Workflow, _: Proyecto) -> str | None:
    permitidas = {f"{repo}@{sha}" for repo, (sha, _tag) in ACCIONES.items()}
    for job in _jobs(wf).values():
        for paso in _pasos(job):
            uso = paso.get("uses")
            if uso and str(uso) not in permitidas:
                return f"{uso} no está en la lista (fijada por SHA)"
    return None


def verificar_permisos(wf: Workflow, _: Proyecto) -> str | None:
    if _dict(wf.get("permissions")) != {"contents": "read"}:
        actuales = wf.get("permissions") or "sin declarar"
        return f"permissions del workflow: {actuales}; se espera contents: read"
    esperados = {
        "build": {"contents": "read", "pages": "read"},
        "deploy": {"pages": "write", "id-token": "write"},
    }
    jobs = _jobs(wf)
    # Un job extra no declara permissions: hereda contents: read del workflow.
    for nombre in dict.fromkeys([*esperados, *jobs]):
        permisos = esperados.get(nombre, {})
        actuales = _dict(jobs.get(nombre, {}).get("permissions"))
        if actuales != permisos:
            esperado = permisos or "heredados"
            return f"job {nombre}: permissions {actuales or 'heredados'}, se espera {esperado}"
    checkouts = [
        p for p in _pasos(jobs.get("build", {})) if _usa(p, "actions/checkout")
    ]
    if not checkouts:
        return "el job build no hace actions/checkout"
    # checkout lee sus inputs como texto: false y "false" valen lo mismo
    if any(
        str(_dict(p.get("with")).get("persist-credentials")).lower() != "false"
        for p in checkouts
    ):
        return "checkout sin persist-credentials: false"
    return None


def verificar_sin_secretos(wf: Workflow, _: Proyecto) -> str | None:
    if re.search(r"\bsecrets\s*[.\[]", repr(wf)):
        return "usa secrets.*"
    return None


def verificar_calidad(wf: Workflow, proyecto: Proyecto) -> str | None:
    build = _jobs(wf).get("build")
    if build is None:
        return "no hay job build"
    pasos = _pasos(build)
    if (
        build.get("continue-on-error")
        or "if" in build
        or any(p.get("continue-on-error") or ("run" in p and "if" in p) for p in pasos)
        or any("||" in str(p.get("run", "")) for p in pasos)
    ):
        return "un fallo no detiene el job build (continue-on-error, if o ||)"
    comandos = [re.sub(r"^npm run test\b", "npm test", c) for c in _comandos(build)]
    for comando in comandos:
        script = re.match(r"npm run (\S+)", comando)
        if script and script[1] not in proyecto.scripts:
            return f"`{comando}`: el script no existe en package.json"
    orden = ["npm ci", "npm run lint", "npm run typecheck", "npm test", "npm run build"]
    posiciones = [_posicion(comandos, c) for c in orden]
    if -1 in posiciones:
        return f"falta `{orden[posiciones.index(-1)]}` en el job build"
    if posiciones != sorted(posiciones):
        return "los pasos no van en el orden ci → lint → typecheck → test → build"
    return None


def verificar_deploy(wf: Workflow, _: Proyecto) -> str | None:
    deploy = _jobs(wf).get("deploy")
    if deploy is None:
        return "no hay job deploy"
    needs = deploy.get("needs")
    if "build" not in (needs if isinstance(needs, list) else [needs]):
        return "deploy no depende de build (needs: build)"
    if _expresion(deploy.get("if")) != SOLO_MAIN:
        return "deploy sin if: github.ref == 'refs/heads/main'"
    entorno = _dict(deploy.get("environment"))
    if entorno.get("name") != "github-pages":
        return "deploy sin environment: name: github-pages"
    pasos = _pasos(deploy)
    if len(pasos) != 1 or not _usa(pasos[0], "actions/deploy-pages"):
        return "deploy debe tener un único paso, actions/deploy-pages (no reconstruye)"
    if (
        pasos[0].get("id") != "deployment"
        or _expresion(entorno.get("url")) != "steps.deployment.outputs.page_url"
    ):
        return (
            "deploy sin url: ${{ steps.deployment.outputs.page_url }} (id: deployment)"
        )
    return None


def verificar_artefacto(wf: Workflow, _: Proyecto) -> str | None:
    pasos = _pasos(_jobs(wf).get("build", {}))

    def indice(condicion: Callable[[dict[str, Any]], bool]) -> int:
        return next((i for i, p in enumerate(pasos) if condicion(p)), -1)

    i_pages = indice(lambda p: _usa(p, "actions/configure-pages"))
    i_build = indice(lambda p: "npm run build" in str(p.get("run", "")))
    i_upload = indice(lambda p: _usa(p, "actions/upload-pages-artifact"))
    if -1 in (i_pages, i_build, i_upload):
        return "el job build necesita configure-pages, npm run build y upload-pages-artifact"
    if not i_pages < i_build < i_upload:
        return "orden esperado: configure-pages → npm run build → upload-pages-artifact"
    pages, build, upload = pasos[i_pages], pasos[i_build], pasos[i_upload]
    if pages.get("id") != "pages":
        return "configure-pages sin id: pages"
    if any(_expresion(p.get("if")) != SOLO_MAIN for p in (pages, upload)):
        return "configure-pages y upload-pages-artifact deben correr solo en main"
    if (
        _expresion(_dict(build.get("env")).get("BASE_PATH"))
        != "steps.pages.outputs.base_path"
    ):
        return "npm run build sin env BASE_PATH: ${{ steps.pages.outputs.base_path }}"
    if _ruta(_dict(upload.get("with")).get("path")) != "out":
        return "upload-pages-artifact no publica out/"
    return None


def verificar_operacion(wf: Workflow, _: Proyecto) -> str | None:
    for nombre, job in _jobs(wf).items():
        minutos = job.get("timeout-minutes")
        if not isinstance(minutos, int) or not 0 < minutos <= 15:
            return f"job {nombre} sin timeout-minutes ≤ 15"
    concurrencia = _dict(_jobs(wf).get("deploy", {}).get("concurrency"))
    if (
        concurrencia.get("group") != "pages"
        or concurrencia.get("cancel-in-progress") is not False
    ):
        return "deploy sin concurrency: group: pages, cancel-in-progress: false"
    return None


@dataclass(frozen=True)
class Regla:
    """Una regla del pipeline: el texto lo lee el modelo; `verificar` lo aplica el programa."""

    id: str
    titulo: str
    bloqueante: bool
    texto: str
    verificar: Callable[[Workflow, Proyecto], str | None]


REGLAS: list[Regla] = [
    Regla(
        id="TRG-01",
        titulo="Disparadores",
        bloqueante=True,
        texto="on: push y pull_request con branches: [main], más workflow_dispatch.",
        verificar=verificar_disparadores,
    ),
    Regla(
        id="REP-01",
        titulo="Entorno fijo",
        bloqueante=True,
        texto=(
            "runs-on: ubuntu-24.04 en cada job (ubuntu-latest cambia de versión sin aviso); "
            "setup-node con node-version-file: .nvmrc, sin node-version."
        ),
        verificar=verificar_entorno,
    ),
    Regla(
        id="REP-02",
        titulo="Dependencias con npm ci",
        bloqueante=True,
        texto=(
            "Instala solo con `npm ci` (respeta package-lock.json). Prohibido npm install, "
            "yarn, pnpm y bun."
        ),
        verificar=verificar_npm_ci,
    ),
    Regla(
        id="REP-03",
        titulo="Acciones fijadas por SHA",
        bloqueante=True,
        texto=(
            "Usa solo las acciones de la lista permitida, con la línea uses: exacta "
            "(fijada por SHA de commit, no por tag)."
        ),
        verificar=verificar_acciones,
    ),
    Regla(
        id="SEG-01",
        titulo="Permisos mínimos",
        bloqueante=True,
        texto=(
            "permissions: contents: read a nivel de workflow; job build: contents: read y "
            "pages: read; job deploy: pages: write e id-token: write. Checkout con "
            "persist-credentials: false."
        ),
        verificar=verificar_permisos,
    ),
    Regla(
        id="SEG-02",
        titulo="Sin secretos",
        bloqueante=True,
        texto=(
            "No uses secrets.*: el workflow se autentica solo con los permissions de cada "
            "job, así corre en un repositorio recién creado sin configurar nada."
        ),
        verificar=verificar_sin_secretos,
    ),
    Regla(
        id="CI-01",
        titulo="Quality gates",
        bloqueante=True,
        texto=(
            "El job build ejecuta, en este orden: npm ci, npm run lint, npm run typecheck, "
            "npm test, npm run build. Solo scripts que existen en package.json. Un fallo en "
            "cualquiera detiene el job: sin continue-on-error, sin if en esos pasos y sin ||."
        ),
        verificar=verificar_calidad,
    ),
    Regla(
        id="CD-01",
        titulo="Deploy solo desde main",
        bloqueante=True,
        texto=(
            "Job deploy con needs: build, if: github.ref == 'refs/heads/main', environment "
            "name: github-pages y url: ${{ steps.deployment.outputs.page_url }}, y un único "
            "paso: actions/deploy-pages (id: deployment). No reconstruye nada."
        ),
        verificar=verificar_deploy,
    ),
    Regla(
        id="CD-02",
        titulo="Artefacto de Pages",
        bloqueante=True,
        texto=(
            "En el job build: configure-pages (id: pages) antes de npm run build y "
            "upload-pages-artifact (with: path: out) después, ambos con if: github.ref == "
            "'refs/heads/main'; el paso npm run build con env: BASE_PATH: "
            "${{ steps.pages.outputs.base_path }}."
        ),
        verificar=verificar_artefacto,
    ),
    Regla(
        id="OPS-01",
        titulo="Límites de ejecución",
        bloqueante=False,
        texto=(
            "timeout-minutes de máximo 15 en cada job; job deploy con concurrency: group: "
            "pages y cancel-in-progress: false (nunca corta un deploy a medias)."
        ),
        verificar=verificar_operacion,
    ),
]


def verificar(workflow_yaml: str, proyecto: Proyecto) -> dict[str, str | None]:
    """Aplica todas las REGLAS a un workflow en texto YAML.

    Returns:
        {id de regla: None si cumple, o el motivo si no}. Si el texto no es un
        workflow YAML, todas las reglas fallan con ese motivo.
    """
    try:
        wf = yaml.safe_load(workflow_yaml)
    except (yaml.YAMLError, ValueError):  # ValueError: p.ej. una fecha imposible
        wf = None
    if not isinstance(wf, dict):
        return {r.id: "la respuesta no es un workflow YAML" for r in REGLAS}
    if True in wf:  # PyYAML sigue YAML 1.1 y lee la clave `on:` como el booleano True
        wf["on"] = wf.pop(True)
    return {r.id: r.verificar(wf, proyecto) for r in REGLAS}


def prompt_controlado(proyecto: Proyecto) -> str:
    """Arma el prompt: tarea, contexto (hechos), acciones, pasos, reglas, casos borde y salida."""
    scripts = "\n".join(f"  - {k}: {v}" for k, v in proyecto.scripts.items())
    acciones = "\n".join(
        f"  uses: {repo}@{sha} # {tag}" for repo, (sha, tag) in ACCIONES.items()
    )
    reglas = "\n".join(
        f"- {r.id} ({'BLOQUEANTE' if r.bloqueante else 'advertencia'}): {r.texto}"
        for r in REGLAS
    )
    return f"""Tarea: escribe {RUTA_WORKFLOW} con el pipeline CI/CD del proyecto de abajo.
- CI: en cada pull request a main y cada push a main, instala, revisa, prueba y construye.
- CD: en push a main (o ejecución manual en main), publica en GitHub Pages lo que construyó CI.

Contexto del proyecto (hechos; úsalos tal cual):
- Next.js {proyecto.version_next} con export estático: `npm run build` deja el sitio en out/.
- Versión de Node: archivo .nvmrc ({proyecto.version_node}).
- Dependencias: npm, con package-lock.json versionado.
- Scripts de package.json:
{scripts}
- next.config.ts usa la variable de entorno BASE_PATH como basePath. GitHub Pages sirve el
  sitio en /<nombre-del-repo>; ese valor lo entrega actions/configure-pages en su salida base_path.
- GitHub Pages está activado con origen "GitHub Actions". El repositorio no tiene secretos.

Acciones permitidas (copia cada línea uses: exacta, con su SHA y su comentario de versión):
{acciones}

Pasos:
1. Job build: checkout → setup-node (cache: npm) → npm ci → npm run lint → npm run typecheck
   → npm test → configure-pages → npm run build → upload-pages-artifact.
2. Job deploy: después de build, publica el artefacto con deploy-pages.

Reglas (el programa comprueba cada una; las BLOQUEANTES son obligatorias):
{reglas}

Casos borde:
- En pull_request el ref es refs/pull/N/merge: no corren configure-pages, upload-pages-artifact
  ni el job deploy; BASE_PATH queda vacío y el sitio se construye para la raíz.
- workflow_dispatch sobre main se comporta como un push a main: construye y despliega.

Salida: el YAML completo del workflow en el campo workflow_yaml, sin cercos de markdown."""


# ─── Llamadas al modelo ───────────────────────────────────────────────────────


class RespuestaWorkflow(BaseModel):
    """Schema de salida, el mismo para ambos prompts."""

    workflow_yaml: str


def get_gemini_client() -> genai.Client:
    """Crea el cliente de Gemini con reintentos ante 429/5xx.

    Edge cases:
        Termina con código 2 si falta GEMINI_API_KEY (entorno o <repo>/.env).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] falta GEMINI_API_KEY (en .env o exportada)."
        )
        sys.exit(2)
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=5)
        ),
    )


def generar(
    client: genai.Client,
    prompt: str,
    system: str | None = None,
    temperature: float | None = None,
) -> tuple[str, float]:
    """Pide el workflow y devuelve (YAML, segundos). El YAML es "" si no respetó el schema.

    Raises:
        google.genai.errors.APIError si la API falla tras los reintentos.
    """
    inicio = time.perf_counter()
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=RespuestaWorkflow,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
    )
    parsed = resp.parsed
    yaml_texto = parsed.workflow_yaml if isinstance(parsed, RespuestaWorkflow) else ""
    return yaml_texto.strip(), time.perf_counter() - inicio


# ─── Salida ───────────────────────────────────────────────────────────────────


def escribir_proyecto(destino: Path, workflow_yaml: str) -> None:
    """Copia proyecto/ (sin artefactos de build) a `destino` y agrega el workflow.

    `destino` no debe existir: main() lo comprueba antes de llamar al modelo.
    """
    shutil.copytree(
        PROYECTO,
        destino,
        ignore=shutil.ignore_patterns(
            "node_modules", ".next", "out", "next-env.d.ts", "*.tsbuildinfo"
        ),
    )
    ruta = destino / RUTA_WORKFLOW
    ruta.parent.mkdir(parents=True)
    cabecera = (
        f"# Generado por examples/12-pipeline-cicd-nextjs/main.py ({MODEL}, prompt controlado)\n"
        f"# y verificado contra {len(REGLAS)} reglas antes de escribirse.\n"
    )
    ruta.write_text(f"{cabecera}{workflow_yaml}\n", encoding="utf-8")


def celda(motivo: str | None) -> str:
    """Celda de la tabla de verificación: ✓ si cumple, ✗ y el motivo si no."""
    if motivo is None:
        return "[green]✓[/green]"
    return f"[red]✗[/red] [dim]{escape(motivo)}[/dim]"


def mostrar_yaml(
    workflow_yaml: str, titulo: str, max_lineas: int | None = None
) -> None:
    """Imprime el YAML con resaltado; si se da `max_lineas`, recorta y dice cuánto omitió."""
    lineas = workflow_yaml.splitlines()
    texto = "\n".join(lineas[:max_lineas]) if max_lineas else workflow_yaml
    if max_lineas and len(lineas) > max_lineas:
        texto += f"\n# [... {len(lineas) - max_lineas} líneas más]"
    syntax = Syntax(texto or "# (vacío)", "yaml", word_wrap=True)
    console.print(Panel(syntax, title=titulo, border_style="bright_black"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un pipeline CI/CD para Next.js con un prompt controlado."
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=DESTINO_POR_DEFECTO,
        help="carpeta nueva donde queda el proyecto listo para subir "
        "(por defecto salida/hola-nextjs-cicd)",
    )
    args = parser.parse_args()
    destino: Path = args.destino.expanduser().resolve()
    if destino.exists():
        console.print(
            f"[bold red]Error:[/bold red] {destino} ya existe. Bórralo o usa otro --destino."
        )
        sys.exit(2)

    proyecto = leer_proyecto()
    client = get_gemini_client()

    console.print(
        Panel.fit(
            "[bold yellow]Pipeline CI/CD para Next.js: prompt vago vs prompt controlado"
            "[/bold yellow]\n"
            f"[dim]Proyecto: Next.js {proyecto.version_next} · Node {proyecto.version_node} · "
            f"{len(REGLAS)} reglas comprobadas por código[/dim]\n"
            f"[dim]Modelo: {MODEL} | 1 corrida por prompt[/dim]",
            border_style="yellow",
        )
    )
    tabla_acciones = Table(
        title="Acciones permitidas (el modelo las copia, no las elige)"
    )
    tabla_acciones.add_column("Acción", style="bold")
    tabla_acciones.add_column("Versión")
    tabla_acciones.add_column("SHA de commit", style="dim")
    for repo, (sha, tag) in ACCIONES.items():
        tabla_acciones.add_row(repo, tag, sha)
    console.print(tabla_acciones)

    try:
        console.print(Rule("[bold cyan]A) Prompt vago[/bold cyan]"))
        console.print(
            Panel(PROMPT_VAGO, title="Entrada al modelo", border_style="bright_black")
        )
        yaml_vago, seg_vago = generar(client, PROMPT_VAGO)
        mostrar_yaml(yaml_vago, f"Workflow generado ({seg_vago:.1f}s)", MAX_LINEAS_VAGO)

        console.print(Rule("[bold magenta]B) Prompt controlado[/bold magenta]"))
        prompt = prompt_controlado(proyecto)
        console.print(
            Panel(
                escape(prompt), title="Entrada al modelo", border_style="bright_black"
            )
        )
        yaml_ctrl, seg_ctrl = generar(client, prompt, SYSTEM_CONTROLADO, temperature=0)
        mostrar_yaml(yaml_ctrl, f"Workflow generado ({seg_ctrl:.1f}s)")
    except errors.APIError as e:
        console.print(f"[bold red]Error de la API de Gemini:[/bold red] {e}")
        sys.exit(2)

    res_vago = verificar(yaml_vago, proyecto)
    res_ctrl = verificar(yaml_ctrl, proyecto)

    tabla = Table(
        title="Verificación por código (mismas reglas para ambos)", show_lines=True
    )
    tabla.add_column("ID", style="bold")
    tabla.add_column("Regla")
    tabla.add_column("Tipo", justify="center")
    tabla.add_column("A) Vago", max_width=38)
    tabla.add_column("B) Controlado", max_width=38)
    for r in REGLAS:
        tipo = (
            "[red]bloqueante[/red]" if r.bloqueante else "[yellow]advertencia[/yellow]"
        )
        tabla.add_row(
            r.id, r.titulo, tipo, celda(res_vago[r.id]), celda(res_ctrl[r.id])
        )
    console.print(tabla)

    def bloqueos(resultado: dict[str, str | None]) -> list[str]:
        return [r.id for r in REGLAS if r.bloqueante and resultado[r.id] is not None]

    def cumplidas(resultado: dict[str, str | None]) -> str:
        return f"{sum(m is None for m in resultado.values())}/{len(REGLAS)}"

    console.print(Rule("[bold yellow]Resumen[/bold yellow]", style="yellow"))
    resumen = Table(show_lines=True)
    resumen.add_column("Métrica", style="bold")
    resumen.add_column("A) Vago", justify="center", style="cyan")
    resumen.add_column("B) Controlado", justify="center", style="magenta")
    resumen.add_row("Reglas cumplidas", cumplidas(res_vago), cumplidas(res_ctrl))
    resumen.add_row(
        "Bloqueantes incumplidas",
        str(len(bloqueos(res_vago))),
        str(len(bloqueos(res_ctrl))),
    )
    resumen.add_row(
        "Líneas de YAML",
        str(len(yaml_vago.splitlines())),
        str(len(yaml_ctrl.splitlines())),
    )
    resumen.add_row("Latencia", f"{seg_vago:.1f}s", f"{seg_ctrl:.1f}s")
    console.print(resumen)

    if bloqueos(res_ctrl):
        console.print(
            f"[bold red]VEREDICTO: el pipeline controlado incumple "
            f"{', '.join(bloqueos(res_ctrl))}; no se escribe nada.[/bold red]"
        )
        sys.exit(1)

    escribir_proyecto(destino, yaml_ctrl)
    ruta = (
        destino.relative_to(Path.cwd())
        if destino.is_relative_to(Path.cwd())
        else destino
    )
    console.print(
        Panel(
            f"cd {ruta}\n"
            'git init -b main && git add -A && git commit -m "Hola mundo Next.js con CI/CD"\n'
            f"gh repo create {destino.name} --public --source . --push\n"
            'gh api -X POST "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pages" '
            "-f build_type=workflow\n"
            "sleep 10 && gh run watch",
            title=f"Próximos pasos: subir {destino.name} y probar el pipeline",
            border_style="green",
        )
    )
    incumple_vago = bloqueos(res_vago)
    contraste = (
        f" El prompt vago incumple {len(incumple_vago)}: {', '.join(incumple_vago)}."
        if incumple_vago
        else ""
    )
    console.print(
        f"[bold green]VEREDICTO: pipeline listo en {ruta / RUTA_WORKFLOW}; cumple todas "
        f"las reglas bloqueantes.{contraste}[/bold green]"
    )


if __name__ == "__main__":
    main()
