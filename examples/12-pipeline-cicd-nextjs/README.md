# Pipeline CI/CD para Next.js con un prompt controlado

Un script que le pide a un LLM el workflow de GitHub Actions (CI + deploy a GitHub Pages) de un
proyecto Next.js "hola mundo" y **comprueba por código** que el YAML cumple reglas de
reproducibilidad y seguridad antes de escribirlo. El resultado es una carpeta lista para subir a un
repositorio nuevo y ver el pipeline correr.

Ejemplo relacionado: `08-revisor-pr` (reglas con ID que el programa verifica).

## El concepto

"Crea un workflow de CI/CD para mi proyecto Next.js" deja que el modelo decida con lo que recuerda
de su entrenamiento: `actions/checkout@v4` (un tag que se mueve y, además, una acción de Node 20),
`node-version: 20.x` o `lts/*`, `ubuntu-latest`, `npm install` en vez de `npm ci`, sin `permissions`
a nivel de workflow. El YAML se ve razonable, pero dos corridas no construyen lo mismo y nadie puede
comprobar qué decidió.

El prompt controlado le entrega al modelo lo que no sabe y acota lo que puede elegir:

| Elemento | En este script |
|---|---|
| **Tarea** | Escribir `.github/workflows/ci-cd.yml`: CI en PR y push a `main`, CD a GitHub Pages desde `main` |
| **Contexto (hechos)** | Versión de Next y de Node (`.nvmrc`), scripts de `package.json`, que `next.config.ts` lee `BASE_PATH`. Se leen de `proyecto/`, no se escriben a mano |
| **Restricción** | Solo 5 acciones permitidas, cada una fijada por SHA de commit: el modelo las copia, no las elige |
| **Pasos** | Job `build` (ci → lint → typecheck → test → configure-pages → build → upload) y job `deploy` |
| **Reglas con ID** | 10 reglas; cada una la comprueba una función de Python sobre el YAML parseado |
| **Casos borde** | En `pull_request` no se publica nada; `workflow_dispatch` sobre `main` despliega |
| **Salida** | JSON con un campo `workflow_yaml`. El schema es el mismo para ambos; B además usa system prompt y `temperature=0` |

| ID | Regla | Tipo |
|---|---|---|
| TRG-01 | `push` y `pull_request` a `main`, más `workflow_dispatch` | bloqueante |
| REP-01 | `runs-on: ubuntu-24.04`; Node desde `.nvmrc` (`node-version-file`) | bloqueante |
| REP-02 | Dependencias con `npm ci`; prohibido `npm install`, yarn, pnpm, bun | bloqueante |
| REP-03 | Solo acciones de la lista, fijadas por SHA de commit | bloqueante |
| SEG-01 | Permisos mínimos por job (un job extra no declara ninguno); checkout con `persist-credentials: false` | bloqueante |
| SEG-02 | Sin `secrets.*`: corre en un repo recién creado | bloqueante |
| CI-01 | `npm ci` → lint → typecheck → test → build con scripts que existen; un fallo detiene el job (sin `continue-on-error` ni `\|\|`) | bloqueante |
| CD-01 | `deploy`: `needs: build`, `if` exacto de `main`, environment `github-pages` con su `url`, un único paso | bloqueante |
| CD-02 | `configure-pages` y `upload-pages-artifact` con el mismo `if` de `main`; build con `BASE_PATH` | bloqueante |
| OPS-01 | `timeout-minutes` ≤ 15; `concurrency` en deploy sin cancelar a medias | advertencia |

### Qué significa "reproducible" aquí

| Qué se fija | Cómo |
|---|---|
| Node | `.nvmrc` con la versión exacta (`24.21.0`) y `node-version-file: .nvmrc` |
| Dependencias | `package.json` con versiones exactas, `package-lock.json` versionado y `npm ci` |
| Acciones | SHA de commit: un tag como `v7` se puede mover, un SHA no |
| Runner | `ubuntu-24.04` en vez de `ubuntu-latest` |
| Configuración previa | Ninguna salvo activar Pages: el pipeline no usa secretos |

El texto que devuelve el modelo **no** es idéntico entre corridas, ni con `temperature=0`: en 5
corridas seguidas salieron dos YAML distintos. Los dos cumplen las 10 reglas. La reproducibilidad no
sale del modelo: sale de las reglas y de la verificación.

## Qué hace el prototipo

1. Lee los hechos de `proyecto/` (`.nvmrc`, versión de `next`, scripts de `package.json`).
2. **A) Prompt vago:** una frase pidiendo CI/CD con GitHub Pages. Muestra las primeras 40 líneas
   del YAML.
3. **B) Prompt controlado:** system prompt + `temperature=0` + el prompt completo (se imprime). Muestra
   el YAML entero.
4. Aplica las **mismas 10 reglas** a ambos YAML (PyYAML + una función por regla) y muestra una tabla
   con el motivo de cada incumplimiento.
5. Si B cumple todas las bloqueantes, copia `proyecto/` y el workflow a `salida/hola-nextjs-cicd/`
   (o a `--destino`) e imprime los comandos para subirlo. Si no, **no escribe nada** y termina con
   código 1, como un check de CI.

## El proyecto Next.js (`proyecto/`)

La entrada es fija, así lo único que varía entre corridas es el pipeline.

| Archivo | Contenido |
|---|---|
| `.nvmrc` | `24.21.0` (Node LTS "Krypton") |
| `package.json` | Next 16.3.7, React 19.2.8, versiones exactas. Scripts: `dev`, `build`, `lint` (`eslint`), `typecheck` (`next typegen && tsc --noEmit`), `test` (`vitest run`) |
| `next.config.ts` | `output: "export"` (sitio estático en `out/`), `basePath: process.env.BASE_PATH` y `agentRules: false` |
| `app/page.tsx` | `<h1>Hola mundo</h1>` |
| `app/page.test.tsx` | Vitest + `renderToStaticMarkup`: la portada contiene `<h1>Hola mundo</h1>` (sin jsdom) |
| `eslint.config.mjs`, `tsconfig.json` | Los que genera `create-next-app@16.3.7` |
| `package-lock.json` | Generado con npm 11.19.0; incluye los binarios de Linux x64 que usa el runner |

Detalles que no son obvios:

- `typecheck` corre `next typegen` antes de `tsc`: `app/layout.tsx` usa el tipo global
  `LayoutProps`, que Next genera; en un checkout limpio `tsc` solo falla.
- ESLint queda en 9.x: `eslint-config-next` 16.3.7 no acepta ESLint 10.
- `agentRules: false`: si `next dev` detecta un agente (Claude Code, Cursor...), Next 16.3 escribe
  `AGENTS.md` y `CLAUDE.md` en el proyecto, que después se copiarían a `salida/` y al repo.
- GitHub Pages sirve el sitio en `https://<usuario>.github.io/<repo>/`. Sin `basePath` el HTML carga
  pero `/_next/...` da 404. `actions/configure-pages` entrega ese prefijo (`base_path`) y el build lo
  recibe como `BASE_PATH`. No se usa `static_site_generator: next` de `configure-pages`: solo sabe
  editar `next.config.js/.mjs` y con un `next.config.ts` crea un `next.config.js` que lo reemplaza
  en silencio.

Verificado con `npm ci && npm run lint && npm run typecheck && npm test && npm run build` en macOS y
en Linux x86_64 (`docker run node:24.21.0`), y el job `build` completo con
[`act`](https://github.com/nektos/act) sobre un evento `pull_request`.

Para correrlo en local: `cd proyecto && nvm use && npm ci && npm run dev`.

## Setup

La key se lee de `GEMINI_API_KEY`: en `<repo>/.env` (la carga `python-dotenv`) o exportada.

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=tu_key
```

## Cómo correr

```bash
python3 main.py
python3 main.py --destino ~/src/hola-nextjs-cicd
echo $?
```

La primera forma escribe en `salida/hola-nextjs-cicd/` (ignorada por git); `--destino` elige otra
carpeta, que no debe existir. Código de salida: 0 = pipeline escrito, 1 = el pipeline controlado
incumple una regla bloqueante, 2 = falta la key, la API falló o el destino ya existe (sin red, Python
termina con un traceback).

Tarda ~30 s (2 llamadas). La corrida grabada está en `output-1.md`.

## Probar el pipeline en GitHub

Requisitos: `gh` autenticado y repositorio **público** (GitHub Pages en repos privados necesita un
plan pago).

```bash
cd salida/hola-nextjs-cicd
git init -b main && git add -A && git commit -m "Hola mundo Next.js con CI/CD"
gh repo create hola-nextjs-cicd --public --source . --push
gh api -X POST "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pages" -f build_type=workflow
sleep 10 && gh run watch
```

El cuarto comando activa Pages con origen "GitHub Actions" (en la web: Settings → Pages → Source:
GitHub Actions). Hazlo justo después del push: el job `build` tarda cerca de un minuto en llegar a
`configure-pages`. Al activar Pages, GitHub crea el environment `github-pages` y lo restringe a la
rama por defecto. El `sleep` le da tiempo a GitHub para registrar el run: si `gh` responde
`found no in progress runs to watch` o `no checks reported`, espera unos segundos y repite el comando.

Qué deberías ver:

- **Push a `main`:** `build` (lint, typecheck, test, build, upload) y después `deploy`. La URL del
  sitio, `https://<usuario>.github.io/hola-nextjs-cicd/`, aparece en el job `deploy`. Puede tardar
  un minuto en responder en esa URL.
- **Ejecución manual:** `gh workflow run ci-cd.yml --ref main` hace lo mismo que un push.
- **Un PR que rompe el CI:** el test exige `Hola mundo`, así que cambiar el título lo rompe. El
  check del PR queda en rojo en el paso `npm test` y `deploy` no corre.

  ```bash
  git switch -c cambio-titulo
  sed -i.bak 's/Hola mundo/Hola CI/' app/page.tsx && rm app/page.tsx.bak
  git commit -am "Cambia el título" && git push -u origin cambio-titulo
  gh pr create --fill && sleep 10 && gh pr checks --watch
  ```

En los logs aparecen dos avisos esperables de npm: ESLint 9 marcado como *deprecated* y
`install-scripts` bloqueando el `postinstall` de `unrs-resolver` (no hace falta: npm ya instala el
binario de Linux).

### Si el primer run falla

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `configure-pages`: `Get Pages site failed ... Not Found` | Pages no estaba activado | Activarlo (comando de arriba) y `gh run rerun --failed` |
| `422 Your current plan does not support GitHub Pages for this repository` | Repo privado en plan Free | `gh repo edit --visibility public --accept-visibility-change-consequences`, repetir el comando que activa Pages y `gh run rerun --failed` |
| `deploy`: `Branch "..." is not allowed to deploy to github-pages` | Deploy desde otra rama, o se renombró la rama por defecto | Desplegar desde `main`, o editar Settings → Environments → github-pages |
| La URL da 404 aunque el run está en verde | Pages quedó en "Deploy from a branch" | `gh api -X PUT "repos/<usuario>/<repo>/pages" -f build_type=workflow` |

## Qué observar (en `output-1.md`)

- **A)** El prompt vago cumple **1/10** reglas. Usa Node `20.x` (sin soporte desde abril de 2026),
  `npm install` en vez de `npm ci`, `actions/checkout@v4` y `setup-node@v4` por tag y
  `ubuntu-latest`. No tiene disparador `pull_request`, así que un PR nunca se revisa, y todo corre en
  un solo job `build_and_deploy` con `pages: write` e `id-token: write`, incluido el `npm install`.
  Nada de eso es un error de sintaxis: el YAML es válido. Lo que falla es que no cumple lo que el
  equipo necesita, porque el prompt no lo decía. En 3 corridas de prueba cumplió entre 0 y 2 reglas.
- **B)** El prompt controlado cumple **10/10** en la primera llamada y copia los 5 SHA sin error. Con
  esta versión del prompt cumplió todas las reglas en 6 de 6 corridas (la grabada y 5 de prueba).
- Los motivos de la tabla son concretos (`usa npm install`, `actions/checkout@v4 no está en la
  lista`) porque cada regla es una función, no una opinión del modelo. Algunos fallos de A (`no hay
  job build`) son de estructura: el prompt vago nunca dijo cómo organizar los jobs.
- El modelo no conoce los SHA ni la versión de Node ni los scripts del proyecto: están en el
  contexto. Si mañana sale `actions/checkout` v8, se cambia `ACCIONES` en `main.py` y el prompt, la
  regla y la verificación se actualizan juntos.

## Métricas

- **Reglas cumplidas:** reglas cuya verificación no encontró problemas / 10.
- **Bloqueantes incumplidas:** si B tiene alguna, el script no escribe nada (código 1).
- **Líneas de YAML y latencia:** por prompt, 1 corrida.

## Siguiente iteración: `SPECS.md`

`SPECS.md` especifica la versión siguiente del pipeline, para implementarla con un agente sobre el
repo ya subido: CI por stages (lint, test, build), CD manual que despliega un git tag, concurrencia
como semáforo (mutex en el deploy, preempción en los PR) y escaneo de dependencias con Trivy. Cada
versión trae criterios de aceptación que se comprueban con un comando.

## Mantener las versiones al día

Los SHA de `ACCIONES` se resolvieron el 2026-09-30. Para actualizar una acción:

```bash
gh api repos/actions/checkout/releases/latest --jq .tag_name
gh api repos/actions/checkout/commits/v7.0.1 --jq .sha
```

El primero da el último tag (p.ej. `v7.0.1`); el segundo, el SHA de ese tag para `ACCIONES`.

En un repositorio real, Dependabot (`package-ecosystem: github-actions`) propone estos cambios como
PR y el pipeline los prueba antes de aceptarlos.
