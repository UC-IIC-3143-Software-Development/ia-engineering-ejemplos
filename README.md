# System Design: Prototipado con IA

Material de una clase de 50 minutos sobre cómo usar LLMs y agentes de código
(Claude Code) para prototipar y programar: desde el prompt hasta los loops de
agentes, con ejemplos ejecutables y un prototipo de e-commerce guiado por un
`SPECS.md`.

## Contenido del repositorio

| Carpeta | Qué hay |
|---------|---------|
| `examples/` | Un script Python por técnica: estocasticidad, few-shot, CoT + self-consistency, alucinación, prompt injection, sicofancia, salidas estructuradas, prompt como código, loop Observar-Pensar-Actuar, ReAct + Plan-and-Execute, Reflexion y un Ralph loop real sobre `claude`. |
| `ecommerce/` | Prototipo React + FastAPI + PostgreSQL (primaria + réplica) + PgBouncer en Docker Compose, construido por versiones a partir de `SPECS.md` (v1 catálogo/carrito, v2 rate limit, v3 réplica + pooling). |

## Cómo correr

Las API keys van en un `.env` en la raíz del repo (está en `.gitignore`, nunca se
commitea). Todos los ejemplos lo cargan solos; no hay que exportar nada.

```bash
# Credenciales: copia la plantilla y completa GEMINI_API_KEY (las demás son opcionales)
cp .env.example .env

# Ejemplos: usan Gemini si hay GEMINI_API_KEY; si no, Claude (SDK o `claude -p`)
cd examples && python3 01_estocastico.py

# Prototipo e-commerce
cd ecommerce && docker compose up --build
```

## Plan de la clase (50 min)

1. LLMs son estocásticos (6 min)
2. Directo → Few-shot → Chain of Thought → Self-consistency (9 min)
3. Modos de falla: alucinación, prompt injection, sicofancia (8 min)
4. Salidas estructuradas (5 min)
5. Prompts confiables y el prompt como código (5 min)
6. Agentes y loops: OTA, Ralph, ReAct, Plan-and-Execute, Reflexion, checkpoints (10 min)
7. Demo: e-commerce prototipado con `SPECS.md` + Claude Code (4 min)
8. Cierre (2 min)
