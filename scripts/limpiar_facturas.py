"""
Limpieza: borra de uploads/facturas/ cualquier archivo que no sea
<folio>.xml o <folio>.pdf. Los mueve a uploads/duplicados/ para no perderlos.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import re
import shutil
from shared import uploads_manager as um

PATRON = re.compile(r'^\d+\.(xml|pdf|XML|PDF)$', re.IGNORECASE)

def main():
    print("=" * 60)
    print("LIMPIEZA DE uploads/facturas/")
    print("=" * 60)

    movidos = 0
    revisados = 0

    for base in (um.FACTURAS, um.SIN_PDF, um.RECHAZADOS):
        if not base.exists():
            continue
        for f in list(base.rglob("*")):
            if not f.is_file():
                continue
            revisados += 1
            if PATRON.match(f.name):
                continue  # nombre válido
            # Mover a duplicados manteniendo estructura año/mes
            try:
                rel = f.relative_to(base)
                destino = um.DUPLICADOS / rel
                destino.parent.mkdir(parents=True, exist_ok=True)
                target = destino
                contador = 1
                while target.exists():
                    target = destino.parent / f"{destino.stem}_{contador}{destino.suffix}"
                    contador += 1
                shutil.move(str(f), str(target))
                movidos += 1
            except Exception as e:
                print(f"  Error con {f}: {e}")

    print(f"  Revisados: {revisados}")
    print(f"  Movidos a duplicados: {movidos}")
    print()

    # Ahora contar lo que queda
    total = sum(1 for _ in um.FACTURAS.rglob("*") if _.is_file())
    print(f"  Archivos restantes en uploads/facturas/: {total}")
    print()
    print("Carpetas con archivos:")
    for d in sorted(set(f.parent for f in um.FACTURAS.rglob("*") if f.is_file())):
        n = sum(1 for _ in d.iterdir() if _.is_file())
        print(f"  {d.relative_to(um.FACTURAS.parent)}: {n} archivos")


if __name__ == "__main__":
    main()