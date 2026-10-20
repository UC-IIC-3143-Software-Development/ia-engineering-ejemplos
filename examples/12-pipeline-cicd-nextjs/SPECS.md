# SPECS — Pipeline CI + CD manual por tag + Trivy (hola-nextjs-cicd)

Este archivo es el **contrato** que guía al agente (Claude Code) para reemplazar el workflow único
`ci-cd.yml`, que genera `main.py`, por tres workflows: **CI**, **CD manual por tag** y **escaneo de
dependencias con Trivy**. Cada versión es incremental: vN debe seguir cumpliendo los criterios de
v(N-1).
Regla de oro: si un criterio no se puede verificar con un comando, no es criterio.

Se aplica sobre el repositorio que sale de `python3 main.py` (`salida/hola-nextjs-cicd/`), ya subido
a GitHub como repo **público** con rama por defecto `main` y Pages activado con origen "GitHub
Actions" (ver README, "Probar el pipeline en GitHub"). `OWNER/REPO` es ese repo.

## Cómo se corren los criterios

- Desde la raíz del repo, con `gh` autenticado. Cada versión se integra con `git push origin main`
  y se espera su CI antes de correr sus criterios.
- Los comandos de GitHub esperan runs con estas dos funciones (definirlas una vez en la shell):
  ```bash
  ultimo() { local wf=$1; shift; gh run list --workflow "$wf" "$@" -L 1 --json databaseId --jq '.[0].databaseId'; }
  esperar() { local wf=$1; shift; sleep 10; gh run watch "$(ultimo "$wf" "$@")" --exit-status; }
  ```
  `esperar ci.yml --branch main --commit "$(git rev-parse HEAD)"` espera el CI del último commit de
  `main` y falla si no terminó en `success`.
- "Seguir cumpliendo v(N-1)" significa volver a correr sus criterios **locales** (`actionlint`,
  `test ! -e`, `act`, `npm test`, el escaneo local de Trivy). Los comandos que crean ramas, tags,
  PRs o clones, y los que comprueban qué versión está publicada, se corren una sola vez, en su
  versión.

## Contexto del proyecto (hechos, no cambiar)

- Next.js 16.3.7 con export estático: `npm run build` deja el sitio en `out/`.
- Node: `.nvmrc` con `24.21.0`. Dependencias: npm con `package-lock.json` versionado.
- Scripts de `package.json`: `lint` (`eslint`), `typecheck` (`next typegen && tsc --noEmit`),
  `test` (`vitest run`), `build` (`next build`).
- `next.config.ts` usa `process.env.BASE_PATH` como `basePath`. GitHub Pages sirve el sitio en
  `/<repo>` y ese valor lo entrega `actions/configure-pages` en su salida `base_path`.

## Restricciones globales

- Archivos: `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `.github/workflows/trivy.yml`,
  `.trivyignore.yaml`. Se **borra** `.github/workflows/ci-cd.yml`: el sitio ya no se publica solo en
  cada push a `main`.
- Solo estas acciones, **fijadas por SHA de commit** con la versión en un comentario
  (`uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`). Un tag se puede
  mover; un SHA no. En marzo de 2026 un atacante movió 76 de los 77 tags de `trivy-action` a código
  malicioso (GHSA-69fq-xp46-6x23): quien fijaba por SHA un commit posterior al 2025-04-09 no se vio
  afectado.

  | Acción | Versión | SHA de commit |
  |---|---|---|
  | `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
  | `actions/setup-node` | v7.0.0 | `820762786026740c76f36085b0efc47a31fe5020` |
  | `actions/configure-pages` | v6.0.0 | `45bfe0192ca1faeb007ade9deae92b16b8254a0d` |
  | `actions/upload-pages-artifact` | v5.0.0 | `fc324d3547104276b827a68afc52ff2a11cc49c9` |
  | `actions/deploy-pages` | v5.0.1 | `368f82528645a54fb793d4d04e342629a3f51346` |
  | `aquasecurity/trivy-action` | v0.36.0 | `ed142fd0673e97e23eac54620cfb913e5ce36c25` |
  | `github/codeql-action/upload-sarif` | v4.38.2 | `2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2` |

- `runs-on: ubuntu-24.04` en todos los jobs (`ubuntu-latest` pasa a Ubuntu 26.04 entre octubre y
  noviembre de 2026). `timeout-minutes` ≤ 15 en cada job.
- Node desde `.nvmrc` (`node-version-file: .nvmrc`, `cache: npm`) y dependencias con `npm ci`.
- `permissions: {}` a nivel de workflow; cada job pide solo lo que usa. Sin `secrets.*`: todo se
  autentica con el `GITHUB_TOKEN` del job. Checkout siempre con `persist-credentials: false`.
- Un input del usuario (`inputs.tag`) nunca se interpola en `run:`: se pasa por `env:` (evita
  inyección de comandos).
- Ids de jobs en inglés y **sin `name:` a nivel de job**: el check se llama como el id (`lint`,
  `test`, `build`, `validate`, `deploy`, `scan`). El `name:` del workflow y de los pasos, y los
  comentarios, en español. `actionlint` sin errores.

## Concurrencia: el semáforo de GitHub Actions

| Primitivo | Semántica | Dónde se usa |
|---|---|---|
| `concurrency` con `cancel-in-progress: false` | **Mutex** (semáforo binario): como máximo 1 run tiene el recurso y 1 espera (`pending`). Si llega un tercero, el que esperaba se cancela y el nuevo toma su lugar | `cd.yml`, grupo `github-pages`: nunca hay dos deploys a la vez y un deploy nunca se corta a medias |
| `concurrency` con `cancel-in-progress: true` | **Preempción**: el run nuevo cancela al que está corriendo | `ci.yml` y `trivy.yml` en pull requests: un push nuevo al PR deja obsoleto el run anterior |
| Grupo distinto por commit | Sin exclusión: cada run tiene su propio grupo | `ci.yml` en `main`: cada commit obtiene su resultado, que el CD exige |
| `strategy.max-parallel: N` | **Semáforo contador**, solo entre los jobs de una misma matriz | No se usa (no hay matriz); es el primitivo si se agrega una |

El grupo es un nombre a nivel de repositorio (dos workflows con el mismo nombre de grupo se
bloquean entre sí). `gh api repos/OWNER/REPO/actions/concurrency_groups/<grupo>` muestra quién
tiene el recurso (`in_progress`) y quién espera (`pending`).

---

## v1 — CI: lint, test y build en cada PR y push a `main`

### Alcance
- `ci.yml` se dispara con `pull_request` a `main` y `push` a `main`. Sin filtros `paths` ni `tags`:
  el CD de v2 solo acepta commits cuyo push a `main` tiene un run de CI en verde.
- Stages (jobs), cada uno con checkout + setup-node + `npm ci`:

  ```
  lint (npm run lint + npm run typecheck) ─┐
                                           ├─► build (npm run build + smoke test)
  test (npm test) ─────────────────────────┘
  ```
  - `lint` y `test` corren en paralelo; `build` tiene `needs: [lint, test]`.
  - El smoke test de `build` falla si `out/index.html` no existe o no contiene `Hola mundo`.
  - Un fallo detiene el pipeline: sin `continue-on-error`, sin `|| true`, sin `if:` en los pasos.
- Permisos: `contents: read` en cada job.
- Concurrencia: en un PR, el push nuevo cancela el run anterior; en `main`, cada SHA tiene su
  grupo y nada se cancela.
  ```yaml
  concurrency:
    group: ${{ github.workflow }}-${{ github.event_name == 'pull_request' && format('pr-{0}', github.event.pull_request.number) || github.sha }}
    cancel-in-progress: true
  ```

### Criterios de aceptación (v1)
```bash
actionlint .github/workflows/*.yml
test ! -e .github/workflows/ci-cd.yml
act pull_request -W .github/workflows/ci.yml -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 \
  --container-architecture linux/amd64
git switch -c prueba-ci && git commit --allow-empty -m "uno" && git push -u origin prueba-ci
gh pr create --fill && esperar ci.yml --branch prueba-ci
git commit --allow-empty -m "dos" && git push && git commit --allow-empty -m "tres" && git push
esperar ci.yml --branch prueba-ci; gh run list --workflow ci.yml --branch prueba-ci -L 2 --json conclusion --jq '[.[].conclusion]'
gh pr merge prueba-ci --merge --delete-branch && git switch main && git pull
esperar ci.yml --branch main --commit "$(git rev-parse HEAD)"
```
- `act` termina con los tres jobs en verde (`🏁 Job succeeded`).
- El primer `esperar` termina en `success` y `gh pr checks prueba-ci` lista `lint`, `test` y
  `build` en verde.
- Los dos pushes seguidos al PR se atropellan: la lista da `["success","cancelled"]` (el más nuevo
  primero): el run de "tres" termina y el de "dos" fue cancelado (preempción).
- Tras el merge, el `esperar` del CI de `main` termina en `success`.

---

## v2 — CD manual: desplegar un git tag a GitHub Pages

### Alcance
- **Versionado con git tags.** Cada versión es un tag anotado semver `vX.Y.Z` sobre un commit de
  `main` que ya pasó CI:
  `git tag -a v1.0.0 -m "v1.0.0" && git push origin v1.0.0`.
  Empujar un tag **no** dispara ningún workflow: desplegar es un acto explícito.
- **Tags inmutables.** Un ruleset del repo (target `tag`, patrón `refs/tags/v*`, reglas `update`,
  `deletion` y `non_fast_forward`) impide mover o borrar una versión publicada. Se crea una vez:
  ```bash
  gh api -X POST repos/OWNER/REPO/rulesets --input - <<'EOF'
  {"name":"tags-de-version-inmutables","target":"tag","enforcement":"active",
   "conditions":{"ref_name":{"include":["refs/tags/v*"],"exclude":[]}},
   "rules":[{"type":"update"},{"type":"deletion"},{"type":"non_fast_forward"}]}
  EOF
  ```
- **La versión es visible en el sitio.** `app/page.tsx` agrega
  ``<p>{`Versión: ${process.env.NEXT_PUBLIC_APP_VERSION ?? "dev"}`}</p>`` y `app/page.test.tsx`
  comprueba que sin la variable muestra `Versión: dev`. Tiene que ser **un solo nodo de texto** (un
  template literal): con `Versión: {x}` el HTML exportado queda `Versión: <!-- -->v1.0.0` y el
  `grep` del criterio no lo encuentra, aunque el test unitario pase.
- `cd.yml` se dispara **solo** con `workflow_dispatch`, con un input `tag` (`type: string`,
  `required: true`). `run-name: CD ${{ inputs.tag }} por @${{ github.actor }}`.
  Se despacha **desde `main`** y construye el commit del tag: el pipeline es siempre el revisado en
  `main`, el código sale del tag, y la política por defecto del environment `github-pages` (solo
  `main`) no se toca.
- Stages (jobs):

  ```
  validate ─► build ─► deploy
  ```
  1. `validate` (`if: github.ref == 'refs/heads/main'`; permisos `contents: read`, `actions: read`):
     - el tag cumple `^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`;
     - existe: checkout **sin `ref`** (el commit de `main` despachado) con `fetch-depth: 0`, que trae
       todas las ramas y todos los tags, y `git rev-parse --verify --quiet "refs/tags/${TAG}^{commit}"`
       da su SHA. No se hace checkout de `refs/tags/<tag>`: con un tag inexistente `actions/checkout`
       fallaría con un error genérico de git antes de este chequeo;
     - está en `main`: `git merge-base --is-ancestor "$SHA" origin/main`;
     - pasó CI: `gh run list --workflow ci.yml --commit "$SHA" --branch main --event push
       --status success --limit 1 --json databaseId --jq length` da `1` (con `GH_TOKEN` y
       `GH_REPO` en `env:`);
     - publica el SHA como output del job y escribe tag + SHA en `$GITHUB_STEP_SUMMARY`.
     Cada chequeo que falla termina con `::error::` y un mensaje que dice cuál falló (formato, tag
     inexistente, no está en `main`, sin CI en verde).
  2. `build` (`needs: validate`; permisos `contents: read`, `pages: read`): checkout **por el SHA
     validado** (no por el nombre del tag), setup-node, `npm ci`, `configure-pages` (`id: pages`),
     `npm run build` con `env: BASE_PATH: ${{ steps.pages.outputs.base_path }}` y
     `NEXT_PUBLIC_APP_VERSION` = el tag, y `upload-pages-artifact` con `path: out`. Sin
     `static_site_generator` (con `next.config.ts` crearía un `next.config.js` que lo reemplaza).
  3. `deploy` (`needs: build`; permisos `pages: write`, `id-token: write`): `environment:
     {name: github-pages, url: ${{ steps.deployment.outputs.page_url }}}` y un único paso,
     `deploy-pages` (`id: deployment`). No reconstruye: publica el artefacto de `build` del mismo run.
- **Semáforo:** `concurrency: {group: github-pages, cancel-in-progress: false}` a nivel de workflow.
- **Rollback** = despachar un tag anterior.

### Criterios de aceptación (v2)
Primera versión y despachos que deben fallar. Cada despacho espera al anterior: en el grupo
`github-pages`, un run `pending` se cancela si llega otro.
```bash
npm test
git switch main && git pull && esperar ci.yml --branch main --commit "$(git rev-parse HEAD)" \
  && git tag -a v1.0.0 -m "v1.0.0" && git push origin v1.0.0
gh workflow run cd.yml --ref main -f tag=v1.0.0 && esperar cd.yml
curl -s "https://OWNER.github.io/REPO/" | grep -o "Versión: v1.0.0"
gh workflow run cd.yml --ref main -f tag=latest && esperar cd.yml; gh run view "$(ultimo cd.yml)"
gh workflow run cd.yml --ref main -f tag=v9.9.9 && esperar cd.yml; gh run view "$(ultimo cd.yml)"
git switch -c fuera-de-main && git commit --allow-empty -m "sin merge" && git tag -a v1.0.1 -m "x"
git push origin fuera-de-main v1.0.1
gh workflow run cd.yml --ref main -f tag=v1.0.1 && esperar cd.yml; gh run view "$(ultimo cd.yml)"
git tag -f -a v1.0.0 -m "movido" fuera-de-main && git push -f origin v1.0.0
git push origin :refs/tags/v1.0.0
git fetch --tags --force origin && git switch main
```
- `npm test` pasa (incluye `Versión: dev`).
- El deploy de `v1.0.0` termina en `success` y la página publicada muestra `Versión: v1.0.0`.
- Para `latest`, `v9.9.9` y `v1.0.1`, `esperar` falla y `gh run view` muestra `validate` en rojo,
  `build` y `deploy` sin correr, y en ANNOTATIONS el `::error::` con la causa (formato, tag
  inexistente, no está en `main`).
- Mover `v1.0.0` a otro commit y borrarlo son rechazados por el ruleset (el `fetch` final
  restaura el tag local).

Semáforo: tres versiones en `main`, cada una con su CI en verde, despachadas seguidas.
```bash
for v in v1.1.0 v1.2.0; do git commit --allow-empty -m "$v" && git push origin main \
  && esperar ci.yml --branch main --commit "$(git rev-parse HEAD)" \
  && git tag -a "$v" -m "$v" && git push origin "$v"; done
for v in v1.0.0 v1.1.0 v1.2.0; do gh workflow run cd.yml --ref main -f tag="$v"; sleep 3; done
gh api repos/OWNER/REPO/actions/concurrency_groups/github-pages
esperar cd.yml; gh run list --workflow cd.yml -L 3 --json displayTitle,conclusion
curl -s "https://OWNER.github.io/REPO/" | grep -o "Versión: v1.2.0"
```
- Mientras corre `v1.0.0`, el grupo `github-pages` tiene un miembro `in_progress` y uno `pending`.
- Al llegar `v1.2.0`, el pendiente `v1.1.0` se cancela: `CD v1.0.0` → `success`,
  `CD v1.1.0` → `cancelled`, `CD v1.2.0` → `success`. Nunca hay dos deploys a la vez.
- El sitio queda en `v1.2.0` (el último pedido).

---

## v3 — Trivy: vulnerabilidades en las dependencias

### Alcance
- `trivy.yml` se dispara con `pull_request` a `main`, `push` a `main`, `schedule` semanal
  (`cron: "23 6 * * 1"`, lunes 06:23 UTC: aparecen CVEs nuevos sin que cambie el código) y
  `workflow_dispatch`.
- Job `scan` (permisos `contents: read`, `security-events: write`), con
  `env: TRIVY_INCLUDE_DEV_DEPS: "true"` (Trivy omite las devDependencies por defecto, y en CI se
  ejecutan eslint, vitest y vite). Cada invocación de `trivy-action` parte de cero: no hereda los
  inputs de la anterior (sin `scan-type` usaría `image`), así que ambas llevan su lista completa.
  1. **Reporte:** `trivy-action` con `version: v0.74.0` (el default de v0.36.0 es v0.70.0, afectado
     por CVE-2026-55092), `scan-type: fs`, `scanners: vuln`, `format: sarif`,
     `output: trivy-results.sarif`, `exit-code: "0"`, `trivyignores: .trivyignore.yaml`. Todas las
     severidades; no bloquea.
  2. **Subida a code scanning:** `upload-sarif` con `sarif_file: trivy-results.sarif` (su default es
     `../results`), `category: trivy-npm` e
     `if: ${{ always() && hashFiles('trivy-results.sarif') != '' }}`.
  3. **Gate:** `trivy-action` con `scan-type: fs`, `scanners: vuln`, `skip-setup-trivy: true`,
     `cache: "false"`, `env: TRIVY_SKIP_DB_UPDATE: "true"` (misma base de datos que el reporte),
     `format: table`, `severity: HIGH,CRITICAL`, `ignore-unfixed: true`, `exit-code: "1"` y el mismo
     `trivyignores`. Bloquea el PR si hay una vulnerabilidad alta o crítica con versión corregida.
- `.trivyignore.yaml` existe siempre (la acción falla si no está), mínimo `vulnerabilities: []`.
  Cada excepción lleva `id`, `purls`, `statement` (por qué se acepta) y `expired_at` (YYYY-MM-DD):
  al vencer, el gate vuelve a fallar solo.
- Concurrencia: `group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}`,
  `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.

### Criterios de aceptación (v3)
```bash
git clone --depth 1 "https://github.com/OWNER/REPO" /tmp/repo-limpio
docker run --rm -v /tmp/repo-limpio:/src:ro aquasec/trivy:0.74.0 fs --scanners vuln \
  --include-dev-deps --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 /src
gh workflow run trivy.yml --ref main && esperar trivy.yml --event workflow_dispatch
gh api "repos/OWNER/REPO/code-scanning/analyses?tool_name=Trivy" --jq length
git switch -c dep-vulnerable main && npm install --save-exact lodash@4.17.15
git commit -am "lodash vulnerable" && git push -u origin dep-vulnerable
gh pr create --fill && esperar trivy.yml --branch dep-vulnerable
gh api "repos/OWNER/REPO/code-scanning/alerts?ref=refs/pull/$(gh pr view dep-vulnerable --json number --jq .number)/merge&tool_name=Trivy&state=open" --jq length
```
- El escaneo local, sobre un clon limpio como el que ve el runner, termina con código 0 (el
  2026-09-30 la tabla muestra `package-lock.json │ npm │ 0`).
- El run manual de `trivy.yml` termina en `success` y code scanning tiene al menos un análisis de
  Trivy.
- En el PR con `lodash@4.17.15`, `esperar` falla: el gate de Trivy queda en rojo con hallazgos HIGH
  (CVE-2020-8203, CVE-2021-23337, entre otros), y code scanning tiene alertas abiertas de Trivy en
  el PR (más de 0; en la pestaña Security, filtro `pr:<número>`: sin filtro solo se ven las de
  `main`).
- Agregar a `.trivyignore.yaml` una entrada por cada id que lista el gate (`purls:
  ["pkg:npm/lodash@4.17.15"]`, con `statement` y `expired_at` futuro), hacer push y
  `esperar trivy.yml --branch dep-vulnerable` termina en `success`. Con `expired_at` en el pasado
  vuelve a fallar. Después se cierra el PR sin merge (`gh pr close dep-vulnerable --delete-branch`).

---

## Fuera de alcance

- Proteger `main` con checks obligatorios (ruleset de rama): recomendado, pero no se pide aquí.
- Releases de GitHub y "immutable releases": el ruleset de tags cubre lo que se necesita.
- Entornos de staging o aprobaciones manuales en el environment.
