"""Verificación nocturna del inventario (RN-09).

Por cada sede activa compara cada lote con la suma de sus movimientos y guarda el resultado.
Las diferencias aparecen como alerta en GET /inventario/alertas hasta la siguiente verificación
limpia. La corre ``app.tareas`` cada noche (servicio ``tareas`` de Docker Compose) o, a mano,
``python -m app.cli verificar-inventario``.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.configuracion.models import Sede
from app.modules.inventario import motor
from app.modules.inventario.models import VerificacionInventario
from app.shared.fechas import ahora

log = logging.getLogger(__name__)


def verificar_inventario(db: Session) -> list[VerificacionInventario]:
    """No confirma la transacción: lo hace quien la llama."""
    resultados = []
    for sede in db.scalars(select(Sede).where(Sede.activa).order_by(Sede.nombre)):
        revisados, diferencias = motor.verificar(db, sede.id)
        verificacion = VerificacionInventario(
            sede_id=sede.id,
            fecha=ahora(),
            lotes_revisados=revisados,
            diferencias=diferencias,
        )
        db.add(verificacion)
        resultados.append(verificacion)
        if diferencias:
            log.warning(
                "Inventario de %s: %d lote(s) no cuadran con sus movimientos: %s",
                sede.nombre,
                len(diferencias),
                diferencias,
            )
        else:
            log.info(
                "Inventario de %s: %d lotes revisados, sin diferencias", sede.nombre, revisados
            )
    db.flush()
    return resultados
