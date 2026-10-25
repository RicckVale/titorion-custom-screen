# Protocolo HID — Titorion Saiph (tela 128×128)

> Protocolo da tela, anotado em 2026-10-24.
> Os bytes abaixo foram conferidos no aparelho. Não é suposição.

## 1. Identificação do dispositivo

| Campo | Valor |
|---|---|
| Vendor ID (VID) | `0x379A` (14234) |
| Product ID (PID) | `0x0920` (2336) |
| Modelo | Titorion **Saiph** (único da marca com tela) |
| Tela | **128×128 px**, RGB565 |
| String de produto | `"Saiph Keyboard"` (confirmado via hidapi) |

Interfaces HID reais do dispositivo (enumeração via `hid.enumerate(0x379A, 0x0920)`):

| usagePage | usage | Função |
|---|---|---|
| `0x0001` | `0x06` | Teclado (×2, iface 0 e 1) |
| `0x0001` | `0x02` | Mouse |
| `0x0001` | `0x80` | System control |
| `0x000C` | `0x01` | Consumer control |
| **`0xFF87`** | **`0x20`** | **← interface de configuração/tela (a que usamos)** |
| `0xFF88` | `0x21` | vendor-defined (função a investigar) |
| `0xFF00` | `0x01` | vendor-defined (função a investigar) |

O driver fala com a interface **vendor-defined**:

| Campo WebHID | Valor |
|---|---|
| `usagePage` | `65415` (`0xFF87`) — confirmado na enumeração real do dispositivo |
| `usage` | `32` (`0x20`) |
| Report ID de saída | `6` |
| Tamanho do relatório | **63 bytes** de payload (report ID não conta) |

## 2. Formato do pacote (função `Ui` do driver)

```
byte[0]    = comando (0x40 / 0x41 / 0x42 ...)
byte[1]    = parâmetro low   (ex.: offset little-endian, byte baixo)
byte[2]    = parâmetro high
byte[3]    = quantidade de bytes de dados neste pacote
byte[4]    = checksum LOW   (soma simples de TODOS os bytes do relatório, com chk=0 no cálculo)
byte[5]    = checksum HIGH
byte[6]    = 0x00
byte[7..]  = dados (máx 56 bytes por pacote)
(resto preenchido com 0x00 até completar 63 bytes)
```

- **Checksum** (função `v2t`): soma simples (`sum & 0xFFFF`), gravada little-endian em `[4]` e `[5]`.
- **Resposta esperada**: o teclado ecoa um input report onde `resp[0] === cmd` e `resp[1] === paramLo`.
  O driver aceita report IDs `0`, `6` ou `7` na resposta. Timeout default 2000 ms, com retries.
- **Tela ocupada**: se `resp[6] === 0x0F` (`x9t` / `a9t` no driver), o pacote não foi aceito.
  O driver reenvia o mesmo relatório até 20 vezes, com 50 ms entre elas. Seguir em frente
  grava por cima de uma tela que ainda não leu o pacote anterior, e a imagem não troca.

## 3. Tabela de comandos (`Ft.GamingKeyboard2`)

Relevantes para a tela:

| Comando | Nome no driver | Função |
|---|---|---|
| `0x40` | `sendScreenControlInformationPackage` | Abre sessão / pacotes de informação |
| `0x41` | `sendScreenControlDataPacket` | Envia dados (header + pixels) |
| `0x42` | `finishScreenControlDataPacket` | Finaliza e exibe |

Outros úteis para projetos futuros (remapeamento de teclas, luzes, firmware):

| Comando | Nome | Comando | Nome |
|---|---|---|---|
| `0x10`/`0x11` | begin/endConnect | `0x17`/`0x18` | get/set **keyMessage** (remap) |
| `0x12`/`0x13` | get/setDeviceMessage | `0x19`/`0x1A` | get/set **lightMessage** (RGB) |
| `0x14`/`0x15` | getdData/setData | `0x30`/`0x31` | get/set **ProFile** |
| `0x32`–`0x35` | Fn defaults/lock | `0xB0`–`0xB7` | versão, bootloader, upgrade firmware |

⚠️ **Não** enviar comandos fora do fluxo documentado da tela sem antes capturar o tráfego
do fluxo já conferido — um dev bricou um XVX S-K80 (hardware primo) mandando pacotes experimentais.

## 4. Fluxo de upload de imagem estática (branch usado pelo Saiph)

Confirmado no componente `AUt` do driver. Sequência exata:

1. **Handshake** — `sendBuffer(0x40, [A5 5A 10 00 01 C5 B1 01])`
   - `C5 B1` = CRC16-MODBUS de `[10 00 01]`, ordem `[high, low]` (validado ✔)
   - Aguardar **300 ms**
2. **Header** — `sendBuffer(0x41, [A5 5A 0C lenHi lenLo crcHi crcLo])`
   - `len` = total de bytes da imagem = `128 * 128 * 2 = 32768` → `lenHi=0x80, lenLo=0x00`
   - CRC16-MODBUS de `[0x0C, lenHi, lenLo]`, ordem `[high, low]`
3. **Pixels** — `sendBuffer(0x41, pixelBytes)`
   - Chunks de **56 bytes**; parâmetro de cada pacote = **offset** little-endian
4. **Finish** — `0x42`, parâmetros `00 00`, sem dados

`sendBuffer` = divisão em chunks + `buildReport` + espera do echo (ver `src/titorion_screen.py`).

### Troca de página visível (componente `CUt` do driver)

O upload grava a imagem, mas a tela só mostra ela na **picture page**. A homepage é o relógio padrão do firmware. Saiph (2336) não está na lista `ar`, então o payload é `A5 5A <sub> 00 00 CRC_HI CRC_LO` no comando `0x40`, seguido de finish `0x42`. CRC16 de `[sub, 0x00, 0x00]`.

| Subcomando | Página no driver |
|---|---|
| `0x0B` | Homepage (relógio) |
| `0x0D` | Picture (imagem enviada) |
| `0x0E` | Apaga **uma** imagem guardada |
| `0x0F` | GIF |

Cada upload **acrescenta** uma imagem na memória da tela. Não substitui a anterior. Quando o espaço acaba, o HID continua respondendo, mas a imagem visível não muda. `0x0E` apaga uma imagem. Se a apagada é a que está na tela, ou se não sobra nenhuma, o firmware cai na homepage (relógio). A troca segura guarda duas, sobe a terceira, manda `0x0D` para mostrar essa terceira e só então manda `0x0E` na anterior, seguido de outro `0x0D` para a tela não ficar no relógio.

`0x0B` e `0x0D` estavam invertidos na biblioteca: chamar “página de imagem” mandava a homepage e a tela voltava para o relógio.

### CRC16-MODBUS (função `Lr` do driver)

```
crc = 0xFFFF
para cada byte: crc ^= byte; 8× { se bit0: crc >>= 1, crc ^= 0xA001; senão crc >>= 1 }
retorna [crc >> 8 & 0xFF, crc & 0xFF]   # ordem [high, low]
```

Teste de sanidade: `CRC16([0x10, 0x00, 0x01]) == [197, 177]` (validado contra o driver ✔)

## 5. Formato de pixel — RGB565 big-endian (função `ut` do driver)

```python
r5 = r >> 3;  g6 = g >> 2;  b5 = b >> 3
pixel = (r5 << 11) | (g6 << 5) | b5     # 16 bits
bytes   = [pixel >> 8, pixel & 0xFF]    # byte ALTO primeiro
```

Total por imagem: `128 × 128 × 2 = 32768 bytes` → `586` pacotes HID (56 bytes cada).

## 6. Mapa de resoluções (`T8` no driver) — outros modelos

`2336: {128×128}` (Saiph). Outros para referência: `12463: 96×160`, `12545/12714/12744/12684: 160×96`,
`12690/12732/12918/12821/12810/12813/12749: 128×128`, `12724/12751/12911/12957/12961/12962/12970: 240×135`,
`12689/12920/12938/12949/12987/12682/12728: 160×80`, `12941: 50×160`.

Modelos na lista `ar = [12920, 12821, 12938, 12682, 12941, 12949, 12911, 12957, 12961, 12962, 12627, 12964, 12970, 12987]`
usam um fluxo **diferente** (comandos `0x10/0x41/0x43...` com outro handshake). **O Saiph (2336) NÃO está nessa lista** — usar o fluxo da seção 4.

## 7. Questões em aberto

- [ ] A imagem persiste após desligar/desconectar? (flash ou RAM?) — define intervalo seguro de auto-update

### ⚠️ ACHADO (2026-10-24) — a tela guarda várias imagens e o espaço acaba

Cada upload é uma imagem **nova** na memória. Depois de várias, o espaço enche: o HID
continua ecoando os pacotes, mas a tela fica na última imagem que coube. Não é chave de
liga/desliga. O Saiph só tem os 3 botões de modo (dongle, USB, Bluetooth).

O driver apaga uma imagem com o subcomando `0x0E`. Apagar a que está na tela,
ou esvaziar a memória, faz o firmware mostrar o relógio. `send_image(replace=True)`
sobe a imagem nova, troca para ela e só então apaga a anterior.

**Mitigação**:
- Duas imagens na memória. A nova entra como terceira, a tela troca para ela, e o `0x0E` tira a que ficou para trás.
- Nunca intercalar uploads (trava por software já implementada na biblioteca).
- Nunca fechar o processo no meio de um upload (app já espera o frame terminar).
- [ ] GIF animado: componente `$Ut` do driver (tem `gifMaxLength` por modelo; Saiph não tem → provável que GIF seja por frames enviados em sequência ou não suportado)
- [x] Voltar a tela ao relógio sem reboot: homepage `0x0B` (driver, componente `CUt`)
- [ ] Remapeamento de teclas por software (`0x18` setkeyMessage) para o recurso "tecla muda conforme o app aberto"
- [ ] Ler estado da tela/teclado (ex.: `0x1F` getPoorNum, `0x55` getDongleAndKeyboardStatus)
