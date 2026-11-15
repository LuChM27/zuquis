import { apiBlob } from './api'

/** Descarga un PDF protegido y lo abre en otra pestaña para imprimirlo o guardarlo. */
export async function abrirPdf(ruta: string): Promise<void> {
  // La pestaña se abre antes de esperar la descarga: si no, el navegador la bloquea.
  const ventana = window.open('', '_blank')
  try {
    const url = URL.createObjectURL(await apiBlob(ruta))
    if (ventana) ventana.location.href = url
    else window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    ventana?.close()
    throw e
  }
}
