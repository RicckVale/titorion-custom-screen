# Ideias e roadmap de recursos

Inspiração: um dev fez o visor do teclado mostrar o **limite diário de uso da nuvem** dele.
Como a tela aceita imagem RGB565 arbitrária via HID, **qualquer coisa que vire imagem
pode ir pro teclado** — basta um software gerar a imagem e reenviar periodicamente.

## 1. Mini-monitor dinâmico (prioridade — base: `src/demo_stats.py`)

Software que gera a imagem 128×128 e atualiza a cada N segundos:

- **Sistema**: CPU %, RAM %, temperatura, GPU, rede (psutil / LibreHardwareMonitor)
- **Relógio / data / Pomodoro**
- **Limites e cotas**: uso diário de API/nuvem (OpenAI, Claude, OpenRouter…),
  via consulta à API do provedor e barra de progresso
- **Notificações**: contador de e-mails não lidos, PRs abertos no GitHub, CI status
- **Mídia**: faixa tocando (Spotify API), volume

⚠️ Intervalo de atualização: até confirmarmos se a imagem vai pra flash ou RAM
(ver `protocol.md` §7), usar intervalo ≥ 5–10 s para não desgastar flash.

## 2. Tela contextual por app em foco

Detectar a janela ativa (Windows: `Get-Process` / `pygetwindow` / evento de foco)
e trocar a imagem conforme o app:

- **Cursor aberto** → tela mostra atalhos do Cursor (Ctrl+K, Ctrl+L…)
- **VS Code** → build status / atalhos
- **Jogo** → FPS, ou arte do jogo
- **Reunião (Teams/Meet)** → "EM REUNIÃO" pra quem chegar perto 😄

Arquitetura: um dict `{processo: gerador_de_imagem}` com fallback pra imagem padrão.

## 3. Remapeamento de teclas por app (fase 2 — mais invasivo)

Além da imagem, trocar o que as **teclas fazem** conforme o app:

- O driver tem os comandos `0x17`/`0x18` (get/set keyMessage) e `0x30`/`0x31` (profiles).
- **Antes de implementar**: capturar o tráfego do driver oficial trocando uma tecla
  (Wireshark/USBPcap ou breakpoint no `sendReport` do DevTools) e documentar o formato
  exato — **nunca chutar pacotes de escrita de keymap** (risco de travar o teclado).
- Alternativa não-invasiva: camada de software com AutoHotkey/PowerToys trocando
  atalhos por app, e a tela só mostrando o mapa ativo (recurso 2).

## 4. GIF animado

O driver tem componente de GIF (`$Ut`) com `gifMaxLength` por modelo; o Saiph (2336)
não tem esse campo, então provavelmente: ou não suporta GIF, ou GIF = frames enviados
em sequência com o mesmo protocolo de imagem. Testar com captura de tráfego primeiro.

## 5. Qualidade de vida da ferramenta

- [ ] CLI: `titorion send imagem.png`, `titorion stats`, `titorion watch-app`
- [ ] Bandeja do Windows (ícone com status, troca de "páginas" da tela)
- [ ] Salvar/restaurar a imagem padrão (relógio) ao sair
- [ ] Suporte a texto com fontes melhores (Pillow + TTF)
