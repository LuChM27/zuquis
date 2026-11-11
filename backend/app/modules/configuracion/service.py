"""Configuración del negocio por sede, métodos de pago y sedes (RF-44, RF-46)."""

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar, instantanea
from app.modules.carta.models import CATEGORIAS_INICIALES, Categoria
from app.modules.configuracion.models import Configuracion, MetodoPago, Sede
from app.modules.configuracion.schemas import (
    CLAVES,
    MetodoPagoCrear,
    MetodoPagoEditar,
    SedeCrear,
    SedeEditar,
)
from app.modules.usuarios.models import Rol
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado

METODOS_INICIALES = [
    ("Efectivo", True, "1105"),
    ("Nequi", False, "1110"),
    ("Bre-B", False, "1110"),
    ("Bancolombia", False, "1110"),
    ("Otra transferencia", False, "1110"),
]

# --- Configuración --------------------------------------------------------------------------


def _a_json(clave: str, valor: Any) -> Any:
    adaptador, _ = CLAVES[clave]
    return adaptador.dump_python(valor, mode="json")


def leer(db: Session, sede_id: uuid.UUID) -> dict[str, Any]:
    """Todas las claves con su valor guardado o el valor por defecto, listas para JSON."""
    guardados = {
        c.clave: c.valor["v"]
        for c in db.scalars(select(Configuracion).where(Configuracion.sede_id == sede_id))
    }
    return {
        clave: guardados[clave] if clave in guardados else _a_json(clave, defecto)
        for clave, (_, defecto) in CLAVES.items()
    }


def valor(db: Session, sede_id: uuid.UUID, clave: str) -> Any:
    """Valor tipado de una clave, para usar desde otros servicios."""
    adaptador, defecto = CLAVES[clave]
    fila = db.scalar(
        select(Configuracion).where(Configuracion.sede_id == sede_id, Configuracion.clave == clave)
    )
    return adaptador.validate_python(fila.valor["v"]) if fila else defecto


def actualizar(db: Session, ctx: Contexto, cambios: dict[str, Any]) -> dict[str, Any]:
    desconocidas = set(cambios) - set(CLAVES)
    if desconocidas:
        raise ErrorNegocio(
            "CLAVE_DESCONOCIDA",
            "Hay claves de configuración que no existen.",
            {"claves": sorted(desconocidas)},
            422,
        )
    antes = leer(db, ctx.sede_id)
    for clave, nuevo in cambios.items():
        adaptador, _ = CLAVES[clave]
        try:
            validado = adaptador.validate_python(nuevo)
        except ValidationError as exc:
            raise ErrorNegocio(
                "VALIDACION",
                f"Valor inválido para '{clave}'.",
                {"clave": clave, "errores": [e["msg"] for e in exc.errors()]},
                422,
            ) from exc
        if clave == "tope_descuento_por_rol":
            _validar_topes(db, validado)
        fila = db.scalar(
            select(Configuracion).where(
                Configuracion.sede_id == ctx.sede_id, Configuracion.clave == clave
            )
        )
        contenido = {"v": adaptador.dump_python(validado, mode="json")}
        if fila is None:
            db.add(Configuracion(sede_id=ctx.sede_id, clave=clave, valor=contenido))
        else:
            fila.valor = contenido
    db.flush()
    despues = leer(db, ctx.sede_id)
    auditar(
        db,
        ctx,
        "editar",
        "configuracion",
        ctx.sede_id,
        antes={k: antes[k] for k in cambios},
        despues={k: despues[k] for k in cambios},
    )
    return despues


def _validar_topes(db: Session, topes: dict) -> None:
    from decimal import Decimal

    for rol_id, pct in topes.items():
        if db.get(Rol, rol_id) is None:
            raise NoEncontrado("el rol", rol_id)
        if not Decimal(0) <= pct <= Decimal(100):
            raise ErrorNegocio(
                "VALIDACION", "El tope debe estar entre 0 y 100 %.", {"rol_id": str(rol_id)}, 422
            )


# --- Métodos de pago ------------------------------------------------------------------------

_CAMPOS_METODO = ["nombre", "es_efectivo", "titular", "cuenta_puc", "activo", "orden"]


def _guardar_metodo(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        mensaje = str(exc.orig)
        if "uq_metodos_pago_efectivo_activo" in mensaje:
            raise Conflicto(
                "EFECTIVO_DUPLICADO", "Ya hay un método de efectivo activo en esta sede."
            ) from exc
        raise Conflicto("METODO_DUPLICADO", "Ya existe un método de pago con ese nombre.") from exc


def listar_metodos(db: Session, sede_id: uuid.UUID, solo_activos: bool) -> list[MetodoPago]:
    consulta = select(MetodoPago).where(MetodoPago.sede_id == sede_id)
    if solo_activos:
        consulta = consulta.where(MetodoPago.activo)
    return list(db.scalars(consulta.order_by(MetodoPago.orden, MetodoPago.nombre)))


def crear_metodo(db: Session, ctx: Contexto, datos: MetodoPagoCrear) -> MetodoPago:
    metodo = MetodoPago(sede_id=ctx.sede_id, **datos.model_dump())
    db.add(metodo)
    _guardar_metodo(db)
    auditar(
        db, ctx, "crear", "metodos_pago", metodo.id, despues=instantanea(metodo, _CAMPOS_METODO)
    )
    return metodo


def editar_metodo(
    db: Session, ctx: Contexto, metodo_id: uuid.UUID, datos: MetodoPagoEditar
) -> MetodoPago:
    metodo = db.get(MetodoPago, metodo_id)
    if metodo is None or metodo.sede_id != ctx.sede_id:
        raise NoEncontrado("el método de pago", metodo_id)
    antes = instantanea(metodo, _CAMPOS_METODO)
    for campo, nuevo in datos.model_dump(exclude_unset=True).items():
        setattr(metodo, campo, nuevo)
    _guardar_metodo(db)
    auditar(
        db,
        ctx,
        "editar",
        "metodos_pago",
        metodo.id,
        antes=antes,
        despues=instantanea(metodo, _CAMPOS_METODO),
    )
    return metodo


# --- Sedes ----------------------------------------------------------------------------------

_CAMPOS_SEDE = ["nombre", "direccion", "telefono", "activa"]


def crear_sede(db: Session, ctx: Contexto, datos: SedeCrear) -> Sede:
    sede = Sede(**datos.model_dump())
    db.add(sede)
    db.flush()
    for orden, (nombre, efectivo, puc) in enumerate(METODOS_INICIALES):
        db.add(
            MetodoPago(
                sede_id=sede.id, nombre=nombre, es_efectivo=efectivo, cuenta_puc=puc, orden=orden
            )
        )
    for orden, (nombre, icono) in enumerate(CATEGORIAS_INICIALES, start=1):
        db.add(Categoria(sede_id=sede.id, nombre=nombre, orden=orden, icono=icono))
    db.flush()
    auditar(db, ctx, "crear", "sedes", sede.id, despues=instantanea(sede, _CAMPOS_SEDE))
    return sede


def editar_sede(db: Session, ctx: Contexto, sede_id: uuid.UUID, datos: SedeEditar) -> Sede:
    sede = db.get(Sede, sede_id)
    if sede is None:
        raise NoEncontrado("la sede", sede_id)
    if datos.activa is False and sede.id == ctx.sede_id:
        raise Conflicto(
            "SEDE_EN_USO", "No puedes desactivar la sede en la que tienes la sesión abierta."
        )
    antes = instantanea(sede, _CAMPOS_SEDE)
    for campo, nuevo in datos.model_dump(exclude_unset=True).items():
        setattr(sede, campo, nuevo)
    db.flush()
    auditar(
        db, ctx, "editar", "sedes", sede.id, antes=antes, despues=instantanea(sede, _CAMPOS_SEDE)
    )
    return sede
