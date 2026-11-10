/** Logo + "ZUQUI'S / REPOSTERÍA", como en la parte superior de la barra lateral. */
export function Marca() {
  return (
    <div className="flex items-center gap-3">
      <img src="/logo.png" alt="" className="size-[66px] shrink-0 rounded-full" />
      <div className="leading-none">
        <p className="font-serif text-[27px] font-semibold tracking-[0.02em] text-cafe">ZUQUI&apos;S</p>
        <p className="mt-2 text-[11px] font-semibold tracking-[0.2em] text-dorado-texto">REPOSTERÍA</p>
      </div>
    </div>
  )
}
