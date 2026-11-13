"""Carta (#16) y recetas versionadas con costeo teórico (#20)."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar, instantanea
from app.modules.auth.models import Usuario
from app.modules.carta.models import (
    Categoria,
    Modificador,
    PrecioHistorial,
    Producto,
    Receta,
    RecetaItem,
)
from app.modules.carta.schemas import (
    CategoriaCrear,
    CategoriaEditar,
    CostoItem,
    CostoSalida,
    ModificadorCrear,
    ModificadorEditar,
    ModificadorSalida,
    PrecioHistorialSalida,
    ProductoCrear,
    ProductoEditar,
    ProductoSalida,
    RecetaEntrada,
    RecetaItemSalida,
    RecetaSalida,
)
from app.modules.configuracion import service as configuracion
from app.modules.inventario import motor
from app.modules.inventario.models import Insumo
from app.modules.inventario.service import tiene_movimientos
from app.shared.bd import guardar_unico
from app.shared.dinero import CIEN, ESCALA_PORCENTAJE, costo_linea, dividir_costo, redondear_a_peso
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora

CAMPOS_PRODUCTO = [
    "categoria_id",
    "nombre",
    "tipo",
    "precio",
    "foto_url",
    "disponible",
    "activo",
    "stock_minimo",
    "dias_vida_util",
]


def _de_la_sede(obj, ctx: Contexto, entidad: str, id_: uuid.UUID):
    if obj is None or obj.sede_id != ctx.sede_id:
        raise NoEncontrado(entidad, id_)
    return obj


# --- Categorías -----------------------------------------------------------------------------


def listar_categorias(db: Session, ctx: Contexto, incluir_inactivas: bool) -> list[Categoria]:
    consulta = select(Categoria).where(Categoria.sede_id == ctx.sede_id)
    if not incluir_inactivas:
        consulta = consulta.where(Categoria.activa)
    return list(db.scalars(consulta.order_by(Categoria.orden, Categoria.nombre)))


def crear_categoria(db: Session, ctx: Contexto, datos: CategoriaCrear) -> Categoria:
    c = Categoria(
        sede_id=ctx.sede_id, nombre=datos.nombre.strip(), orden=datos.orden, icono=datos.icono
    )
    db.add(c)
    guardar_unico(db)
    auditar(
        db, ctx, "crear", "categorias", c.id, despues=instantanea(c, ["nombre", "orden", "icono"])
    )
    return c


def editar_categoria(
    db: Session, ctx: Contexto, categoria_id: uuid.UUID, datos: CategoriaEditar
) -> Categoria:
    c = _de_la_sede(db.get(Categoria, categoria_id), ctx, "la categoría", categoria_id)
    campos = ["nombre", "orden", "icono", "activa"]
    antes = instantanea(c, campos)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(c, campo, valor)
    guardar_unico(db)
    auditar(db, ctx, "editar", "categorias", c.id, antes=antes, despues=instantanea(c, campos))
    return c


# --- Modificadores --------------------------------------------------------------------------


def _con_receta(db: Session, columna, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    return set(db.scalars(select(columna).where(columna.in_(ids), Receta.vigente)))


def modificador_salida(db: Session, m: Modificador) -> ModificadorSalida:
    salida = ModificadorSalida.model_validate(m, from_attributes=True)
    salida.tiene_receta = m.id in _con_receta(db, Receta.modificador_id, [m.id])
    return salida


def listar_modificadores(
    db: Session, ctx: Contexto, incluir_inactivos: bool
) -> list[ModificadorSalida]:
    consulta = select(Modificador).where(Modificador.sede_id == ctx.sede_id)
    if not incluir_inactivos:
        consulta = consulta.where(Modificador.activo)
    mods = list(db.scalars(consulta.order_by(Modificador.nombre)))
    con_receta = _con_receta(db, Receta.modificador_id, [m.id for m in mods])
    return [
        ModificadorSalida.model_validate(m, from_attributes=True).model_copy(
            update={"tiene_receta": m.id in con_receta}
        )
        for m in mods
    ]


def crear_modificador(db: Session, ctx: Contexto, datos: ModificadorCrear) -> Modificador:
    m = Modificador(sede_id=ctx.sede_id, nombre=datos.nombre.strip(), precio=datos.precio)
    db.add(m)
    guardar_unico(db)
    auditar(db, ctx, "crear", "modificadores", m.id, despues=instantanea(m, ["nombre", "precio"]))
    return m


def editar_modificador(
    db: Session, ctx: Contexto, modificador_id: uuid.UUID, datos: ModificadorEditar
) -> Modificador:
    m = _de_la_sede(db.get(Modificador, modificador_id), ctx, "la adición", modificador_id)
    campos = ["nombre", "precio", "activo"]
    antes = instantanea(m, campos)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(m, campo, valor)
    guardar_unico(db)
    auditar(db, ctx, "editar", "modificadores", m.id, antes=antes, despues=instantanea(m, campos))
    return m


# --- Productos ------------------------------------------------------------------------------


def obtener_producto(db: Session, ctx: Contexto, producto_id: uuid.UUID) -> Producto:
    return _de_la_sede(db.get(Producto, producto_id), ctx, "el producto", producto_id)


def _salidas_productos(
    db: Session, ctx: Contexto, productos: list[Producto]
) -> list[ProductoSalida]:
    ids = [p.id for p in productos]
    con_receta = _con_receta(db, Receta.producto_id, ids)
    mods_con_receta = _con_receta(
        db, Receta.modificador_id, [m.id for p in productos for m in p.modificadores]
    )
    salidas = []
    for p in productos:
        salida = ProductoSalida.model_validate(p, from_attributes=True)
        salida.tiene_receta = p.id in con_receta
        for m in salida.modificadores:
            m.tiene_receta = m.id in mods_con_receta
        if p.tipo == "lote":
            salida.stock = motor.stock(db, ctx.sede_id, "producto", p.id, incluir_vencidos=False)
        salidas.append(salida)
    return salidas


def producto_salida(db: Session, ctx: Contexto, p: Producto) -> ProductoSalida:
    return _salidas_productos(db, ctx, [p])[0]


def listar_productos(
    db: Session,
    ctx: Contexto,
    categoria_id: uuid.UUID | None,
    incluir_inactivos: bool,
    tipo: str | None,
) -> list[ProductoSalida]:
    consulta = (
        select(Producto)
        .where(Producto.sede_id == ctx.sede_id)
        .options(selectinload(Producto.modificadores))
        .order_by(Producto.nombre)
    )
    if categoria_id:
        consulta = consulta.where(Producto.categoria_id == categoria_id)
    if tipo:
        consulta = consulta.where(Producto.tipo == tipo)
    if not incluir_inactivos:
        # El POS no muestra productos desactivados; los reportes sí los consultan.
        consulta = consulta.where(Producto.activo)
    return _salidas_productos(db, ctx, list(db.scalars(consulta)))


def _modificadores_de(db: Session, ctx: Contexto, ids: list[uuid.UUID]) -> list[Modificador]:
    mods = list(
        db.scalars(
            select(Modificador).where(Modificador.id.in_(ids), Modificador.sede_id == ctx.sede_id)
        )
    )
    if len(mods) != len(set(ids)):
        raise ErrorNegocio("VALIDACION", "Hay adiciones que no existen.", status=422)
    return mods


def _registrar_precio(db: Session, ctx: Contexto, p: Producto, anterior: int | None) -> None:
    db.add(
        PrecioHistorial(
            sede_id=ctx.sede_id,
            producto_id=p.id,
            precio_anterior=anterior,
            precio_nuevo=p.precio,
            usuario_id=ctx.usuario_id,
            fecha=ahora(),
        )
    )


def crear_producto(db: Session, ctx: Contexto, datos: ProductoCrear) -> Producto:
    _de_la_sede(db.get(Categoria, datos.categoria_id), ctx, "la categoría", datos.categoria_id)
    p = Producto(
        sede_id=ctx.sede_id,
        **datos.model_dump(exclude={"modificador_ids", "nombre"}),
        nombre=datos.nombre.strip(),
    )
    p.modificadores = _modificadores_de(db, ctx, datos.modificador_ids)
    db.add(p)
    guardar_unico(db)
    _registrar_precio(db, ctx, p, None)
    auditar(db, ctx, "crear", "productos", p.id, despues=instantanea(p, CAMPOS_PRODUCTO))
    return p


def editar_producto(
    db: Session, ctx: Contexto, producto_id: uuid.UUID, datos: ProductoEditar
) -> Producto:
    p = obtener_producto(db, ctx, producto_id)
    antes = instantanea(p, CAMPOS_PRODUCTO)
    cambios = datos.model_dump(exclude_unset=True)
    if "categoria_id" in cambios:
        _de_la_sede(
            db.get(Categoria, cambios["categoria_id"]), ctx, "la categoría", cambios["categoria_id"]
        )
    if "tipo" in cambios and cambios["tipo"] != p.tipo and tiene_movimientos(db, "producto", p.id):
        raise Conflicto(
            "TIPO_CON_MOVIMIENTOS",
            "Este producto ya tiene stock o ventas registradas: no se puede cambiar su tipo.",
        )
    if "modificador_ids" in cambios:
        p.modificadores = _modificadores_de(db, ctx, cambios.pop("modificador_ids"))
    precio_anterior = p.precio
    for campo, valor in cambios.items():
        setattr(p, campo, valor.strip() if campo == "nombre" else valor)
    guardar_unico(db)
    if p.precio != precio_anterior:
        _registrar_precio(db, ctx, p, precio_anterior)
    auditar(
        db, ctx, "editar", "productos", p.id, antes=antes, despues=instantanea(p, CAMPOS_PRODUCTO)
    )
    return p


def historial_precios(
    db: Session, ctx: Contexto, producto_id: uuid.UUID
) -> list[PrecioHistorialSalida]:
    obtener_producto(db, ctx, producto_id)
    filas = db.execute(
        select(PrecioHistorial, Usuario.nombre)
        .outerjoin(Usuario, Usuario.id == PrecioHistorial.usuario_id)
        .where(PrecioHistorial.producto_id == producto_id)
        .order_by(PrecioHistorial.fecha.desc())
    ).all()
    return [
        PrecioHistorialSalida(
            precio_anterior=h.precio_anterior,
            precio_nuevo=h.precio_nuevo,
            usuario=nombre,
            fecha=h.fecha,
        )
        for h, nombre in filas
    ]


# --- Recetas --------------------------------------------------------------------------------


def _filtro_dueno(producto_id: uuid.UUID | None, modificador_id: uuid.UUID | None):
    return (
        Receta.producto_id == producto_id
        if producto_id
        else Receta.modificador_id == modificador_id
    )


def receta_vigente(
    db: Session, producto_id: uuid.UUID | None = None, modificador_id: uuid.UUID | None = None
) -> Receta | None:
    return db.scalar(
        select(Receta)
        .where(_filtro_dueno(producto_id, modificador_id), Receta.vigente)
        .options(selectinload(Receta.items))
    )


def guardar_receta(
    db: Session,
    ctx: Contexto,
    datos: RecetaEntrada,
    producto_id: uuid.UUID | None = None,
    modificador_id: uuid.UUID | None = None,
) -> Receta:
    """Crea una versión nueva y deja la anterior como histórica: las ventas y producciones ya
    registradas conservan su receta y su costo."""
    insumo_ids = [i.insumo_id for i in datos.items]
    if len(set(insumo_ids)) != len(insumo_ids):
        raise ErrorNegocio("VALIDACION", "Un insumo aparece dos veces en la receta.", status=422)
    insumos = db.scalars(
        select(Insumo).where(Insumo.id.in_(insumo_ids), Insumo.sede_id == ctx.sede_id)
    ).all()
    if len(insumos) != len(insumo_ids):
        raise ErrorNegocio("VALIDACION", "Hay insumos que no existen.", status=422)

    anterior = db.scalar(
        select(Receta)
        .where(_filtro_dueno(producto_id, modificador_id), Receta.vigente)
        .with_for_update()
    )
    ultima_version = db.scalar(
        select(Receta.version)
        .where(_filtro_dueno(producto_id, modificador_id))
        .order_by(Receta.version.desc())
        .limit(1)
    )
    if anterior:
        anterior.vigente = False
        db.flush()
    receta = Receta(
        sede_id=ctx.sede_id,
        producto_id=producto_id,
        modificador_id=modificador_id,
        rendimiento=datos.rendimiento,
        version=(ultima_version or 0) + 1,
        vigente=True,
        items=[
            RecetaItem(sede_id=ctx.sede_id, insumo_id=i.insumo_id, cantidad=i.cantidad, orden=n)
            for n, i in enumerate(datos.items)
        ],
    )
    db.add(receta)
    db.flush()
    auditar(
        db,
        ctx,
        "crear",
        "recetas",
        receta.id,
        antes={"version_anterior": anterior.version} if anterior else None,
        despues={
            "producto_id": str(producto_id) if producto_id else None,
            "modificador_id": str(modificador_id) if modificador_id else None,
            "version": receta.version,
            "rendimiento": str(receta.rendimiento),
            "items": [
                {"insumo_id": str(i.insumo_id), "cantidad": str(i.cantidad)} for i in datos.items
            ],
        },
    )
    return receta


def _insumos(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Insumo]:
    return {i.id: i for i in db.scalars(select(Insumo).where(Insumo.id.in_(ids)))}


def receta_salida(db: Session, receta: Receta) -> RecetaSalida:
    insumos = _insumos(db, [i.insumo_id for i in receta.items])
    return RecetaSalida(
        id=receta.id,
        version=receta.version,
        vigente=receta.vigente,
        rendimiento=receta.rendimiento,
        creado_en=receta.creado_en,
        items=[
            RecetaItemSalida(
                insumo_id=i.insumo_id,
                insumo=insumos[i.insumo_id].nombre,
                unidad=insumos[i.insumo_id].unidad_base,
                cantidad=i.cantidad,
            )
            for i in receta.items
        ],
    )


def versiones(
    db: Session, producto_id: uuid.UUID | None = None, modificador_id: uuid.UUID | None = None
) -> list[RecetaSalida]:
    recetas = db.scalars(
        select(Receta)
        .where(_filtro_dueno(producto_id, modificador_id))
        .options(selectinload(Receta.items))
        .order_by(Receta.version.desc())
    ).all()
    return [receta_salida(db, r) for r in recetas]


def costo_teorico(db: Session, ctx: Contexto, receta: Receta, precio: int) -> CostoSalida:
    """RF-07: cada insumo al último costo de compra; líneas redondeadas a peso y sumadas (§6);
    el costo por unidad divide ese total entre el rendimiento."""
    insumos = _insumos(db, [i.insumo_id for i in receta.items])
    items, completo = [], True
    for item in receta.items:
        insumo = insumos[item.insumo_id]
        costo_u = motor.ultimo_costo(db, ctx.sede_id, "insumo", insumo.id, origen="compra")
        if costo_u is None:
            completo = False
        items.append(
            CostoItem(
                insumo_id=insumo.id,
                insumo=insumo.nombre,
                unidad=insumo.unidad_base,
                cantidad=item.cantidad,
                costo_unitario=costo_u,
                costo=None if costo_u is None else costo_linea(item.cantidad, costo_u),
            )
        )
    costo_receta = sum(i.costo or 0 for i in items)
    costo_unitario = dividir_costo(costo_receta, receta.rendimiento)
    costo_por_unidad = redondear_a_peso(costo_unitario)
    margen = precio - costo_por_unidad
    margen_pct = (
        (Decimal(margen) * CIEN / Decimal(precio)).quantize(ESCALA_PORCENTAJE)
        if precio > 0
        else None
    )
    margen_minimo = configuracion.valor(db, ctx.sede_id, "margen_minimo")
    return CostoSalida(
        margen_minimo=margen_minimo,
        margen_bajo=margen_pct is not None and margen_pct < margen_minimo,
        receta_id=receta.id,
        version=receta.version,
        rendimiento=receta.rendimiento,
        items=items,
        completo=completo,
        costo_receta=costo_receta,
        costo_unitario=costo_unitario,
        costo_por_unidad=costo_por_unidad,
        precio=precio,
        margen=margen,
        margen_porcentaje=margen_pct,
    )
