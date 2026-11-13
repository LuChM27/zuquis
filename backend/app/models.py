"""Registro de todos los modelos, para Alembic y las pruebas de guardia."""

from app.core.idempotencia_models import Idempotencia
from app.core.modelo import Base
from app.modules.auditoria.models import Auditoria
from app.modules.auth.models import SesionRefresh, Usuario
from app.modules.caja.models import CajaMovimiento, CajaSesion
from app.modules.carta.models import (
    Categoria,
    Modificador,
    PrecioHistorial,
    Producto,
    Receta,
    RecetaItem,
    producto_modificadores,
)
from app.modules.compras.models import Compra, CompraItem, PagoCompra, Proveedor, proveedor_insumos
from app.modules.configuracion.models import Configuracion, MetodoPago, Sede, Unidad
from app.modules.inventario.models import (
    AjusteInventario,
    FaltanteInventario,
    Insumo,
    Lote,
    Merma,
    MovimientoInventario,
    Presentacion,
    VerificacionInventario,
)
from app.modules.produccion.models import Produccion
from app.modules.usuarios.models import Permiso, Rol, UsuarioRol, rol_permisos

__all__ = [
    "AjusteInventario",
    "Auditoria",
    "Base",
    "CajaMovimiento",
    "CajaSesion",
    "Categoria",
    "Compra",
    "CompraItem",
    "Configuracion",
    "FaltanteInventario",
    "Idempotencia",
    "Insumo",
    "Lote",
    "Merma",
    "MetodoPago",
    "Modificador",
    "MovimientoInventario",
    "PagoCompra",
    "Permiso",
    "PrecioHistorial",
    "Presentacion",
    "Produccion",
    "Producto",
    "Proveedor",
    "Receta",
    "RecetaItem",
    "Rol",
    "Sede",
    "SesionRefresh",
    "Unidad",
    "Usuario",
    "UsuarioRol",
    "VerificacionInventario",
    "producto_modificadores",
    "proveedor_insumos",
    "rol_permisos",
]
