"""Clientes (#39, RF-40): registro, búsqueda rápida por nombre o teléfono e historial."""

import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.clientes.models import Cliente
from app.modules.clientes.schemas import (
    ClienteCrear,
    ClienteEditar,
    ClienteSalida,
    DomicilioHistorial,
    EncargoHistorial,
    Historial,
    VentaHistorial,
)
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora
from app.shared.paginacion import ParamsPagina, paginar


def normalizar_telefono(telefono: str | None) -> str | None:
    """Deja solo los dígitos y quita el indicativo de Colombia: "+57 300 123 4567" y
    "300-1234567" quedan como "3001234567"."""
    digitos = re.sub(r"\D", "", telefono or "")
    if not digitos:
        return None
    if len(digitos) == 12 and digitos.startswith("57"):
        digitos = digitos[2:]
    if not 7 <= len(digitos) <= 15:
        raise ErrorNegocio(
            "TELEFONO_INVALIDO",
            "El teléfono debe tener entre 7 y 15 números.",
            {"telefono": telefono},
            status=422,
        )
    return digitos


def obtener(db: Session, ctx: Contexto, cliente_id: uuid.UUID) -> Cliente:
    c = db.get(Cliente, cliente_id)
    if c is None or c.sede_id != ctx.sede_id:
        raise NoEncontrado("el cliente", cliente_id)
    return c


def _advertir_repetido(
    db: Session, ctx: Contexto, telefono: str | None, excepto: uuid.UUID | None = None
) -> None:
    """Advertencia, no bloqueo: quien registra decide si es la misma persona."""
    if telefono is None:
        return
    consulta = select(Cliente).where(
        Cliente.sede_id == ctx.sede_id, Cliente.telefono == telefono, Cliente.activo
    )
    if excepto:
        consulta = consulta.where(Cliente.id != excepto)
    otro = db.scalars(consulta.order_by(Cliente.creado_en)).first()
    if otro is not None:
        raise Conflicto(
            "TELEFONO_REPETIDO",
            f"{otro.nombre} ya está registrado con ese teléfono.",
            {"cliente": ClienteSalida.model_validate(otro).model_dump(mode="json")},
        )


def crear(db: Session, ctx: Contexto, datos: ClienteCrear) -> Cliente:
    telefono = normalizar_telefono(datos.telefono)
    if not datos.permitir_telefono_repetido:
        _advertir_repetido(db, ctx, telefono)
    c = Cliente(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        nombre=" ".join(datos.nombre.split()),
        telefono=telefono,
        direccion=(datos.direccion or "").strip() or None,
        notas=(datos.notas or "").strip() or None,
        autoriza_datos=datos.autoriza_datos,
        autorizo_en=ahora() if datos.autoriza_datos else None,
        activo=True,
    )
    db.add(c)
    db.flush()
    auditar(db, ctx, "crear", "clientes", c.id, despues={"nombre": c.nombre})
    return c


def editar(db: Session, ctx: Contexto, cliente_id: uuid.UUID, datos: ClienteEditar) -> Cliente:
    c = obtener(db, ctx, cliente_id)
    cambios = datos.model_dump(exclude_unset=True, exclude={"permitir_telefono_repetido"})
    if "telefono" in cambios:
        cambios["telefono"] = normalizar_telefono(cambios["telefono"])
        if cambios["telefono"] != c.telefono and not datos.permitir_telefono_repetido:
            _advertir_repetido(db, ctx, cambios["telefono"], excepto=c.id)
    if cambios.get("nombre"):
        cambios["nombre"] = " ".join(cambios["nombre"].split())
    for campo in ("direccion", "notas"):
        if campo in cambios:
            cambios[campo] = (cambios[campo] or "").strip() or None
    if cambios.get("autoriza_datos") is not None and cambios["autoriza_datos"] != c.autoriza_datos:
        c.autorizo_en = ahora() if cambios["autoriza_datos"] else None
    for campo, valor in cambios.items():
        if valor is None and campo in ("nombre", "autoriza_datos", "activo"):
            continue
        setattr(c, campo, valor)
    db.flush()
    auditar(db, ctx, "editar", "clientes", c.id, despues={"nombre": c.nombre})
    return c


def listar(
    db: Session, ctx: Contexto, params: ParamsPagina, q: str | None, incluir_inactivos: bool
) -> tuple[list[Cliente], int]:
    consulta = select(Cliente).where(Cliente.sede_id == ctx.sede_id).order_by(Cliente.nombre)
    if not incluir_inactivos:
        consulta = consulta.where(Cliente.activo)
    if q and q.strip():
        texto = q.strip()
        filtros = [Cliente.nombre.ilike(f"%{texto}%")]
        if digitos := re.sub(r"\D", "", texto):
            filtros.append(Cliente.telefono.like(f"%{digitos}%"))
        consulta = consulta.where(or_(*filtros))
    return paginar(db, consulta, params)


def historial(db: Session, ctx: Contexto, cliente_id: uuid.UUID) -> Historial:
    from app.modules.domicilios.models import Domicilio
    from app.modules.encargos.models import Encargo
    from app.modules.ventas.models import Venta

    c = obtener(db, ctx, cliente_id)
    ventas = db.scalars(
        select(Venta).where(Venta.cliente_id == c.id).order_by(Venta.fecha.desc()).limit(100)
    ).all()
    encargos = db.scalars(
        select(Encargo)
        .where(Encargo.cliente_id == c.id)
        .order_by(Encargo.fecha_entrega.desc())
        .limit(100)
    ).all()
    domicilios = db.scalars(
        select(Domicilio)
        .where(Domicilio.cliente_id == c.id)
        .order_by(Domicilio.creado_en.desc())
        .limit(100)
    ).all()
    total = db.scalar(
        select(func.coalesce(func.sum(Venta.total), 0)).where(
            Venta.cliente_id == c.id, Venta.estado == "pagada"
        )
    )
    return Historial(
        cliente=ClienteSalida.model_validate(c),
        ventas=[
            VentaHistorial(
                id=v.id,
                numero=v.numero,
                fecha=v.fecha,
                total=v.total,
                estado=v.estado,
                tipo_servicio=v.tipo_servicio,
            )
            for v in ventas
        ],
        encargos=[
            EncargoHistorial(
                id=e.id,
                numero=e.numero,
                descripcion=e.descripcion,
                fecha_entrega=e.fecha_entrega,
                total=e.total,
                estado=e.estado,
            )
            for e in encargos
        ],
        domicilios=[
            DomicilioHistorial(
                id=d.id, fecha=d.creado_en, direccion=d.direccion, valor=d.valor, estado=d.estado
            )
            for d in domicilios
        ],
        total_comprado=int(total or 0),
    )
