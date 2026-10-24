"""check_device.py — Verifica se o teclado e a interface da tela estao visiveis.

Somente leitura: enumera os dispositivos HID, nao envia nada ao teclado.

    python src/check_device.py
"""

import hid

from titorion_screen import TitorionScreen, VID, PID, USAGE_PAGE, USAGE

print(f"Interfaces HID com VID=0x{VID:04X} PID=0x{PID:04X}:\n")
found = False
for info in hid.enumerate(VID, PID):
    up = info.get("usage_page") or 0
    u = info.get("usage") or 0
    mark = "  <== INTERFACE DA TELA" if (up == USAGE_PAGE and u == USAGE) else ""
    print(
        f"  usage_page=0x{up:04X} usage=0x{u:02X} "
        f"iface={info.get('interface_number')} "
        f"product={info.get('product_string')!r}{mark}"
    )
    found = True

if not found:
    print("  (nenhuma — teclado esta conectado por cabo?)")

print()
path = TitorionScreen.find_interface()
print("find_interface():", "OK - interface da tela encontrada" if path else "NAO ENCONTRADA")
