# Tela do teclado

Como desenhar uma imagem de 128×128 e fazê-la aparecer no Titorion Saiph sem derrubar a tela no relógio roxo.

O protocolo HID em si está em [`../protocol.md`](../protocol.md). Este guia é o caminho para criar uma tela nova em cima da biblioteca.

## O que é uma tela

Uma tela é uma imagem Pillow de **128×128 pixels, RGB**. O programa escolhe qual desenhar conforme o app em foco e manda para o teclado por `send_image()`.

Não existe um arquivo de layout. Cada tela é uma função que devolve essa imagem.

## Onde o código entra

| Peça | Arquivo | Papel |
|---|---|---|
| Desenho | `src/stats_render.py` | Monta a imagem. Cores, blocos e fontes ficam aqui. |
| Escolha | `src/screen_frame.py` | `build_frame()` decide qual tela usar e devolve `(imagem, texto, modo)`. |
| Envio | `src/titorion_screen.py` | `send_image()` grava no teclado. Não chame o HID de outro lugar. |
| Apps vigiados | `config/screen.json` | Lista de executáveis que trocam a tela (Cursor, Claude). |

`build_frame()` precisa devolver três coisas:

1. A imagem 128×128.
2. Uma frase curta para o log da bandeja.
3. Um `modo` estável, por exemplo `stats` ou `limite:Claude`. Quando o modo muda, a tela nova sai na hora. O mesmo modo espera o intervalo (mínimo 10 s) e não reenvia se os pixels não mudaram.

## Desenhar

Use o papel, a tinta e os blocos que já existem. O cartaz é chapado: borda preta, sombra dura, sem cantos arredondados.

As palavras do cartaz saem de `src/i18n.py`. Português e inglês trocam SEMANA/WEEK, SESSAO/SESSION, CARREGANDO/LOADING e o restante. A chave `language` em `config/screen.json` guarda a escolha (`pt` ou `en`). O botão PT/EN do Screen Studio grava essa chave e o próximo envio sai no idioma novo.

```python
from PIL import Image, ImageDraw

from stats_render import INK, PAPER, _block, _display, _level_color
from titorion_screen import SCREEN_H, SCREEN_W


def render_exemplo(titulo: str, pct: float) -> Image.Image:
    imagem = Image.new("RGB", (SCREEN_W, SCREEN_H), PAPER)
    draw = ImageDraw.Draw(imagem)
    _block(draw, (4, 4, 120, 26), INK, shadow=2)
    draw.text((62, 15), titulo[:10], font=_display(13), fill=(255, 255, 255), anchor="mm")
    _block(draw, (4, 34, 120, 120), _level_color(pct))
    draw.text((62, 78), f"{pct:.0f}%", font=_display(30), fill=INK, anchor="mm")
    return imagem
```

Porcentagem na cor do nível: até 50% verde, até 75% amarelo, daí vermelho. O relógio não é porcentagem e fica amarelo.

Para a tela passar a valer, `build_frame()` devolve essa imagem:

```python
imagem = render_exemplo("EXEMPLO", valor)
return imagem, f"exemplo {valor:.0f}%", "exemplo"
```

O terceiro valor (`"exemplo"`) é o modo. Use um nome diferente para cada situação que deve trocar na hora, como `limite:Cursor` e `limite:Claude`.

## Como a imagem chega no teclado

Cada envio **acrescenta** uma imagem. Não substitui a anterior. A memória é curta: se encher, o teclado continua respondendo e a imagem visível para de mudar.

`send_image()` já faz a troca segura:

1. Sobe a imagem nova enquanto a atual continua na tela.
2. Muda para essa imagem (`0x0D`, picture page).
3. Apaga a anterior (`0x0E`) e pede a picture page de novo.

Duas coisas derrubam a tela no relógio roxo (homepage `0x0B`):

- Apagar a imagem que está sendo mostrada antes de existir outra no lugar.
- Ficar sem nenhuma imagem guardada.

Não chame `delete_picture()` nem `switch_to_home_page()` no meio de uma troca. Não feche o processo no meio de um `send_image()`: o envio cortado trava o controlador até reconectar o teclado.

Comando novo, fora de `0x40` / `0x41` / `0x42` e das páginas já documentadas, só depois de capturar o tráfego do driver oficial.

## App em foco

`src/active_app.py` olha a janela da frente, não uma janela aberta atrás. O nome do executável entra em `config/screen.json`, em `programmingApps`. Aí `build_frame()` pode desenhar uma tela só para aquele app.

O Discord é a exceção da chamada de voz. Com a janela do Discord na frente, o cartaz mostra online, conversa e microfone (`src/discord_status.py`, lista `discordApps`). Se houver uma conversa de voz, esse cartaz passa na frente do relógio e das telas do Cursor e do Claude. Ao sair da conversa, volta quem está na frente.

Números de conta (cota do Cursor, limite do Claude) vêm da sessão local da pessoa. Não grave token, cookie nem porcentagem fixa no código.

## Conferir sem o teclado

Dá para olhar um cartaz que já existe antes de enviar:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'src'); from stats_render import render_loading; render_loading().resize((512, 512), 0).save('preview.png')"
```

No teclado, o Screen Studio sobe pela bandeja (`Screen Studio.bat`). A janela não precisa ficar aberta. Duplo clique na logo abre o preview. **Sair**, no menu do ícone, encerra de verdade.

## Histórico de Modificações Recentes

- 24/10/2026 — Guia de como criar uma tela. O Screen Studio passou a ficar na bandeja, com ícone próprio, e a janela fechada não interrompe o teclado.
- 24/10/2026 — A logo do programa passou a ser o nome TITORION CUSTOM SCREEN em pixel (`src/brand_mark.py`). Na bandeja, o recorte é o monograma TC.
- 24/10/2026 — Idioma pt/en na janela e nos cartazes (`src/i18n.py`, chave `language` em `config/screen.json`).
- 24/10/2026 — Cartaz do Discord (online, conversa, microfone). A chamada de voz tem prioridade sobre o relógio e as outras telas.
