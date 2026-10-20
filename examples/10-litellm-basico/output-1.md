Corrida del 2026-09-30 · LiteLLM 1.103 + Gemini · `COLUMNS=110 python3 main.py` (modo repetible: reproduce
`grabacion.json`, grabada con `--en-vivo`)

```text
╭────────────────────────────────────────────────────────────────────────╮
│ LiteLLM en producción: reintentos, rate limit, cooldown y fallback     │
│ 5 tickets al grupo soporte (flash-lite, cuota 2 rpm). Respaldo: flash. │
│ Modo: repetible (grabación)                                            │
╰────────────────────────────────────────────────────────────────────────╯
Ticket 1 · 429 simulado del proveedor: el Router espera y reintenta
  x soporte/router: RateLimitError This is a mock exception for model=soporte, to trigger a rate limit error.
  ok soporte/flash-lite · reintentos=1 · fallbacks=0 · 65/37 tokens · $0.000112
    facturacion: Hola, lamentamos el inconveniente con el cobro doble y la demora de tu pedido, ya estamos re…
Ticket 2 · Llamada normal
  ok soporte/flash-lite · reintentos=0 · fallbacks=0 · 65/37 tokens · $0.000112
    facturacion: Hola, lamentamos el inconveniente con el cobro doble y la demora de tu pedido, ya estamos re…
Ticket 3 · Cuota propia agotada: al respaldo, sin llamar al proveedor
  x soporte/flash-lite: RateLimitError Model rate limit exceeded. RPM limit=2, current usage=3
  ok respaldo/flash · reintentos=0 · fallbacks=1 · 65/516 tokens · $0.001984
    facturacion: Lamentamos el inconveniente, revisaremos el cobro duplicado para reembolsarlo de inmediato y…
Ticket 4 · Segundo rechazo: flash-lite sale de rotación (cooldown)
  x soporte/flash-lite: RateLimitError Model rate limit exceeded. RPM limit=2, current usage=4
  ok respaldo/flash · reintentos=0 · fallbacks=1 · 65/516 tokens · $0.001984
    facturacion: Lamentamos el inconveniente, revisaremos el cobro duplicado para reembolsarlo de inmediato y…
Ticket 5 · flash-lite en cooldown: directo al respaldo
  x soporte/router: RouterRateLimitError No deployments available for selected model, Try again in 60 seconds…
  ok respaldo/flash · reintentos=0 · fallbacks=1 · 65/516 tokens · $0.001984
    facturacion: Lamentamos el inconveniente, revisaremos el cobro duplicado para reembolsarlo de inmediato y…

VEREDICTO: 5/5 tickets respondidos · reintentos: 1 · al respaldo: 3
Costo: $0 en esta corrida (las respuestas grabadas cuestan $0.006175 en vivo).
```
