"""Registro de todos los modelos, para Alembic y las pruebas de guardia."""

from app.core.idempotencia_models import Idempotencia
from app.core.modelo import Base
from app.modules.auditoria.models import Auditoria
from app.modules.auth.models import SesionRefresh, Usuario
from app.modules.caja.models import CajaArqueo, CajaMovimiento, CajaSesion
from app.modules.carta.models import (
    Categoria,
    Modificador,
    PrecioHistorial,
    Producto,
    Receta,
    RecetaItem,
    producto_modificadores,
)
from app.modules.clientes.models import Cliente
from app.modules.compras.models import Compra, CompraItem, PagoCompra, Proveedor, proveedor_insumos
from app.modules.configuracion.models import Configuracion, MetodoPago, Sede, Unidad
from app.modules.domicilios.models import Domiciliario, Domicilio
from app.modules.encargos.models import Encargo, EncargoAbono, EncargoItem
from app.modules.gastos.models import CategoriaGasto, Gasto
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
from app.modules.ventas.models import (
    Consecutivo,
    Venta,
    VentaItem,
    VentaItemModificador,
    VentaPago,
)

__all__ = [
    "AjusteInventario",
    "Auditoria",
    "Base",
    "CajaArqueo",
    "CajaMovimiento",
    "CajaSesion",
    "Categoria",
    "CategoriaGasto",
    "Cliente",
    "Compra",
    "CompraItem",
    "Configuracion",
    "Consecutivo",
    "Domiciliario",
    "Domicilio",
    "Encargo",
    "EncargoAbono",
    "EncargoItem",
    "FaltanteInventario",
    "Gasto",
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
    "Venta",
    "VentaItem",
    "VentaItemModificador",
    "VentaPago",
    "VerificacionInventario",
    "producto_modificadores",
    "proveedor_insumos",
    "rol_permisos",
]
