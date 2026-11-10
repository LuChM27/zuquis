"""Idempotency-Key para operaciones que mueven dinero o inventario (sección 9).

Uso en un router:

    @router.post("/ventas", status_code=201)
    def crear(datos: ..., ctx = Depends(requiere("ventas.crear")),
              idem: Idempotencia = Depends(idempotencia(requerida=True)), db = Depends(obtener_db)):
        if (previa := idem.iniciar(db, ctx)) is not None:
            return previa
        salida = service.crear(...)
        idem.guardar(db, 201, salida)
        db.commit()
        return salida

Funcionamiento: la clave se inserta en la misma transacción de la operación. Si llega una
segunda petición con la misma clave mientras la primera sigue en curso, PostgreSQL la hace
esperar en el índice único; cuando la primera confirma, la segunda devuelve la respuesta
guardada sin repetir la operación. Si la primera falla, la segunda se ejecuta normalmente.
"""

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.core.idempotencia_models import Idempotencia as RegistroIdempotencia
from app.shared.errores import Conflicto, ErrorNegocio
from app.shared.fechas import ahora

VIGENCIA = timedelta(hours=48)


@dataclass
class Idempotencia:
    clave: str | None
    ruta: str
    hash_cuerpo: str
    usuario_id: Any = None

    def iniciar(self, db: Session, ctx: Contexto) -> JSONResponse | None:
        """Devuelve la respuesta guardada si la operación ya se hizo; si no, reserva la clave."""
        if self.clave is None:
            return None
        self.usuario_id = ctx.usuario_id
        valores = {
            "usuario_id": ctx.usuario_id,
            "clave": self.clave,
            "ruta": self.ruta,
            "hash_cuerpo": self.hash_cuerpo,
            "expira_en": ahora() + VIGENCIA,
        }
        insertada = db.execute(
            insert(RegistroIdempotencia)
            .values(**valores)
            .on_conflict_do_nothing(index_elements=["usuario_id", "clave"])
            .returning(RegistroIdempotencia.id)
        ).scalar_one_or_none()
        if insertada is not None:
            return None

        previa = db.scalar(
            select(RegistroIdempotencia).where(
                RegistroIdempotencia.usuario_id == ctx.usuario_id,
                RegistroIdempotencia.clave == self.clave,
            )
        )
        if previa is None or previa.expira_en <= ahora():
            # Venció: se descarta y se trata como clave nueva.
            db.execute(
                delete(RegistroIdempotencia).where(
                    RegistroIdempotencia.usuario_id == ctx.usuario_id,
                    RegistroIdempotencia.clave == self.clave,
                )
            )
            db.execute(insert(RegistroIdempotencia).values(**valores))
            return None
        if previa.ruta != self.ruta or previa.hash_cuerpo != self.hash_cuerpo:
            raise Conflicto(
                "IDEMPOTENCIA_CONFLICTO",
                "Esta clave de operación ya se usó con datos distintos.",
                {"clave": self.clave},
            )
        if previa.estado_http is None:
            raise Conflicto("IDEMPOTENCIA_EN_PROCESO", "La operación todavía se está procesando.")
        return JSONResponse(
            status_code=previa.estado_http,
            content=previa.respuesta,
            headers={"Idempotent-Replayed": "true"},
        )

    def guardar(self, db: Session, estado_http: int, respuesta: Any) -> None:
        if self.clave is None:
            return
        registro = db.scalar(
            select(RegistroIdempotencia).where(
                RegistroIdempotencia.clave == self.clave,
                RegistroIdempotencia.usuario_id == self.usuario_id,
            )
        )
        registro.estado_http = estado_http
        registro.respuesta = jsonable_encoder(respuesta)


def idempotencia(requerida: bool = False):
    async def dependencia(
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
    ) -> Idempotencia:
        if idempotency_key is None and requerida:
            raise ErrorNegocio(
                "IDEMPOTENCIA_REQUERIDA", "Falta el encabezado Idempotency-Key.", status=400
            )
        cuerpo = await request.body()
        return Idempotencia(
            clave=idempotency_key.strip() if idempotency_key else None,
            ruta=f"{request.method} {request.url.path}",
            hash_cuerpo=hashlib.sha256(cuerpo).hexdigest(),
        )

    return dependencia


def limpiar_vencidas(db: Session) -> int:
    resultado = db.execute(
        delete(RegistroIdempotencia).where(RegistroIdempotencia.expira_en <= ahora())
    )
    return resultado.rowcount or 0
