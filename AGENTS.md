# AGENTS.md — titorion-custom

## O que é este projeto

Ferramentas customizadas para o teclado **Titorion Saiph** (USB VID `0x379A`, PID `0x0920`,
string de produto `"Saiph Keyboard"`, tela **128×128 px RGB565**), nascidas de engenharia
reversa do driver web oficial (`https://titorion.i-game.tech/`).

## Fonte da verdade

- **Protocolo HID da tela**: [`docs/protocol.md`](docs/protocol.md) — leia antes de mexer
  em qualquer código que fale com o teclado.
- **Como o protocolo foi descoberto**: [`docs/reverse-engineering.md`](docs/reverse-engineering.md).
- **Roadmap/ideias**: [`docs/ideas.md`](docs/ideas.md).
- **Bundle original do driver oficial** fica só no site (`https://titorion.i-game.tech/`).
 Não copie o `.js` para este repositório. Os nomes minificados mudam a cada build; busque pelas strings
 (`sendScreenControlDataPacket`, `setkeyMessage`, `usagePage:65415`).

## Regras de segurança (importante)

- **Nunca inventar pacotes de escrita** para comandos fora do fluxo documentado da tela
  (`0x40`/`0x41`/`0x42`) sem antes capturar o tráfego do driver oficial — hardware dessa
  família já foi brickado por pacotes experimentais (caso XVX S-K80).
- Checksums: soma simples no cabeçalho HID; CRC16/MODBUS dentro dos payloads `A5 5A`.
  Sanity check do CRC: `crc16_modbus([0x10,0x00,0x01]) == (197,177)`.
- Intervalo de auto-update da tela ≥ 5–10 s até confirmarmos se a imagem vai para
  flash ou RAM (questão aberta em `docs/protocol.md` §7).
- Pedir confirmação do usuário antes de enviar qualquer comando novo ao dispositivo.

## Estrutura e convenções

- `tools/web/index.html` — ferramenta WebHID autocontida (abrir em Chrome/Edge, sem build).
- `src/titorion_screen.py` — biblioteca do protocolo; tudo que fala com o teclado passa por ela.
- `src/demo_*.py` — demos/CLIs finos sobre a biblioteca.
- Dependências Python em `.venv` local: `pip install -r requirements.txt`.
- Código em português (usuário brasileiro); comentários de protocolo citam a função
  equivalente do driver oficial (ex.: `# função Ui() do driver`) para rastreabilidade.

## Testes

- `python src/check_device.py` — enumeração (read-only, seguro, não envia nada).
- `python src/demo_static.py --red` — teste de envio real (tela vermelha).
