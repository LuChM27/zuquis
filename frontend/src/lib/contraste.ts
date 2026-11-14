/** Modo de alto contraste guardado en este equipo (solo es una preferencia de pantalla). */
const CLAVE = 'zuquis.contraste'

export function contrasteAlto(): boolean {
  try {
    return localStorage.getItem(CLAVE) === 'alto'
  } catch {
    return false
  }
}

export function aplicarContraste(alto: boolean): void {
  if (alto) document.documentElement.dataset.contraste = 'alto'
  else delete document.documentElement.dataset.contraste
  try {
    if (alto) localStorage.setItem(CLAVE, 'alto')
    else localStorage.removeItem(CLAVE)
  } catch {
    // Sin almacenamiento (ventana privada): solo dura esta visita.
  }
}
