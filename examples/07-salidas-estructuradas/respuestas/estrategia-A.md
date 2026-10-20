# Estrategia A: JSON en el prompt

## Corrida 1 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 1 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 1 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 1 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 1 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "producto": "polera",
      "cantidad": 2,
      "descripcion": "negras talla M"
    },
    {
      "producto": "gorro de lana",
      "cantidad": 1
    }
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 1 · P2 · OK

```text
```json
{
  "cliente": "John Smith",
  "items": [
    "3 tazas de cerámica"
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 1 · P3 · items.0: anidado (dict)

```text
```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "cantidad": 1,
      "descripcion": "notebook"
    },
    {
      "cantidad": 2,
      "descripcion": "mouse inalámbricos"
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 1 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 1 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
Aquí tienes los datos extraídos en formato JSON:

```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "nombre": "cuadernos universitarios",
      "cantidad": 4
    },
    {
      "nombre": "estuche",
      "cantidad": 1
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 2 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 2 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 2 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 2 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 2 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "nombre": "polera negra talla M",
      "cantidad": 2
    },
    {
      "nombre": "gorro de lana",
      "cantidad": 1
    }
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 2 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 2 · P3 · items.0: anidado (dict)

```text
```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "nombre": "notebook",
      "cantidad": 1
    },
    {
      "nombre": "mouse inalámbrico",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 2 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 2 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "producto": "cuadernos universitarios",
      "cantidad": 4
    },
    {
      "producto": "estuche",
      "cantidad": 1
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 3 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 3 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 3 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 3 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 3 · P1 · OK

```text
```json
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
```

## Corrida 3 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 3 · P3 · items.0: anidado (dict)

```text
Aquí tienes los datos extraídos en formato JSON:

```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "nombre": "notebook",
      "cantidad": 1
    },
    {
      "nombre": "mouse inalámbricos",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 3 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 3 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "producto": "cuadernos universitarios",
      "cantidad": 4
    },
    {
      "producto": "estuche",
      "cantidad": 1
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 4 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 4 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 4 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 4 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 4 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "cantidad": 2,
      "producto": "poleras negras talla M"
    },
    {
      "cantidad": 1,
      "producto": "gorro de lana"
    }
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 4 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12,
      "subtotal": 36
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 4 · P3 · items.0: anidado (dict)

```text
```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "nombre": "notebook",
      "cantidad": 1
    },
    {
      "nombre": "mouse inalámbricos",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 4 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": ["licencias de software"],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 4 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
Claro, aquí tienes los datos del pedido en formato JSON:

```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "producto": "cuadernos universitarios",
      "cantidad": 4
    },
    {
      "producto": "estuche",
      "cantidad": 1
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 5 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 5 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 5 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 5 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 5 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "producto": "polera negra talla M",
      "cantidad": 2
    },
    {
      "producto": "gorro de lana",
      "cantidad": 1
    }
  ],
  "total": 34990.00,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 5 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 5 · P3 · items.0: anidado (dict)

```text
```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "nombre": "notebook",
      "cantidad": 1
    },
    {
      "nombre": "mouse inalámbricos",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 5 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 5 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "cantidad": 4,
      "producto": "cuadernos universitarios"
    },
    {
      "cantidad": 1,
      "producto": "estuche"
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 6 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 6 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 6 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 6 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 6 · P1 · OK

```text
```json
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
```

## Corrida 6 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 6 · P3 · items.0: anidado (dict)

```text
```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "producto": "notebook",
      "cantidad": 1
    },
    {
      "producto": "mouse inalámbrico",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 6 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 6 · P5 · fecha_entrega: null

```text
¡Claro! Aquí tienes los datos extraídos en formato JSON:

```json
{
  "cliente": "Diego Fuentes",
  "items": [
    "4 cuadernos universitarios",
    "1 estuche"
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 7 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 7 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 7 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 7 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 7 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "producto": "polera",
      "cantidad": 2,
      "color": "negra",
      "talla": "M"
    },
    {
      "producto": "gorro de lana",
      "cantidad": 1
    }
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 7 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 7 · P3 · items.0: anidado (dict)

```text
```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "producto": "notebook",
      "cantidad": 1
    },
    {
      "producto": "mouse inalámbricos",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 7 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 7 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "cantidad": 4,
      "producto": "cuadernos universitarios"
    },
    {
      "cantidad": 1,
      "producto": "estuche"
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 8 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 8 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 8 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 8 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 8 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "producto": "polera negra talla M",
      "cantidad": 2
    },
    {
      "producto": "gorro de lana",
      "cantidad": 1
    }
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 8 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 8 · P3 · items.0: anidado (dict)

```text
```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "nombre": "notebook",
      "cantidad": 1
    },
    {
      "nombre": "mouse inalámbricos",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 8 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 8 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "producto": "cuadernos universitarios",
      "cantidad": 4
    },
    {
      "producto": "estuche",
      "cantidad": 1
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 9 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 9 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 9 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 9 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 9 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "producto": "polera negra",
      "cantidad": 2,
      "talla": "M"
    },
    {
      "producto": "gorro de lana",
      "cantidad": 1
    }
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 9 · P2 · items.0: anidado (dict)

```text
```json
{
  "cliente": "John Smith",
  "items": [
    {
      "producto": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 9 · P3 · items.0: anidado (dict)

```text
Aquí tienes los datos extraídos en formato JSON:

```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "producto": "notebook",
      "cantidad": 1
    },
    {
      "producto": "mouse inalámbrico",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 9 · P4 · OK

```text
```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 9 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "producto": "cuadernos universitarios",
      "cantidad": 4
    },
    {
      "producto": "estuche",
      "cantidad": 1
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

## Corrida 10 · T1 · OK

```text
```json
{
  "categoria": "facturacion"
}
```
```

## Corrida 10 · T2 · OK

```text
```json
{
  "categoria": "soporte_tecnico"
}
```
```

## Corrida 10 · T3 · OK

```text
```json
{
  "categoria": "ventas"
}
```
```

## Corrida 10 · T4 · OK

```text
```json
{
  "categoria": "otro"
}
```
```

## Corrida 10 · P1 · items.0: anidado (dict)

```text
```json
{
  "cliente": "María Pérez",
  "items": [
    {
      "producto": "polera",
      "cantidad": 2,
      "color": "negra",
      "talla": "M"
    },
    {
      "producto": "gorro de lana",
      "cantidad": 1
    }
  ],
  "total": 34990,
  "moneda": "CLP",
  "fecha_entrega": "2026-10-15"
}
```
```

## Corrida 10 · P2 · items.0: anidado (dict)

```text
Aquí tienes los datos extraídos en formato JSON:

```json
{
  "cliente": "John Smith",
  "items": [
    {
      "nombre": "tazas de cerámica",
      "cantidad": 3,
      "precio_unitario": 12
    }
  ],
  "total": 36,
  "moneda": "USD",
  "fecha_entrega": "2026-11-02"
}
```
```

## Corrida 10 · P3 · items.0: anidado (dict)

```text
Claro, aquí tienes los datos extraídos en formato JSON:

```json
{
  "cliente": "Camila Rojas",
  "items": [
    {
      "nombre": "notebook",
      "cantidad": 1
    },
    {
      "nombre": "mouse inalámbricos",
      "cantidad": 2
    }
  ],
  "total": 650000,
  "moneda": "CLP",
  "fecha_entrega": "2026-12-01"
}
```
```

## Corrida 10 · P4 · OK

```text
Claro, aquí tienes los datos extraídos en formato JSON:

```json
{
  "cliente": "Pedro González",
  "items": [
    "5 licencias de software"
  ],
  "total": 1250.50,
  "moneda": "USD",
  "fecha_entrega": "2026-12-04"
}
```
```

## Corrida 10 · P5 · items.0: anidado (dict) · fecha_entrega: null

```text
```json
{
  "cliente": "Diego Fuentes",
  "items": [
    {
      "producto": "cuadernos universitarios",
      "cantidad": 4
    },
    {
      "producto": "estuche",
      "cantidad": 1
    }
  ],
  "total": 12000,
  "moneda": "CLP",
  "fecha_entrega": null
}
```
```

