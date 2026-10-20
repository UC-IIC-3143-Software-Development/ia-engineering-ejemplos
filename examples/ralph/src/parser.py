"""Parser mínimo de líneas 'clave=valor' (objetivo de los tests del Ralph loop)."""


def parse_line(line: str) -> tuple[str, str]:
    """Devuelve (clave, valor) de 'clave=valor'. Recorta espacios. Lanza ValueError si no hay '='."""
    if "=" not in line:
        raise ValueError(f"línea sin '=': {line!r}")
    key, value = line.split("=", 1)
    return key.strip(), value.strip()


def parse_text(text: str) -> dict[str, str]:
    """Parsea varias líneas; ignora vacías y comentarios que empiezan con '#'."""
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = parse_line(line)
        result[key] = value
    return result


def to_int(value: str, default: int = 0) -> int:
    """Convierte a int; si no es numérico devuelve `default`."""
    try:
        return int(value)
    except ValueError:
        return default
