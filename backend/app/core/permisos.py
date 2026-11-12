"""Catálogo de permisos (clave modulo.accion) y roles base (sección 2 de la especificación).

El catálogo vive en código y se sincroniza con la tabla ``permisos`` al iniciar la API. Los
cuatro roles base se crean una sola vez con sus permisos por defecto; después el
administrador puede editarlos libremente.
"""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DefPermiso:
    clave: str
    descripcion: str

    @property
    def modulo(self) -> str:
        return self.clave.split(".", 1)[0]


CATALOGO: tuple[DefPermiso, ...] = (
    # Ventas y caja
    DefPermiso("ventas.crear", "Vender, cobrar y registrar propinas"),
    DefPermiso("ventas.anular", "Anular ventas"),
    DefPermiso("descuentos.aplicar", "Aplicar descuentos y cortesías hasta el tope del rol"),
    DefPermiso("descuentos.autorizar", "Autorizar descuentos por encima del tope de otro rol"),
    DefPermiso("caja.abrir", "Abrir caja"),
    DefPermiso("caja.cerrar", "Cerrar caja con arqueo"),
    DefPermiso("caja.movimientos", "Registrar entradas y salidas manuales de caja"),
    # Encargos y clientes
    DefPermiso("encargos.crear", "Crear encargos y recibir abonos"),
    DefPermiso("encargos.anular_abono", "Anular abonos"),
    DefPermiso("encargos.devolver_abono", "Cancelar encargos y decidir la devolución del abono"),
    DefPermiso("clientes.gestionar", "Crear y editar clientes"),
    # Gastos y compras
    DefPermiso("gastos.crear", "Registrar gastos de cualquier fuente"),
    DefPermiso("gastos.crear_caja", "Registrar gastos pagados de la caja"),
    DefPermiso("gastos.anular", "Anular gastos"),
    DefPermiso("compras.crear", "Registrar compras e ingreso de insumos"),
    DefPermiso("compras.anular", "Anular compras"),
    DefPermiso("proveedores.gestionar", "Crear y editar proveedores"),
    # Inventario y producción
    DefPermiso("produccion.crear", "Registrar producción"),
    DefPermiso("produccion.anular", "Anular producciones"),
    DefPermiso("inventario.ver", "Consultar stock, lotes y kardex"),
    DefPermiso("inventario.merma", "Registrar mermas"),
    DefPermiso("inventario.ajustar", "Hacer ajustes por conteo físico"),
    DefPermiso("insumos.gestionar", "Crear y editar insumos y presentaciones"),
    # Carta
    DefPermiso("carta.editar", "Editar carta, productos y precios"),
    DefPermiso("recetas.editar", "Editar recetas"),
    # Reportes
    DefPermiso("reportes.ver", "Ver todos los reportes y el dashboard"),
    DefPermiso("reportes.ver_caja_propia", "Ver el reporte de su caja del día"),
    DefPermiso("reportes.ver_inventario", "Ver reportes de inventario"),
    DefPermiso("reportes.exportar", "Exportar reportes a Excel y PDF"),
    # Administración
    DefPermiso("config.editar", "Editar configuración del negocio, sedes y métodos de pago"),
    DefPermiso("usuarios.gestionar", "Administrar usuarios y roles"),
    DefPermiso("auditoria.ver", "Consultar la auditoría"),
)

CLAVES = frozenset(p.clave for p in CATALOGO)


@dataclass(frozen=True)
class DefRolBase:
    clave_base: str
    nombre: str
    descripcion: str
    permisos: frozenset[str]


ROLES_BASE: tuple[DefRolBase, ...] = (
    DefRolBase("admin", "Dueño / Admin", "Acceso total", CLAVES),
    DefRolBase(
        "cajero",
        "Cajero / Vendedor",
        "Vende, maneja la caja, encargos y gastos de caja",
        frozenset(
            {
                "ventas.crear",
                "descuentos.aplicar",
                "caja.abrir",
                "caja.cerrar",
                "caja.movimientos",
                "encargos.crear",
                "clientes.gestionar",
                "gastos.crear_caja",
                "reportes.ver_caja_propia",
            }
        ),
    ),
    DefRolBase(
        "produccion",
        "Producción / Cocina",
        "Compras, producción, mermas y recetas",
        frozenset(
            {
                "compras.crear",
                "proveedores.gestionar",
                "produccion.crear",
                "inventario.ver",
                "inventario.merma",
                "insumos.gestionar",
                "recetas.editar",
                "reportes.ver_inventario",
            }
        ),
    ),
    DefRolBase(
        "contador",
        "Contador",
        "Consulta y exporta reportes",
        frozenset(
            {"reportes.ver", "reportes.ver_inventario", "reportes.exportar", "inventario.ver"}
        ),
    ),
)

assert all(r.permisos <= CLAVES for r in ROLES_BASE), "Rol base con permiso fuera del catálogo"


def sincronizar(db: Session) -> None:
    """Crea los permisos nuevos del catálogo y los roles base que falten. Idempotente.

    Usa un bloqueo de PostgreSQL para que dos procesos que arrancan a la vez no choquen.
    """
    from app.modules.usuarios.models import Permiso, Rol

    db.execute(text("SELECT pg_advisory_xact_lock(727001)"))
    existentes = {p.clave: p for p in db.scalars(select(Permiso))}
    nuevos: set[str] = set()
    for definicion in CATALOGO:
        permiso = existentes.get(definicion.clave)
        if permiso is None:
            permiso = Permiso(
                clave=definicion.clave, descripcion=definicion.descripcion, modulo=definicion.modulo
            )
            db.add(permiso)
            existentes[definicion.clave] = permiso
            nuevos.add(definicion.clave)
        else:
            permiso.descripcion = definicion.descripcion
            permiso.modulo = definicion.modulo
    db.flush()

    roles = {r.clave_base: r for r in db.scalars(select(Rol).where(Rol.clave_base.is_not(None)))}
    for definicion in ROLES_BASE:
        rol = roles.get(definicion.clave_base)
        if rol is not None:
            # Un permiso que aparece en una versión nueva se agrega a los roles base que lo
            # traen por defecto. Lo que el admin ya cambió no se toca.
            for clave in sorted(nuevos & definicion.permisos):
                rol.permisos.append(existentes[clave])
            continue
        db.add(
            Rol(
                nombre=definicion.nombre,
                descripcion=definicion.descripcion,
                es_base=True,
                clave_base=definicion.clave_base,
                permisos=[existentes[c] for c in sorted(definicion.permisos)],
            )
        )
    db.flush()
