"""Pools de conexión: uno para escrituras (RW, primaria) y otro para lecturas (RO, réplica).

Ambos pasan por PgBouncer en modo transaction, por eso se desactivan los prepared
statements (prepare_threshold=None): no hay garantía de reutilizar la misma conexión.
"""

import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_KW = {"row_factory": dict_row, "prepare_threshold": None}

rw = ConnectionPool(os.environ.get("DATABASE_URL_RW", "postgresql://shop:shop@pgbouncer:5432/shop"), kwargs=_KW)
ro = ConnectionPool(os.environ.get("DATABASE_URL_RO", "postgresql://shop:shop@pgbouncer:5432/shop_ro"), kwargs=_KW)
