Corrida del 2026-09-28 · modelo gemini-2.5-flash · `COLUMNS=110 python3 main.py` (código de salida 1: PR bloqueado)

```text
╭──────────────────────────────────────────────────────╮
│ Bot revisor de PRs: reglas de negocio vs prompt vago │
│ Archivo: pr_checkout.py (65 líneas) | 9 reglas       │
│ Modelo: gemini-2.5-flash | 1 corrida por estrategia  │
╰──────────────────────────────────────────────────────╯
      Reglas del equipo (lo que el bot debe comprobar)       
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ ID      ┃ Regla                             ┃    Tipo     ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ NEG-01  │ Montos con Decimal                │ bloqueante  │
│ NEG-02  │ IVA desde configuración           │ advertencia │
│ NEG-03  │ Tope de descuento 30 %            │ bloqueante  │
│ SEG-01  │ Sin credenciales en el código     │ bloqueante  │
│ SEG-02  │ SQL parametrizado                 │ bloqueante  │
│ SEG-03  │ Sin datos personales en logs      │ bloqueante  │
│ PERF-01 │ Sin consultas dentro de loops     │ bloqueante  │
│ PERF-02 │ Timeout en llamadas HTTP          │ advertencia │
│ DAT-01  │ Stock y pedido en una transacción │ bloqueante  │
└─────────┴───────────────────────────────────┴─────────────┘
────────────────────────────── A) Prompt vago: "ingeniero senior + clean code" ───────────────────────────────
╭─────────────────────────────────────── Respuesta del modelo (40.5s) ───────────────────────────────────────╮
│ ¡Excelente iniciativa con este PR! Es una buena base para el flujo de checkout, y demuestra un             │
│ entendimiento de las necesidades. Sin embargo, como ingeniero senior, veo varias áreas críticas y de       │
│ buenas prácticas que debemos abordar para mejorar la seguridad, robustez, mantenibilidad y claridad del    │
│ código.                                                                                                    │
│                                                                                                            │
│ Aquí está mi revisión detallada:                                                                           │
│                                                                                                            │
│ ---------------------------------------------------------------------------------------------------------- │
│                                                                                                            │
│ Revisión del Pull Request #482                                                                             │
│                                                                                                            │
│ Título del PR: checkout con cupones de descuento y descuento de stock.                                     │
│                                                                                                            │
│ Comentarios Generales: El código implementa un flujo de checkout que incluye cálculo de totales,           │
│ integración con una API de pagos y actualización de stock en base de datos. La estructura general de       │
│ funciones es lógica, pero hay aspectos fundamentales de seguridad, manejo de transacciones, modelado de    │
│ datos y configuraciones que deben ser mejorados.                                                           │
│                                                                                                            │
│ ---------------------------------------------------------------------------------------------------------- │
│                                                                                                            │
│ Puntos Críticos y Mejoras Obligatorias:                                                                    │
│                                                                                                            │
│  1 Vulnerabilidad de SQL Injection (Crítico)                                                               │
│     • Problema: En cargar_items, la consulta SQL está construida con f-strings (f"SELECT ... WHERE id =    │
│       {linea['producto_id']}"). Esto es una vulnerabilidad de SQL Injection grave. Un atacante podría      │
│       manipular producto_id para ejecutar comandos SQL maliciosos en tu base de datos.                     │
│     • Solución: Siempre utiliza consultas parametrizadas para pasar valores a la base de datos. psycopg lo │
│       soporta perfectamente.                                                                               │
│     • Ejemplo:                                                                                             │
│                                                                                                            │
│        # EN LUGAR DE:                                                                                      │
│        # fila = conn.execute(f"SELECT id, nombre, precio FROM productos WHERE id =                         │
│        {linea['producto_id']}").fetchone()                                                                 │
│        # DEBE SER:                                                                                         │
│        with conn.cursor() as cur:                                                                          │
│            cur.execute("SELECT id, nombre, precio FROM productos WHERE id = %s", (linea['producto_id'],))  │
│            fila = cur.fetchone()                                                                           │
│                                                                                                            │
│     • Acción: Corregir todas las consultas SQL que usen f-strings para insertar valores.                   │
│  2 Manejo de Secretos (Crítico)                                                                            │
│     • Problema: PAYMENT_API_KEY está hardcodeado directamente en el código fuente. Esto es una práctica de │
│       seguridad muy deficiente. Si el código se filtra o se guarda en un repositorio público, tu clave API │
│       estaría expuesta.                                                                                    │
│     • Solución: Los secretos deben cargarse desde variables de entorno, un servicio de secretos (como AWS  │
│       Secrets Manager o HashiCorp Vault), o un archivo .env (en desarrollo, nunca para producción y        │
│       siempre ignorado por Git). DB_URL ya usa os.environ, lo cual es bueno.                               │
│     • Acción: Mover PAYMENT_API_KEY a una variable de entorno.                                             │
│  3 Transaccionalidad de la Base de Datos (Crítico para integridad de datos)                                │
│     • Problema: En checkout, hay dos conn.commit() separados. Los UPDATE de stock se confirman antes de    │
│       que se inserte el pedido. Si la inserción del pedido falla (por ejemplo, por un problema de base de  │
│       datos), el stock ya habrá sido descontado y no se revertirá, llevando a inconsistencias.             │
│     • Solución: Todas las operaciones de base de datos relacionadas con un único evento de negocio (como   │
│       un checkout) deben ser parte de una única transacción atómica. Si algo falla en la transacción, todo │
│       debe ser revertido (rollback). psycopg ofrece un excelente manejo de transacciones con bloques with. │
│     • Ejemplo:                                                                                             │
│                                                                                                            │
│        def checkout(...):                                                                                  │
│            with psycopg.connect(DB_URL) as conn:                                                           │
│                with conn.transaction(): # <-- Esto inicia una transacción                                  │
│                    items = cargar_items(conn, carrito)                                                     │
│                                                                                                            │
│                                                                                                            │
│ [... 390 líneas más]                                                                                       │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
──────────────────────────────────────── B) Bot con reglas de negocio ────────────────────────────────────────
Revisión estructurada recibida en 13.4s
                                             Resultado por regla                                              
┏━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ ID      ┃ Veredicto bot ┃          Líneas           ┃ Evidencia (cita)           ┃ ¿Cita real? ┃ Esperado  ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ NEG-01  │   no_cumple   │ 17,20,21,22,23,24,33,38,… │ subtotal = 0.0             │     sí      │ no_cumple │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ NEG-02  │   no_cumple   │            23             │ iva = neto * 0.19          │     sí      │ no_cumple │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ NEG-03  │    cumple     │           12,21           │ descuento = min(descuento, │     n/a     │  cumple   │
│         │               │                           │ subtotal * TOPE_DESCUENTO) │             │           │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ SEG-01  │   no_cumple   │            10             │ PAYMENT_API_KEY =          │     sí      │ no_cumple │
│         │               │                           │ "sk_live_51HxQ7fakeFAKEfa… │             │           │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ SEG-02  │   no_cumple   │            31             │ f"SELECT id, nombre,       │     sí      │ no_cumple │
│         │               │                           │ precio FROM productos      │             │           │
│         │               │                           │ WHERE id =                 │             │           │
│         │               │                           │ {linea['producto_id']}"    │             │           │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ SEG-03  │   no_cumple   │           39,64           │ log.info("Cobrando %s a    │     sí      │ no_cumple │
│         │               │                           │ %s", total, email)         │             │           │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ PERF-01 │   no_cumple   │           30,56           │ fila = conn.execute(       │     sí      │ no_cumple │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ PERF-02 │    cumple     │            44             │ timeout=5,                 │     n/a     │  cumple   │
├─────────┼───────────────┼───────────────────────────┼────────────────────────────┼─────────────┼───────────┤
│ DAT-01  │   no_cumple   │           58,63           │ conn.commit()              │     sí      │ no_cumple │
└─────────┴───────────────┴───────────────────────────┴────────────────────────────┴─────────────┴───────────┘
╭──────────────────────────────── Comentario que el bot publicaría en el PR ─────────────────────────────────╮
│ 🤖 Cambios requeridos                                                                                      │
│                                                                                                            │
│  • NEG-01 (líneas 17, 20, 21, 22, 23, 24, 33, 38, 39, 43, 50, 53, 54, 61): subtotal = 0.0 → Utiliza        │
│    decimal.Decimal para todas las operaciones y representaciones de montos de dinero. Importa 'from        │
│    decimal import Decimal' y convierte los valores a Decimal al leerlos de la base de datos o al           │
│    inicializarlos.                                                                                         │
│  • SEG-01 (líneas 10): PAYMENT_API_KEY = "sk_live_51HxQ7fakeFAKEfake9a8b7c6d5e4f3a2b1" → Las API keys no   │
│    deben ser literales en el código. Deben leerse de variables de entorno, por ejemplo: PAYMENT_API_KEY =  │
│    os.environ["PAYMENT_API_KEY"].                                                                          │
│  • SEG-02 (líneas 31): f"SELECT id, nombre, precio FROM productos WHERE id = {linea['producto_id']}" → Las │
│    consultas SQL deben usar parámetros (%s) en lugar de f-strings para evitar inyección SQL. Ejemplo:      │
│    conn.execute("SELECT id, nombre, precio FROM productos WHERE id = %s", (linea['producto_id'],)).        │
│  • SEG-03 (líneas 39, 64): log.info("Cobrando %s a %s", total, email) → Información sensible como el email │
│    no debe ser loggeada ni impresa directamente. Utiliza una función de enmascaramiento (p.ej.,            │
│    enmascarar(email)) antes de registrarla.                                                                │
│  • PERF-01 (líneas 30, 56): fila = conn.execute( → Evita ejecutar consultas a la base de datos dentro de   │
│    bucles (problema N+1). Para cargar ítems, considera una sola consulta con WHERE id = ANY(%s). Para      │
│    actualizar stock, usa una sola consulta con UPDATE ... WHERE id = ANY(%s) o un UPSERT.                  │
│  • DAT-01 (líneas 58, 63): conn.commit() → Las operaciones de descontar stock y registrar el pedido deben  │
│    ocurrir en una única transacción atómica. Utiliza 'with conn.transaction():' para asegurar que ambos    │
│    pasos se confirmen o reviertan juntos, y elimina los 'conn.commit()' intermedios.                       │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
────────────────────────────────────────────────── Resumen ───────────────────────────────────────────────────
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Métrica                        ┃       A) Prompt vago        ┃         B) Reglas de negocio         ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Formato de salida              │ texto libre (2594 palabras) │ JSON validado: 1 veredicto por regla │
├────────────────────────────────┼─────────────────────────────┼──────────────────────────────────────┤
│ Reglas del equipo evaluadas    │       no garantizado        │                 9/9                  │
├────────────────────────────────┼─────────────────────────────┼──────────────────────────────────────┤
│ Citas de violación verificadas │       no verificable        │                 7/7                  │
├────────────────────────────────┼─────────────────────────────┼──────────────────────────────────────┤
│ Violaciones reales detectadas  │    hay que leerlo a mano    │                 7/7                  │
├────────────────────────────────┼─────────────────────────────┼──────────────────────────────────────┤
│ Veredictos correctos           │             n/a             │                 9/9                  │
├────────────────────────────────┼─────────────────────────────┼──────────────────────────────────────┤
│ Usable por CI (exit code)      │             no              │                  sí                  │
└────────────────────────────────┴─────────────────────────────┴──────────────────────────────────────┘
VEREDICTO: PR BLOQUEADO, 6 reglas bloqueantes incumplidas (NEG-01, SEG-01, SEG-02, SEG-03, PERF-01, DAT-01).
```
