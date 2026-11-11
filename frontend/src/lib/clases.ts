export const unir = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')
