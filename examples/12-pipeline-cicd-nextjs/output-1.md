Corrida del 2026-09-30 · modelo gemini-2.5-flash · `COLUMNS=120 python3 main.py` (código de salida 0: pipeline escrito en `salida/hola-nextjs-cicd/`)

```text
╭────────────────────────────────────────────────────────────────────────────╮
│ Pipeline CI/CD para Next.js: prompt vago vs prompt controlado              │
│ Proyecto: Next.js 16.3.7 · Node 24.21.0 · 10 reglas comprobadas por código │
│ Modelo: gemini-2.5-flash | 1 corrida por prompt                            │
╰────────────────────────────────────────────────────────────────────────────╯
               Acciones permitidas (el modelo las copia, no las elige)                
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Acción                        ┃ Versión ┃ SHA de commit                            ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ actions/checkout              │ v7.0.1  │ 3d3c42e5aac5ba805825da76410c181273ba90b1 │
│ actions/setup-node            │ v7.0.0  │ 820762786026740c76f36085b0efc47a31fe5020 │
│ actions/configure-pages       │ v6.0.0  │ 45bfe0192ca1faeb007ade9deae92b16b8254a0d │
│ actions/upload-pages-artifact │ v5.0.0  │ fc324d3547104276b827a68afc52ff2a11cc49c9 │
│ actions/deploy-pages          │ v5.0.1  │ 368f82528645a54fb793d4d04e342629a3f51346 │
└───────────────────────────────┴─────────┴──────────────────────────────────────────┘
──────────────────────────────────────────────────── A) Prompt vago ────────────────────────────────────────────────────
╭───────────────────────────────────────────────── Entrada al modelo ──────────────────────────────────────────────────╮
│ Crea un workflow de GitHub Actions con CI/CD para mi proyecto Next.js: que revise el código, corra los tests y lo    │
│ publique en GitHub Pages.                                                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────────────────────── Workflow generado (9.7s) ──────────────────────────────────────────────╮
│ name: Next.js CI/CD a GitHub Pages                                                                                   │
│                                                                                                                      │
│ on:                                                                                                                  │
│   push:                                                                                                              │
│     branches:                                                                                                        │
│       - main                                                                                                         │
│   # Permite ejecutar el workflow manualmente desde la pestaña de Actions                                             │
│   workflow_dispatch:                                                                                                 │
│                                                                                                                      │
│ env:                                                                                                                 │
│   NODE_VERSION: "20.x"                                                                                               │
│                                                                                                                      │
│ jobs:                                                                                                                │
│   build_and_deploy:                                                                                                  │
│     runs-on: ubuntu-latest                                                                                           │
│     permissions:                                                                                                     │
│       contents: read                                                                                                 │
│       pages: write                                                                                                   │
│       id-token: write                                                                                                │
│                                                                                                                      │
│     steps:                                                                                                           │
│       - name: Checkout del código                                                                                    │
│         uses: actions/checkout@v4                                                                                    │
│                                                                                                                      │
│       - name: Configurar Node.js                                                                                     │
│         uses: actions/setup-node@v4                                                                                  │
│         with:                                                                                                        │
│           node-version: ${{ env.NODE_VERSION }}                                                                      │
│           cache: 'npm' # O 'yarn' si usas Yarn                                                                       │
│                                                                                                                      │
│       - name: Instalar dependencias                                                                                  │
│         run: npm install                                                                                             │
│                                                                                                                      │
│       - name: Ejecutar Lint                                                                                          │
│         run: npm run lint                                                                                            │
│                                                                                                                      │
│       - name: Ejecutar Tests                                                                                         │
│         run: npm test                                                                                                │
│                                                                                                                      │
│       - name: Construir el sitio estático de Next.js                                                                 │
│ # [... 20 líneas más]                                                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
───────────────────────────────────────────────── B) Prompt controlado ─────────────────────────────────────────────────
╭───────────────────────────────────────────────── Entrada al modelo ──────────────────────────────────────────────────╮
│ Tarea: escribe .github/workflows/ci-cd.yml con el pipeline CI/CD del proyecto de abajo.                              │
│ - CI: en cada pull request a main y cada push a main, instala, revisa, prueba y construye.                           │
│ - CD: en push a main (o ejecución manual en main), publica en GitHub Pages lo que construyó CI.                      │
│                                                                                                                      │
│ Contexto del proyecto (hechos; úsalos tal cual):                                                                     │
│ - Next.js 16.3.7 con export estático: `npm run build` deja el sitio en out/.                                         │
│ - Versión de Node: archivo .nvmrc (24.21.0).                                                                         │
│ - Dependencias: npm, con package-lock.json versionado.                                                               │
│ - Scripts de package.json:                                                                                           │
│   - dev: next dev                                                                                                    │
│   - build: next build                                                                                                │
│   - lint: eslint                                                                                                     │
│   - typecheck: next typegen && tsc --noEmit                                                                          │
│   - test: vitest run                                                                                                 │
│ - next.config.ts usa la variable de entorno BASE_PATH como basePath. GitHub Pages sirve el                           │
│   sitio en /<nombre-del-repo>; ese valor lo entrega actions/configure-pages en su salida base_path.                  │
│ - GitHub Pages está activado con origen "GitHub Actions". El repositorio no tiene secretos.                          │
│                                                                                                                      │
│ Acciones permitidas (copia cada línea uses: exacta, con su SHA y su comentario de versión):                          │
│   uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1                                           │
│   uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0                                         │
│   uses: actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d # v6.0.0                                    │
│   uses: actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0                              │
│   uses: actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1                                       │
│                                                                                                                      │
│ Pasos:                                                                                                               │
│ 1. Job build: checkout → setup-node (cache: npm) → npm ci → npm run lint → npm run typecheck                         │
│    → npm test → configure-pages → npm run build → upload-pages-artifact.                                             │
│ 2. Job deploy: después de build, publica el artefacto con deploy-pages.                                              │
│                                                                                                                      │
│ Reglas (el programa comprueba cada una; las BLOQUEANTES son obligatorias):                                           │
│ - TRG-01 (BLOQUEANTE): on: push y pull_request con branches: [main], más workflow_dispatch.                          │
│ - REP-01 (BLOQUEANTE): runs-on: ubuntu-24.04 en cada job (ubuntu-latest cambia de versión sin aviso); setup-node con │
│ node-version-file: .nvmrc, sin node-version.                                                                         │
│ - REP-02 (BLOQUEANTE): Instala solo con `npm ci` (respeta package-lock.json). Prohibido npm install, yarn, pnpm y    │
│ bun.                                                                                                                 │
│ - REP-03 (BLOQUEANTE): Usa solo las acciones de la lista permitida, con la línea uses: exacta (fijada por SHA de     │
│ commit, no por tag).                                                                                                 │
│ - SEG-01 (BLOQUEANTE): permissions: contents: read a nivel de workflow; job build: contents: read y pages: read; job │
│ deploy: pages: write e id-token: write. Checkout con persist-credentials: false.                                     │
│ - SEG-02 (BLOQUEANTE): No uses secrets.*: el workflow se autentica solo con los permissions de cada job, así corre   │
│ en un repositorio recién creado sin configurar nada.                                                                 │
│ - CI-01 (BLOQUEANTE): El job build ejecuta, en este orden: npm ci, npm run lint, npm run typecheck, npm test, npm    │
│ run build. Solo scripts que existen en package.json. Un fallo en cualquiera detiene el job: sin continue-on-error,   │
│ sin if en esos pasos y sin ||.                                                                                       │
│ - CD-01 (BLOQUEANTE): Job deploy con needs: build, if: github.ref == 'refs/heads/main', environment name:            │
│ github-pages y url: ${{ steps.deployment.outputs.page_url }}, y un único paso: actions/deploy-pages (id:             │
│ deployment). No reconstruye nada.                                                                                    │
│ - CD-02 (BLOQUEANTE): En el job build: configure-pages (id: pages) antes de npm run build y upload-pages-artifact    │
│ (with: path: out) después, ambos con if: github.ref == 'refs/heads/main'; el paso npm run build con env: BASE_PATH:  │
│ ${{ steps.pages.outputs.base_path }}.                                                                                │
│ - OPS-01 (advertencia): timeout-minutes de máximo 15 en cada job; job deploy con concurrency: group: pages y         │
│ cancel-in-progress: false (nunca corta un deploy a medias).                                                          │
│                                                                                                                      │
│ Casos borde:                                                                                                         │
│ - En pull_request el ref es refs/pull/N/merge: no corren configure-pages, upload-pages-artifact                      │
│   ni el job deploy; BASE_PATH queda vacío y el sitio se construye para la raíz.                                      │
│ - workflow_dispatch sobre main se comporta como un push a main: construye y despliega.                               │
│                                                                                                                      │
│ Salida: el YAML completo del workflow en el campo workflow_yaml, sin cercos de markdown.                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭───────────────────────────────────────────── Workflow generado (10.3s) ──────────────────────────────────────────────╮
│ name: CI/CD                                                                                                          │
│ on:                                                                                                                  │
│   push:                                                                                                              │
│     branches:                                                                                                        │
│       - main                                                                                                         │
│   pull_request:                                                                                                      │
│     branches:                                                                                                        │
│       - main                                                                                                         │
│   workflow_dispatch:                                                                                                 │
│                                                                                                                      │
│ permissions:                                                                                                         │
│   contents: read                                                                                                     │
│                                                                                                                      │
│ jobs:                                                                                                                │
│   build:                                                                                                             │
│     runs-on: ubuntu-24.04                                                                                            │
│     timeout-minutes: 15                                                                                              │
│     permissions:                                                                                                     │
│       contents: read                                                                                                 │
│       pages: read                                                                                                    │
│     steps:                                                                                                           │
│       - name: Checkout repository                                                                                    │
│         uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1                                     │
│         with:                                                                                                        │
│           persist-credentials: false                                                                                 │
│                                                                                                                      │
│       - name: Setup Node.js                                                                                          │
│         uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0                                   │
│         with:                                                                                                        │
│           node-version-file: .nvmrc                                                                                  │
│           cache: npm                                                                                                 │
│                                                                                                                      │
│       - name: Install dependencies                                                                                   │
│         run: npm ci                                                                                                  │
│                                                                                                                      │
│       - name: Lint                                                                                                   │
│         run: npm run lint                                                                                            │
│                                                                                                                      │
│       - name: Typecheck                                                                                              │
│         run: npm run typecheck                                                                                       │
│                                                                                                                      │
│       - name: Test                                                                                                   │
│         run: npm test                                                                                                │
│                                                                                                                      │
│       - name: Configure GitHub Pages                                                                                 │
│         id: pages                                                                                                    │
│         if: github.ref == 'refs/heads/main'                                                                          │
│         uses: actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d # v6.0.0                              │
│                                                                                                                      │
│       - name: Build Next.js project                                                                                  │
│         run: npm run build                                                                                           │
│         env:                                                                                                         │
│           BASE_PATH: ${{ steps.pages.outputs.base_path }}                                                            │
│                                                                                                                      │
│       - name: Upload Pages artifact                                                                                  │
│         if: github.ref == 'refs/heads/main'                                                                          │
│         uses: actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0                        │
│         with:                                                                                                        │
│           path: out                                                                                                  │
│                                                                                                                      │
│   deploy:                                                                                                            │
│     needs: build                                                                                                     │
│     runs-on: ubuntu-24.04                                                                                            │
│     timeout-minutes: 15                                                                                              │
│     if: github.ref == 'refs/heads/main'                                                                              │
│     environment:                                                                                                     │
│       name: github-pages                                                                                             │
│       url: ${{ steps.deployment.outputs.page_url }}                                                                  │
│     concurrency:                                                                                                     │
│       group: pages                                                                                                   │
│       cancel-in-progress: false                                                                                      │
│     permissions:                                                                                                     │
│       pages: write                                                                                                   │
│       id-token: write                                                                                                │
│     steps:                                                                                                           │
│       - name: Deploy to GitHub Pages                                                                                 │
│         id: deployment                                                                                               │
│         uses: actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                             Verificación por código (mismas reglas para ambos)                             
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ ID     ┃ Regla                    ┃    Tipo     ┃ A) Vago                                ┃ B) Controlado ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ TRG-01 │ Disparadores             │ bloqueante  │ ✗ faltan disparadores: pull_request    │ ✓             │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ REP-01 │ Entorno fijo             │ bloqueante  │ ✗ job build_and_deploy: runs-on        │ ✓             │
│        │                          │             │ 'ubuntu-latest', no ubuntu-24.04       │               │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ REP-02 │ Dependencias con npm ci  │ bloqueante  │ ✗ usa `npm install`                    │ ✓             │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ REP-03 │ Acciones fijadas por SHA │ bloqueante  │ ✗ actions/checkout@v4 no está en la    │ ✓             │
│        │                          │             │ lista (fijada por SHA)                 │               │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ SEG-01 │ Permisos mínimos         │ bloqueante  │ ✗ permissions del workflow: sin        │ ✓             │
│        │                          │             │ declarar; se espera contents: read     │               │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ SEG-02 │ Sin secretos             │ bloqueante  │ ✓                                      │ ✓             │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ CI-01  │ Quality gates            │ bloqueante  │ ✗ no hay job build                     │ ✓             │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ CD-01  │ Deploy solo desde main   │ bloqueante  │ ✗ no hay job deploy                    │ ✓             │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ CD-02  │ Artefacto de Pages       │ bloqueante  │ ✗ el job build necesita                │ ✓             │
│        │                          │             │ configure-pages, npm run build y       │               │
│        │                          │             │ upload-pages-artifact                  │               │
├────────┼──────────────────────────┼─────────────┼────────────────────────────────────────┼───────────────┤
│ OPS-01 │ Límites de ejecución     │ advertencia │ ✗ job build_and_deploy sin             │ ✓             │
│        │                          │             │ timeout-minutes ≤ 15                   │               │
└────────┴──────────────────────────┴─────────────┴────────────────────────────────────────┴───────────────┘
─────────────────────────────────────────────────────── Resumen ────────────────────────────────────────────────────────
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Métrica                 ┃ A) Vago ┃ B) Controlado ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Reglas cumplidas        │  1/10   │     10/10     │
├─────────────────────────┼─────────┼───────────────┤
│ Bloqueantes incumplidas │    8    │       0       │
├─────────────────────────┼─────────┼───────────────┤
│ Líneas de YAML          │   60    │      78       │
├─────────────────────────┼─────────┼───────────────┤
│ Latencia                │  9.7s   │     10.3s     │
└─────────────────────────┴─────────┴───────────────┘
╭──────────────────────────── Próximos pasos: subir hola-nextjs-cicd y probar el pipeline ─────────────────────────────╮
│ cd salida/hola-nextjs-cicd                                                                                           │
│ git init -b main && git add -A && git commit -m "Hola mundo Next.js con CI/CD"                                       │
│ gh repo create hola-nextjs-cicd --public --source . --push                                                           │
│ gh api -X POST "repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pages" -f build_type=workflow           │
│ sleep 10 && gh run watch                                                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
VEREDICTO: pipeline listo en salida/hola-nextjs-cicd/.github/workflows/ci-cd.yml; cumple todas las reglas bloqueantes. 
El prompt vago incumple 8: TRG-01, REP-01, REP-02, REP-03, SEG-01, CI-01, CD-01, CD-02.
```
