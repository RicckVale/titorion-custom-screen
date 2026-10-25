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

Se o teclado foi reiniciado e a imagem visível parou de mudar, a memória ficou com cartaz velho e o arquivo `config/screen_state.json` não sabe disso. **Esvaziar tela**, na janela ou na bandeja, pede a picture page (`0x0D`), apaga uma imagem por vez (`0x0E`, no máximo seis, e para no primeiro timeout) e grava de novo o cartaz de carregamento e o cartaz atual. O relógio roxo pode aparecer nesse intervalo. Não é comando novo.

Comando novo, fora de `0x40` / `0x41` / `0x42` e das páginas já documentadas, só depois de capturar o tráfego real.

## App em foco

`src/active_app.py` olha a janela da frente, não uma janela aberta atrás. O nome do executável entra em `config/screen.json`, em `programmingApps`. Aí `build_frame()` pode desenhar uma tela só para aquele app.

O Discord (`src/discord_status.py`, lista `discordApps`) mostra online, conversa e microfone quando a janela dele está na frente. Numa chamada de voz, esse cartaz reveza com o que as outras regras escolheriam (Claude, Cursor, Spotify ou o relógio), cerca de 10 segundos cada. O campeão não entra nessa troca: com o jogo na frente, a tela fica nele. Ao sair da conversa, fica quem está na frente.

O Spotify (`src/spotify_now.py`, lista `spotifyApps`) mostra a faixa da sessão de mídia do Windows, com a capa quando ela vem junto. Tocando, ele troca o relógio. Com a janela do Spotify na frente, mostra também pausa ou a ausência de faixa. Se essa leitura não responder, a tela segue para o relógio em vez de ficar no cartaz anterior. Cursor, Claude e a partida do League na frente continuam na frente. Na chamada do Discord, o Spotify entra na vez dele quando teria trocado o relógio.

Fora desses cartazes, o relógio reveza com o tempo. O intervalo está em `weatherTurnSeconds`.

O League (`src/lol_match.py`, lista `leagueApps`) mostra o campeão enquanto o executável da partida está aberto e a partida responde em `leagueLiveUrl`. Não precisa ser a janela da frente. Cursor ou Claude na frente continuam na frente. O nome e o nível vêm da partida. Uma partida nova é outro processo: o campeão anterior sai na hora. Se a leitura piscar no meio do jogo, o último campeão continua na tela. Quando o nome muda, e de novo quando a partida fecha, o Screen Studio esvazia as imagens guardadas e grava o cartaz seguinte. Sem isso a foto do campeão continua na tela. O relógio roxo pode aparecer nesse intervalo. Uma chamada do Discord não cobre esse cartaz. A resposta não diz se uma skill está pronta, e o comando de luz do teclado ainda não foi capturado, então as teclas não mudam de cor. Um erro de envio não desliga o monitor: ele tenta de novo.

Números de conta (cota do Cursor, limite do Claude) vêm da sessão local da pessoa. Não grave token, cookie nem porcentagem fixa no código. Uma leitura fica em cache por 60 segundos. Se a sessão não puder ser lida, o cartaz ainda sai e o log da bandeja diz que a cota não foi lida.

### Cursor

O editor guarda o login em `%APPDATA%\Cursor\User\globalStorage\state.vscdb`, na chave `cursorAuth/accessToken`. O Screen Studio abre esse banco só para leitura e envia o token como cabeçalho Bearer. Ele não copia o token para este projeto.

O pedido é um POST para a URL em `config/screen.json` (`usageUrl`), corpo `{}`, com `Content-Type: application/json` e `Connect-Protocol-Version: 1`.

| Na tela | Campo |
|---|---|
| Incluído, no canto | `planUsage.includedSpend` dividido por `planUsage.limit` |
| API | `planUsage.apiPercentUsed` |
| Auto, na frente | `planUsage.autoPercentUsed` |
| Dias restantes | `billingCycleEnd`, convertido em dias inteiros |

Esse endpoint devolve porcentagens do período de cobrança. Ele não devolve um contador bruto de tokens.

### Claude

O aplicativo de desktop guarda a sessão do claude.ai em `%LOCALAPPDATA%\Claude-Data\<profile>\`. O Screen Studio escolhe o perfil que tem `Network\Cookies` e `Local State`, usando o arquivo de cookies gravado por último. O id da organização é o cookie `lastActiveOrg`. O cookie de sessão precisa estar presente. Nenhum desses valores é gravado neste repositório.

Com o Claude aberto, ele trava o banco de cookies. O programa então lê o arquivo pelo handle que o aplicativo já tem. A chave em `Local State` é aberta com o DPAPI do Windows, e cada valor de cookie é decifrado com essa chave. Cookies de outros sites são ignorados.

O pedido é um GET para a URL em `config/screen.json` (`claudeUsageUrl`), com `{org}` trocado por essa organização. A chamada é feita com um cliente parecido com o navegador. Uma biblioteca HTTP comum é barrada pela Cloudflare antes do JSON de uso voltar.

| Na tela | Campo |
|---|---|
| Semana, todos os modelos, na frente | `limits[]` em que `kind` é `weekly_all`, campo `percent`. Se essa lista faltar, `seven_day.utilization` |
| Sessão, embaixo | `limits[]` em que `kind` é `session`, campo `percent`. Se essa lista faltar, `five_hour.utilization` |
| Tempo até reiniciar, no adesivo | `resets_at` do limite semanal, mostrado em minutos, horas ou dias |

Uma organização que só tem acesso de API, e não a sessão do chat, não devolve esse uso. A janela do Claude precisa ser a da frente.

### Discord, Spotify e League

Online no Discord significa uma conexão TCP ativa. Em chamada significa que o log de voz do próprio aplicativo terminou em conectado. O microfone é a sessão de captura do Windows desse processo, e só aparece durante a chamada.

O Spotify lê a sessão de mídia do Windows. Sem conta e sem token. A capa vem dessa mesma sessão, quando o player manda. O nome da faixa cresce quando é curto e encolhe quando é longo, até caber inteiro no bloco.

O tempo (`src/weather.py`) reveza com o relógio. O intervalo é `weatherTurnSeconds` em `config/screen.json`, no mínimo 10 segundos. A cidade é `weatherCity`. Vazia, o lugar sai da rede, uma vez, e a previsão sai do Open-Meteo, sem token. A leitura fica em cache por 10 minutos.

No League, o nome da foto de exemplo não é fixo. No teclado, é o campeão que a partida aberta devolve.

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
- 24/10/2026 — Cartaz do Spotify com a faixa atual. Tocando, substitui o relógio.
- 24/10/2026 — A conversa do Discord passa a ser lida do último estado de voz do log do app. O UDP sem endereço remoto não marcava a chamada.
- 24/10/2026 — A chamada do Discord deixa de travar a tela. O cartaz reveza com a outra prioridade, cerca de 10 segundos cada.
- 24/10/2026 — Cartaz das duas magias de invocador com a janela do League na frente. O nome sai da partida local. Sem recarga e sem comando de LED.
- 24/10/2026 — O cartaz do League passou a mostrar o campeão da partida, com o nível no adesivo. As magias saíram da tela.
- 24/10/2026 — Os campos de cota do Cursor e do Claude, e a leitura do Discord, saíram do README e ficaram neste guia.
- 24/10/2026 — Saíram o monitor antigo do terminal, o teste que enchia a galeria, a logo solta e os previews que o README não usa mais.
- 24/10/2026 — Com o jogo na frente, o cartaz do campeão deixa de revezar com a chamada do Discord.
- 24/10/2026 — O cartaz do campeão ganhou a marca do League no cabeçalho, no mesmo lugar da marca do Cursor e da do Claude.
- 24/10/2026 — O cartaz do campeão entra com a partida aberta, mesmo sem a janela do jogo na frente. Um erro de envio não para o monitor.
- 24/10/2026 — Esvaziar tela apaga as imagens guardadas com `0x0E` e grava o cartaz atual de novo, para quando um reinício deixa a imagem velha presa.
- 24/10/2026 — Os cartazes do Discord e do Spotify ganharam a marca no cabeçalho, no mesmo lugar da marca do League.
- 24/10/2026 — Troca de campeão esvazia a galeria antes de gravar. Uma leitura que pisca no meio da mesma partida não tira o cartaz.
- 25/10/2026 — Ao fechar a partida, a imagem do campeão sai da tela. A galeria é esvaziada e o cartaz seguinte entra.
- 25/10/2026 — Uma leitura do Spotify que não responde não segura a troca de cartaz.
- 25/10/2026 — O tempo reveza com o relógio. A capa da faixa entra no cartaz do Spotify quando a sessão de mídia manda a imagem.
- 25/10/2026 — O nome da faixa no Spotify encolhe para caber inteiro e cresce quando o título é curto.
- 25/10/2026 — O cartaz do tempo ganhou ícone em pixel da condição: sol, nuvem, chuva, neve e tempestade.
