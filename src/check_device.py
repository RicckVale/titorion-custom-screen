"""check_device.py — Verifica se o teclado e a interface da tela estao visiveis.

Somente leitura: enumera os dispositivos HID, nao envia nada ao teclado.
A porta USB muda o caminho; a tela é a usage page 0xFF87 / usage 0x20.

    python src/check_device.py
"""

import hid

from titorion_screen import VID, PID, USAGE_PAGE, USAGE, screen_candidates

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
chosen = screen_candidates()
if not chosen:
    print("Interface da tela: NAO ENCONTRADA")
else:
    best = chosen[0]
    via = "descritor HID" if best["source"] == "descriptor" else "hidapi"
    print(
        f"Interface da tela: OK usage_page=0x{best['usage_page']:04X} "
        f"usage=0x{best['usage']:02X} via {via}"
    )
    if len(chosen) > 1:
        print(f"  {len(chosen)} caminhos (porta USB antiga e nova). A conexão abre o primeiro que responder.")
