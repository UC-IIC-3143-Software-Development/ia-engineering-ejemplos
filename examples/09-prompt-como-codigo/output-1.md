2026-09-28 · modelo: gemini-2.5-flash · comando: `COLUMNS=110 python3 main.py` (3 corridas por caso y versión, 113 s)

```text
╭──────────────────────────────────────────────────────────────────────────────────────────╮
│ Prompt como código: registry + arnés de regresión                                        │
│ Los mismos 10 casos contra triage_ticket@v1 (producción) y triage_ticket@v2 (candidata). │
│ Modelo: gemini-2.5-flash | 3 corridas por caso y versión                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────╯

──────────────────────────────────────────── Registry de prompts ─────────────────────────────────────────────
  Clave             ┃  Estado                  ┃  Líneas  
━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━
  triage_ticket@v1  │  producción (congelada)  │      19  
  triage_ticket@v2  │  candidata               │      23  

Diff triage_ticket@v1 → triage_ticket@v2
     alta  — caída del servicio, pérdida de datos, ventas que se pierden ahora
  -          mismo o equipos completos que no pueden iniciar sesión.
  -  media — experiencia degradada, fallas parciales, reembolsos y cobros
  -          incorrectos o duplicados.
  -  baja  — preguntas generales, copias de facturas, tokens o documentación
  -          de la API para uso personal, dónde cambiar la contraseña,
  -          sugerencias o felicitaciones.
  +          mismo o incidentes de seguridad.
  +  media — experiencia degradada, fallas parciales o solicitudes con plazo.
  +  baja  — preguntas generales, sugerencias o felicitaciones.
   
     facturacion — cobros, pagos, facturas, reembolsos o cambios de plan.
  -  tecnico     — errores, fallas, rendimiento, API, tokens o documentación técnica.
  -  general     — cuenta, perfil, contraseña, datos de despacho y todo lo demás.
  +  tecnico     — errores, fallas, rendimiento e incidentes de seguridad.
  +  general     — todo lo demás.
  +
  +Reglas adicionales:
  +  - Un cobro duplicado o no reconocido es urgencia alta (riesgo de contracargo).
  +  - Por seguridad, todo mensaje que mencione "contraseña", "cuenta", "acceso",
  +    "sesión", "API" o "token" DEBE ser urgencia alta y categoría tecnico,
  +    sin importar el contexto.
  +  - Pedir facturas para la contabilidad tiene plazo tributario: urgencia media.
   

── triage_ticket@v1 (producción) ──────────────────────────────
  Caso #01: ●●●  10.9s     Caso #02: ●●●   5.8s     Caso #03: ●●●   5.6s     Caso #04: ●●●   4.1s   
  Caso #05: ●●●   6.0s     Caso #06: ○○○   6.5s     Caso #07: ●●●   4.0s     Caso #08: ●●●   5.1s   
  Caso #09: ○○○   7.3s     Caso #10: ○○○   5.7s   

── triage_ticket@v2 (candidata) ──────────────────────────────
  Caso #01: ●●●   5.2s     Caso #02: ●●●   6.7s     Caso #03: ○○○   5.2s     Caso #04: ○○○   3.8s   
  Caso #05: ●●●   5.0s     Caso #06: ●●●   4.3s     Caso #07: ●●●   6.8s     Caso #08: ○○○   6.4s   
  Caso #09: ●●●   3.9s     Caso #10: ●●●   4.6s   

────────────────────────────────────────────────── Resumen ───────────────────────────────────────────────────

                                  Reporte de regresión (mayoría de corridas)                                  
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃  # ┃ Mensaje del cliente          ┃     Esperado     ┃        v1         ┃        v2         ┃    Delta    ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│  1 │ Nadie de mi equipo puede     │   alta/tecnico   │     PASA 3/3      │     PASA 3/3      │    igual    │
│    │ iniciar sesión desde esta    │                  │                   │                   │             │
│    │ mañana y hoy tenemos que     │                  │                   │                   │             │
│    │ despachar pedidos.           │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  2 │ ¿Cómo cambio mi foto de      │   baja/general   │     PASA 3/3      │     PASA 3/3      │    igual    │
│    │ perfil?                      │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  3 │ Necesito una copia de la     │ baja/facturacion │     PASA 3/3      │     FALLA 0/3     │ REGRESIÓN ✗ │
│    │ factura de marzo para mi     │                  │                   │ media/facturacion │             │
│    │ contador.                    │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  4 │ ¿Dónde encuentro el token de │   baja/tecnico   │     PASA 3/3      │     FALLA 0/3     │ REGRESIÓN ✗ │
│    │ la API para un proyecto      │                  │                   │   alta/tecnico    │             │
│    │ personal?                    │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  5 │ El checkout tira error 500 y │   alta/tecnico   │     PASA 3/3      │     PASA 3/3      │    igual    │
│    │ estamos perdiendo ventas     │                  │                   │                   │             │
│    │ ahora mismo.                 │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  6 │ Me cobraron dos veces la     │ alta/facturacion │     FALLA 0/3     │     PASA 3/3      │  ARREGLO ✓  │
│    │ misma compra en la tarjeta.  │                  │ media/facturacion │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  7 │ La app está muy lenta al     │  media/tecnico   │     PASA 3/3      │     PASA 3/3      │    igual    │
│    │ recorrer el catálogo.        │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  8 │ Quiero actualizar mi         │   baja/general   │     PASA 3/3      │     FALLA 0/3     │ REGRESIÓN ✗ │
│    │ contraseña por seguridad,    │                  │                   │   alta/tecnico    │             │
│    │ ¿dónde está esa opción?      │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│  9 │ Alguien entró a mi cuenta    │   alta/tecnico   │     FALLA 0/3     │     PASA 3/3      │  ARREGLO ✓  │
│    │ sin permiso y cambió la      │                  │   alta/general    │                   │             │
│    │ dirección de despacho.       │                  │                   │                   │             │
├────┼──────────────────────────────┼──────────────────┼───────────────────┼───────────────────┼─────────────┤
│ 10 │ Aparece en mi tarjeta un     │ alta/facturacion │     FALLA 0/3     │     PASA 3/3      │  ARREGLO ✓  │
│    │ cargo de su tienda que no    │                  │ media/facturacion │                   │             │
│    │ reconozco.                   │                  │                   │                   │             │
└────┴──────────────────────────────┴──────────────────┴───────────────────┴───────────────────┴─────────────┘

                                       Métricas por versión                                        
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Métrica                          ┃ triage_ticket@v1 (producción) ┃ triage_ticket@v2 (candidata) ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Casos que pasan                  │             7/10              │             7/10             │
├──────────────────────────────────┼───────────────────────────────┼──────────────────────────────┤
│ Llamadas correctas               │             21/30             │            21/30             │
├──────────────────────────────────┼───────────────────────────────┼──────────────────────────────┤
│ Casos inestables                 │               0               │              0               │
├──────────────────────────────────┼───────────────────────────────┼──────────────────────────────┤
│ Latencia media por llamada       │             2.0s              │             1.7s             │
├──────────────────────────────────┼───────────────────────────────┼──────────────────────────────┤
│ Arreglos (v1 falla → v2 pasa)    │               —               │              3               │
├──────────────────────────────────┼───────────────────────────────┼──────────────────────────────┤
│ Regresiones (v1 pasa → v2 falla) │               —               │              3               │
└──────────────────────────────────┴───────────────────────────────┴──────────────────────────────┘

─────────────────────────────────────────── Detalle de regresiones ───────────────────────────────────────────

Caso #03 "Necesito una copia de la factura de marzo para mi contador."
  esperado: baja/facturacion   v1: baja/facturacion (aciertos 3/3)   v2: media/facturacion (aciertos 0/3)
  Motivo: urgencia: esperado 'baja', obtuvo 'media'

╭──────────────────────────────────────────── Entrada al modelo ─────────────────────────────────────────────╮
│                                                                                                            │
│  Eres el asistente de triage del soporte de una tienda online.                                             │
│  Clasifica el mensaje del cliente con una urgencia y una categoría.                                        │
│                                                                                                            │
│  Urgencia:                                                                                                 │
│    alta  — caída del servicio, pérdida de datos, ventas que se pierden ahora                               │
│            mismo o incidentes de seguridad.                                                                │
│    media — experiencia degradada, fallas parciales o solicitudes con plazo.                                │
│    baja  — preguntas generales, sugerencias o felicitaciones.                                              │
│                                                                                                            │
│  Categoría:                                                                                                │
│    facturacion — cobros, pagos, facturas, reembolsos o cambios de plan.                                    │
│    tecnico     — errores, fallas, rendimiento e incidentes de seguridad.                                   │
│    general     — todo lo demás.                                                                            │
│                                                                                                            │
│  Reglas adicionales:                                                                                       │
│    - Un cobro duplicado o no reconocido es urgencia alta (riesgo de contracargo).                          │
│    - Por seguridad, todo mensaje que mencione "contraseña", "cuenta", "acceso",                            │
│      "sesión", "API" o "token" DEBE ser urgencia alta y categoría tecnico,                                 │
│      sin importar el contexto.                                                                             │
│    - Pedir facturas para la contabilidad tiene plazo tributario: urgencia media.                           │
│                                                                                                            │
│  Mensaje del cliente:                                                                                      │
│  Necesito una copia de la factura de marzo para mi contador.                                               │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─────────────────────────────────────────── Respuesta del modelo ───────────────────────────────────────────╮
│                                                                                                            │
│  ASISTENTE: {"urgencia": "media", "categoria": "facturacion"}                                              │
│                                                                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

Caso #04 "¿Dónde encuentro el token de la API para un proyecto personal?"
  esperado: baja/tecnico   v1: baja/tecnico (aciertos 3/3)   v2: alta/tecnico (aciertos 0/3)
  Motivo: urgencia: esperado 'baja', obtuvo 'alta'

Caso #08 "Quiero actualizar mi contraseña por seguridad, ¿dónde está esa opción?"
  esperado: baja/general   v1: baja/general (aciertos 3/3)   v2: alta/tecnico (aciertos 0/3)
  Motivo: urgencia: esperado 'baja', obtuvo 'alta'; categoria: esperado 'general', obtuvo 'tecnico'

VEREDICTO: NO PROMOVER triage_ticket@v2. Arregla 3 caso(s) pero rompe 3 que triage_ticket@v1 resolvía; 
triage_ticket@v1 sigue en producción. El total (7/10 vs 7/10) lo esconde: solo la comparación caso a caso lo 
muestra.

```
