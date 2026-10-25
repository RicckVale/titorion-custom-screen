# Diário da engenharia reversa — como chegamos ao protocolo

Registro da investigação (2026-10-24) para referência futura.

## Passo a passo

1. **Identificação do hardware no Windows**
   - `Get-PnpDevice` listou o teclado como `USB Composite Device` **VID_379A / PID_0920**,
     com 2 interfaces de teclado, mouse, consumer control e 3 interfaces "vendor-defined".
   - 3 interfaces vendor = canal de configuração (tela, RGB, remap) separado do teclado HID normal.

2. **Descoberta do driver oficial**
   - Site da Titorion (`titorion.com.br/drivers`) aponta para o **driver web**: `https://titorion.i-game.tech/`
   - É um app React que fala com o teclado via **WebHID** (por isso exige Chrome/Edge/Opera).

3. **Análise do bundle JS**
   - Lido em `https://titorion.i-game.tech/assets/index-CUuVw08z.js` (~4,5 MB minificado).
   - O bundle não fica neste repositório: é o programa oficial, e republicá-lo aqui seria cópia sem licença.
   - Achados principais:
     - `Ud` — registro de ~200 dispositivos suportados (vendorId/productId/reqLen/layout).
       O PID **2336** (nosso `0x0920`) está lá → confirmação de que é o Saiph.
     - `Ft.GamingKeyboard2` — tabela completa de opcodes (0x40/0x41/0x42 = tela).
     - `Ui` — montador de pacotes (cmd, parâmetro, len, checksum, dados).
     - `v2t` — checksum por soma simples; `Lr` — CRC16/MODBUS; `Wi` — u16 little-endian.
     - `h9t`/`g9t`/`w9t` — funções de envio da tela (info / dados / finish).
     - `AUt` — componente de upload de imagem: canvas → `getImageData` → **RGB565 big-endian** (`ut`).
     - `T8` — mapa de resolução por PID: **2336 → 128×128**.
     - `sendData` — camada WebHID: reportId 6, resposta validada por echo dos 2 primeiros bytes,
       timeout 2000 ms, retries (`Tb`).

4. **Validação**
   - CRC16 de `[0x10, 0x00, 0x01]` calculado = `[197, 177]` = `C5 B1` — exatamente os bytes
     fixos do handshake no driver. Implementação confirmada bit a bit.

## Ferramentas que valem para investigações futuras

- **Chrome DevTools** no `titorion.i-game.tech`: breakpoint em `navigator.hid` / `sendReport`
  mostra os bytes exatos de qualquer ação (remap de tecla, RGB, firmware...).
- **Wireshark + USBPcap** no Windows: captura o tráfego USB enquanto o driver opera.
- Busca no bundle: os nomes minificados mudam a cada build, mas as strings
  (`sendScreenControlDataPacket`, `setkeyMessage`, `usagePage:65415`) permanecem —
  são as melhores âncoras de busca.

## Referências externas úteis

- Protocolo primo documentado: "Reverse engineering the ROYUAN keyboard HID protocol" (dnim.dev)
  — família Attack Shark/Epomaker/Akko com abordagem parecida (WebHID + Electron).
- Alerta de risco: Hackaday 2024-09 — dev bricou um XVX S-K80 enviando pacotes experimentais;
  por isso aqui só replicamos fielmente a sequência oficial.
