"""Tareas nocturnas. Corre como servicio aparte (``tareas`` en Docker Compose):

python -m app.tareas

Cada noche, a la hora TAREAS_HORA (hora local del negocio, por defecto 02:00), verifica el
inventario (RN-09) y borra las claves de idempotencia vencidas. Si una tarea falla se registra
el error y se sigue con la siguiente; el servicio no se cae.
"""

import logging
import time as reloj
from datetime import datetime, time, timedelta

from app.core.config import obtener_config
from app.core.db import SesionLocal
from app.core.idempotencia import limpiar_vencidas
from app.modules.inventario.tareas import verificar_inventario
from app.shared.fechas import ahora, zona

log = logging.getLogger("app.tareas")


def proxima_ejecucion(momento: datetime, hora: time) -> datetime:
    """Siguiente vez que el reloj local marca ``hora`` después de ``momento``."""
    local = momento.astimezone(zona()) if momento.tzinfo is None else momento
    candidata = datetime.combine(local.date(), hora, tzinfo=local.tzinfo)
    if candidata <= local:
        candidata = datetime.combine(local.date() + timedelta(days=1), hora, tzinfo=local.tzinfo)
    return candidata


def ejecutar() -> None:
    for nombre, tarea in (
        ("verificación de inventario", verificar_inventario),
        ("limpieza de idempotencia", limpiar_vencidas),
    ):
        try:
            with SesionLocal() as db:
                tarea(db)
                db.commit()
            log.info("Tarea terminada: %s", nombre)
        except Exception:
            log.exception("Falló la tarea: %s", nombre)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    hora = time.fromisoformat(obtener_config().tareas_hora)
    while True:
        siguiente = proxima_ejecucion(ahora().astimezone(zona()), hora)
        log.info("Próxima ejecución: %s", siguiente.isoformat())
        reloj.sleep(max(0.0, (siguiente - ahora()).total_seconds()))
        ejecutar()


if __name__ == "__main__":
    main()
