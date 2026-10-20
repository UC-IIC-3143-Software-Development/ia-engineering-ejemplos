Corrida del 2026-09-28 · LiteLLM 1.103 + Gemini · `COLUMNS=120 python3 main.py`

```text
╭──────────────────────────────────────────────────────────────────────╮
│ LiteLLM: tokens y costo de un prompt                                 │
│ Mismo prompt, misma llamada (litellm.completion), distintos modelos. │
│ Modelos: 5 escenarios | 1 ejecución cada uno                         │
╰──────────────────────────────────────────────────────────────────────╯
╭───────────────────────────────────────────────── Entrada al modelo ──────────────────────────────────────────────────╮
│ Eres el asistente de soporte de una tienda online. Clasifica este ticket en una de: facturacion, envio,              │
│ producto_defectuoso, otro. Luego redacta una respuesta de 2 frases para el cliente.                                  │
│                                                                                                                      │
│ Ticket: "Compré unas zapatillas hace 10 días, me llegaron con la suela despegada y además me cobraron el envío dos   │
│ veces."                                                                                                              │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
              Precios según LiteLLM (USD por millón de tokens)               
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Modelo                        ┃   Entrada ┃ Salida (incluye razonamiento) ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ gemini/gemini-3.5-flash-lite  │ $0.300000 │                         $2.50 │
│ gemini/gemini-2.5-flash       │ $0.300000 │                         $2.50 │
│ gemini/gemini-3.8-flash       │ $0.750000 │                         $3.75 │
│ gemini/gemini-3.1-pro-preview │     $2.00 │                        $12.00 │
└───────────────────────────────┴───────────┴───────────────────────────────┘
  o 3.5 Flash-Lite  1.2s · 169 tokens · $0.000249
  o 2.5 Flash (razonamiento por defecto) 10.8s · 2024 tokens · $0.004886
  o 2.5 Flash (razonamiento apagado)  1.1s · 152 tokens · $0.000206
  o 3.8 Flash  3.7s · 782 tokens · $0.002695
  o 3.1 Pro (preview)  9.7s · 1084 tokens · $0.012218
╭─────────────────────────────────────── Respuesta del modelo (3.5 Flash-Lite) ────────────────────────────────────────╮
│ Clasificación: producto_defectuoso (también aplica envio y facturacion, pero el problema principal físico es el      │
│ defecto del producto).                                                                                               │
│                                                                                                                      │
│ Respuesta para el cliente: Lamentamos mucho el inconveniente con tus zapatillas y el doble cobro del envío. Por      │
│ favor, responde a este mensaje con una foto del defecto y tus datos para gestionar inmediatamente el reembolso del   │
│ envío y el cambio de tu producto.                                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
──────────────────────────────────────────── Resumen: uso de tokens y costo ────────────────────────────────────────────
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃                ┃                ┃   Tokens salida ┃              ┃          ┃             ┃             ┃            ┃
┃                ┃                ┃        (texto + ┃     De ellos ┃          ┃       Costo ┃       Costo ┃      Costo ┃
┃ Escenario      ┃ Tokens entrada ┃         razon.) ┃ razonamiento ┃ Latencia ┃ 1 ejecución ┃ 1.000 ejec. ┃   1 millón ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 3.5 Flash-Lite │             79 │              90 │       0 (0%) │     1.2s │   $0.000249 │   $0.248700 │    $248.70 │
├────────────────┼────────────────┼─────────────────┼──────────────┼──────────┼─────────────┼─────────────┼────────────┤
│ 2.5 Flash      │             79 │            1945 │   1873 (96%) │    10.8s │   $0.004886 │       $4.89 │  $4,886.20 │
│ (razonamiento  │                │                 │              │          │             │             │            │
│ por defecto)   │                │                 │              │          │             │             │            │
├────────────────┼────────────────┼─────────────────┼──────────────┼──────────┼─────────────┼─────────────┼────────────┤
│ 2.5 Flash      │             79 │              73 │       0 (0%) │     1.1s │   $0.000206 │   $0.206200 │    $206.20 │
│ (razonamiento  │                │                 │              │          │             │             │            │
│ apagado)       │                │                 │              │          │             │             │            │
├────────────────┼────────────────┼─────────────────┼──────────────┼──────────┼─────────────┼─────────────┼────────────┤
│ 3.8 Flash      │             79 │             703 │    636 (90%) │     3.7s │   $0.002695 │       $2.70 │  $2,695.50 │
├────────────────┼────────────────┼─────────────────┼──────────────┼──────────┼─────────────┼─────────────┼────────────┤
│ 3.1 Pro        │             79 │            1005 │    935 (93%) │     9.7s │   $0.012218 │      $12.22 │ $12,218.00 │
│ (preview)      │                │                 │              │          │             │             │            │
└────────────────┴────────────────┴─────────────────┴──────────────┴──────────┴─────────────┴─────────────┴────────────┘
Costo total de esta demo: $0.020255
VEREDICTO: el mismo prompt cuesta 59x más con '3.1 Pro (preview)' que con '2.5 Flash (razonamiento apagado)'. Los tokens
de salida (incluido el razonamiento) dominan el costo: medir antes de elegir modelo.
```
