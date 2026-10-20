# Estrategia C: Modo estructurado

## Corrida 1 · T1 · OK

```text
{"categoria": "facturacion"}
```

## Corrida 1 · T2 · OK

```text
{"categoria": "soporte_tecnico"}
```

## Corrida 1 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 1 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 1 · P1 · OK

```text
{"cliente":"María Pérez","items":["2 poleras negras talla M","1 gorro de lana"],"total":34990,"moneda":"CLP","fecha_entrega":"2026-10-15"}
```

## Corrida 1 · P2 · OK

```text
{
"cliente": "John Smith",
"items": ["3 tazas de cerámica"],
"total": 36,
"moneda": "USD",
"fecha_entrega": "2026-11-02"
}
```

## Corrida 1 · P3 · OK

```text
{
"cliente": "Camila Rojas",
"items": ["1 notebook", "2 mouse inalambricos"],
"total": 650000,
"moneda": "CLP",
"fecha_entrega": "2026-12-01"
}
```

## Corrida 1 · P4 · OK

```text
{
  "cliente": "Pedro González",
  "items": ["5 licencias de software"],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```

## Corrida 1 · P5 · fecha_entrega='0001-01-01'

```text
{
"cliente": "Diego Fuentes",
"items": ["4 cuadernos universitarios", "1 estuche"],
"total": 12000,
"moneda": "CLP",
"fecha_entrega": "0001-01-01"
}
```

## Corrida 2 · T1 · OK

```text
{"categoria":"facturacion"}
```

## Corrida 2 · T2 · OK

```text
{"categoria": "soporte_tecnico"}
```

## Corrida 2 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 2 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 2 · P1 · OK

```text
{
"cliente": "María Pérez",
"items": ["2 poleras negras talla M", "1 gorro de lana"],
"total": 34990,
"moneda": "CLP",
"fecha_entrega": "2026-10-15"
}
```

## Corrida 2 · P2 · OK

```text
{
"cliente": "John Smith",
"items": ["3 tazas de cerámica"],
"total": 36,
"moneda": "USD",
"fecha_entrega": "2026-11-02"
}
```

## Corrida 2 · P3 · OK

```text
{
  "cliente": "Camila Rojas",
  "items": ["1 notebook", "2 mouse inalambricos"],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```

## Corrida 2 · P4 · OK

```text
{"cliente":"Pedro González","items":["5 licencias de software"],"total":1250.50,"moneda":"USD","fecha_entrega":"2026-12-04"}
```

## Corrida 2 · P5 · fecha_entrega='0000-00-00'

```text
{"cliente": "Diego Fuentes", "items": ["4 cuadernos universitarios", "1 estuche"], "total": 12000, "moneda": "CLP", "fecha_entrega": "0000-00-00"}
```

## Corrida 3 · T1 · OK

```text
{"categoria": "facturacion"}
```

## Corrida 3 · T2 · OK

```text
{"categoria": "soporte_tecnico"}
```

## Corrida 3 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 3 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 3 · P1 · OK

```text
{
  "cliente": "María Pérez",
  "items": ["2 poleras negras talla M", "1 gorro de lana"],
  "total": 34990.0,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```

## Corrida 3 · P2 · OK

```text
{
"cliente": "John Smith",
"items": ["3 tazas de cerámica"],
"total": 36,
"moneda": "USD",
"fecha_entrega": "2026-11-02"
}
```

## Corrida 3 · P3 · OK

```text
{
"cliente": "Camila Rojas",
"items": ["1 notebook", "2 mouse inalámbricos"],
"total": 650000,
"moneda": "CLP",
"fecha_entrega": "2026-12-01"
}
```

## Corrida 3 · P4 · OK

```text
{"cliente":"Pedro González","items":["licencias de software"],"total":1250.50,"moneda":"USD","fecha_entrega":"2026-12-04"}
```

## Corrida 3 · P5 · fecha_entrega='9999-12-31'

```text
{
  "cliente": "Diego Fuentes",
  "items": [
    "4 cuadernos universitarios",
    "1 estuche"
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": "9999-12-31"
}
```

## Corrida 4 · T1 · OK

```text
{"categoria":"facturacion"}
```

## Corrida 4 · T2 · OK

```text
{"categoria": "soporte_tecnico"}
```

## Corrida 4 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 4 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 4 · P1 · OK

```text
{"cliente":"María Pérez","items":["2 poleras negras talla M","1 gorro de lana"],"total":34990,"moneda":"CLP","fecha_entrega":"2026-10-15"}
```

## Corrida 4 · P2 · OK

```text
{
  "cliente": "John Smith",
  "items": ["3 tazas de cerámica"],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```

## Corrida 4 · P3 · OK

```text
{
  "cliente": "Camila Rojas",
  "items": ["notebook", "mouse inalámbricos"],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```

## Corrida 4 · P4 · OK

```text
{
  "cliente": "Pedro González",
  "items": ["5 licencias de software"],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```

## Corrida 4 · P5 · fecha_entrega='9999-12-31'

```text
{
"cliente": "Diego Fuentes",
"items": ["4 cuadernos universitarios", "1 estuche"],
"total": 12000,
"moneda": "CLP",
"fecha_entrega": "9999-12-31"
}
```

## Corrida 5 · T1 · OK

```text
{"categoria":"facturacion"}
```

## Corrida 5 · T2 · OK

```text
{"categoria":"soporte_tecnico"}
```

## Corrida 5 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 5 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 5 · P1 · OK

```text
{"cliente":"María Pérez","items":["2 poleras negras talla M","1 gorro de lana"],"total":34990,"moneda":"CLP","fecha_entrega":"2026-10-15"}
```

## Corrida 5 · P2 · OK

```text
{
  "cliente": "John Smith",
  "items": ["3 tazas de cerámica"],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```

## Corrida 5 · P3 · OK

```text
{"cliente":"Camila Rojas","items":["1 notebook","2 mouse inalambricos"],"total":650000,"moneda":"CLP","fecha_entrega":"2026-12-01"}
```

## Corrida 5 · P4 · OK

```text
{
"cliente": "Pedro González",
"items": ["licencias de software"],
"total": 1250.50,
"moneda": "USD",
"fecha_entrega": "2026-12-04"
}
```

## Corrida 5 · P5 · fecha_entrega='2024-01-01'

```text
{"cliente":"Diego Fuentes","items":["4 cuadernos universitarios","1 estuche"],"total":12000,"moneda":"CLP","fecha_entrega":"2024-01-01"}
```

## Corrida 6 · T1 · OK

```text
{"categoria": "facturacion"}
```

## Corrida 6 · T2 · OK

```text
{"categoria":"soporte_tecnico"}
```

## Corrida 6 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 6 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 6 · P1 · OK

```text
{
  "cliente": "María Pérez",
  "items": ["2 poleras negras talla M", "1 gorro de lana"],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```

## Corrida 6 · P2 · OK

```text
{"cliente":"John Smith","items":["3 tazas de cerámica"],"total":36,"moneda":"USD","fecha_entrega":"2026-11-02"}
```

## Corrida 6 · P3 · OK

```text
{
  "cliente": "Camila Rojas",
  "items": [
    "notebook",
    "mouse inalambricos"
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```

## Corrida 6 · P4 · OK

```text
{
  "cliente": "Pedro González",
  "items": ["licencias de software"],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```

## Corrida 6 · P5 · fecha_entrega='2024-12-31'

```text
{"cliente":"Diego Fuentes","items":["4 cuadernos universitarios","1 estuche"],"total":12000,"moneda":"CLP","fecha_entrega":"2024-12-31"}
```

## Corrida 7 · T1 · OK

```text
{"categoria": "facturacion"}
```

## Corrida 7 · T2 · OK

```text
{"categoria": "soporte_tecnico"}
```

## Corrida 7 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 7 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 7 · P1 · OK

```text
{
  "cliente": "María Pérez",
  "items": [
    "2 poleras negras talla M",
    "1 gorro de lana"
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```

## Corrida 7 · P2 · OK

```text
{
  "cliente": "John Smith",
  "items": ["3 tazas de cerámica"],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```

## Corrida 7 · P3 · OK

```text
{"cliente":"Camila Rojas","items":["1 notebook","2 mouse inalámbricos"],"total":650000,"moneda":"CLP","fecha_entrega":"2026-12-01"}
```

## Corrida 7 · P4 · OK

```text
{
  "cliente": "Pedro González",
  "items": ["5 licencias de software"],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```

## Corrida 7 · P5 · fecha_entrega='9999-12-31'

```text
{
  "cliente": "Diego Fuentes",
  "items": ["4 cuadernos universitarios", "1 estuche"],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": "9999-12-31"
}
```

## Corrida 8 · T1 · OK

```text
{"categoria": "facturacion"}
```

## Corrida 8 · T2 · OK

```text
{"categoria": "soporte_tecnico"}
```

## Corrida 8 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 8 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 8 · P1 · OK

```text
{
"cliente": "María Pérez",
"items": ["2 poleras negras talla M", "1 gorro de lana"],
"total": 34990,
"moneda": "CLP",
"fecha_entrega": "2026-10-15"
}
```

## Corrida 8 · P2 · OK

```text
{
  "cliente": "John Smith",
  "items": ["tazas de cerámica"],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```

## Corrida 8 · P3 · OK

```text
{
"cliente": "Camila Rojas",
"items": ["1 notebook", "2 mouse inalámbricos"],
"total": 650000,
"moneda": "CLP",
"fecha_entrega": "2026-12-01"
}
```

## Corrida 8 · P4 · OK

```text
{
"cliente": "Pedro González",
"items": ["5 licencias de software"],
"total": 1250.50,
"moneda": "USD",
"fecha_entrega": "2026-12-04"
}
```

## Corrida 8 · P5 · fecha_entrega='2024-12-31'

```text
{
  "cliente": "Diego Fuentes",
  "items": ["4 cuadernos universitarios", "1 estuche"],
  "total": 12000.0,
  "moneda": "CLP",
  "fecha_entrega": "2024-12-31"
}
```

## Corrida 9 · T1 · OK

```text
{"categoria": "facturacion"}
```

## Corrida 9 · T2 · OK

```text
{"categoria":"soporte_tecnico"}
```

## Corrida 9 · T3 · OK

```text
{"categoria":"ventas"}
```

## Corrida 9 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 9 · P1 · OK

```text
{"cliente":"María Pérez","items":["2 poleras negras talla M","1 gorro de lana"],"total":34990,"moneda":"CLP","fecha_entrega":"2026-10-15"}
```

## Corrida 9 · P2 · OK

```text
{
  "cliente": "John Smith",
  "items": ["3 tazas de cerámica"],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```

## Corrida 9 · P3 · OK

```text
{
  "cliente": "Camila Rojas",
  "items": ["1 notebook", "2 mouse inalambricos"],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```

## Corrida 9 · P4 · OK

```text
{
  "cliente": "Pedro González",
  "items": ["licencias de software"],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```

## Corrida 9 · P5 · fecha_entrega='2024-01-01'

```text
{"cliente":"Diego Fuentes","items":["4 cuadernos universitarios","1 estuche"],"total":12000,"moneda":"CLP","fecha_entrega":"2024-01-01"}
```

## Corrida 10 · T1 · OK

```text
{"categoria": "facturacion"}
```

## Corrida 10 · T2 · OK

```text
{"categoria": "soporte_tecnico"}
```

## Corrida 10 · T3 · OK

```text
{"categoria": "ventas"}
```

## Corrida 10 · T4 · OK

```text
{"categoria": "otro"}
```

## Corrida 10 · P1 · OK

```text
{
  "cliente": "María Pérez",
  "items": ["2 poleras negras talla M", "1 gorro de lana"],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```

## Corrida 10 · P2 · OK

```text
{"cliente":"John Smith","items":["3 tazas de cerámica"],"total":36,"moneda":"USD","fecha_entrega":"2026-11-02"}
```

## Corrida 10 · P3 · OK

```text
{
"cliente": "Camila Rojas",
"items": ["1 notebook", "2 mouse inalambricos"],
"total": 650000,
"moneda": "CLP",
"fecha_entrega": "2026-12-01"
}
```

## Corrida 10 · P4 · OK

```text
{"cliente":"Pedro González","items":["5 licencias de software"],"total":1250.50,"moneda":"USD","fecha_entrega":"2026-12-04"}
```

## Corrida 10 · P5 · fecha_entrega='2023-10-27'

```text
{
  "cliente": "Diego Fuentes",
  "items": [
    "4 cuadernos universitarios",
    "1 estuche"
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": "2023-10-27"
}
```

