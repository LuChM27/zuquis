from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import permisos
from app.core.config import obtener_config
from app.core.db import SesionLocal, obtener_db
from app.modules.archivos.router import router as archivos_router
from app.modules.auditoria.router import router as auditoria_router
from app.modules.auth.router import router as auth_router
from app.modules.caja.router import router as caja_router
from app.modules.carta.router import router as carta_router
from app.modules.compras.router import router as compras_router
from app.modules.configuracion.router import router as configuracion_router
from app.modules.gastos.router import router as gastos_router
from app.modules.inventario.router import router as inventario_router
from app.modules.produccion.router import router as produccion_router
from app.modules.usuarios.router import router as usuarios_router
from app.modules.ventas.router import router as ventas_router
from app.shared.errores import registrar_manejadores

PREFIJO_API = "/api/v1"


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    with SesionLocal() as db:
        permisos.sincronizar(db)
        db.commit()
    yield


def crear_app(sincronizar_al_iniciar: bool = True) -> FastAPI:
    app = FastAPI(
        title="Zuqui's API",
        version="0.1.0",
        description="Sistema contable, punto de venta e inventario de Zuqui's Repostería.",
        lifespan=ciclo_de_vida if sincronizar_al_iniciar else None,
        docs_url="/docs",
        openapi_url=f"{PREFIJO_API}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=obtener_config().cors_lista,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    registrar_manejadores(app)

    api = APIRouter(prefix=PREFIJO_API)

    @api.get("/salud", tags=["Sistema"])
    def salud(db: Session = Depends(obtener_db)) -> dict[str, str]:
        db.execute(text("SELECT 1"))
        return {"api": "ok", "db": "ok"}

    for router in (
        auth_router,
        usuarios_router,
        configuracion_router,
        auditoria_router,
        archivos_router,
        inventario_router,
        carta_router,
        compras_router,
        produccion_router,
        caja_router,
        ventas_router,
        gastos_router,
    ):
        api.include_router(router)
    app.include_router(api)
    return app


app = crear_app()
