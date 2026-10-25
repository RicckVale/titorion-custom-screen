# titorion-custom-screen

![logo titorion-custom](assets/titorion-custom-screen.png)

Fonte: https://github.com/RicckVale/titorion-custom-screen

## O que é

Ferramentas caseiras para a telinha do teclado **Titorion Saiph** (USB VID `0x379A`, PID `0x0920`, produto `"Saiph Keyboard"`). A tela tem **128×128 pixels**, RGB565.

O que este programa envia ao teclado está em [`docs/protocol.md`](docs/protocol.md). Um pacote novo, fora desse fluxo, não entra sem uma captura já conferida.

A tela de fábrica, e a mesma foto com o cartaz do Claude nesse lugar:

| Antes | Depois |
|---|---|
| ![Tela de fábrica](assets/preview-keyboard-before.png) | ![Cartaz do Claude na tela](assets/preview-keyboard-after.png) |

## O que faz

O Screen Studio fica na bandeja do Windows, com a logo do projeto, e segue a janela da frente. A janela do programa não precisa ficar aberta.


| Janela da frente | O que aparece na tela                                                                                                                         |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Cursor           | Cota da conta: Auto na frente, API em seguida, incluído no canto. Verde até 50%, amarelo até 75%, vermelho acima disso.                        |
| Claude           | Limite do Claude: a semana (todos os modelos) na frente, a sessão embaixo, o tempo até reiniciar no adesivo. Cabeçalho laranja, com a estrela. |
| Discord          | Online, em conversa de voz ou não, e o microfone (aberto, mudo, ou fora de chamada). Cabeçalho blurple.                                       |
| Spotify          | A faixa que está tocando: título, artista, e se está tocando ou em pausa. Cabeçalho no verde do Spotify.                                      |
| League           | O campeão da partida aberta, com o nível no adesivo. Cabeçalho azul.                                                                          |
| Qualquer outra   | Relógio, CPU e RAM, no mesmo tipo de cartaz.                                                                                                  |

Os cartazes, no tamanho que o teclado desenha:

| Cursor | Claude | Relógio, CPU e RAM |
|---|---|---|
| ![Cota do Cursor](assets/preview-cursor.png) | ![Cota do Claude](assets/preview-claude.png) | ![Relógio, CPU e RAM](assets/preview-stats.png) |

| Discord, sem chamada | Spotify, tocando | League, na partida |
|---|---|---|
| ![Discord livre](assets/preview-discord.png) | ![Spotify tocando](assets/preview-spotify.png) | ![Campeão](assets/preview-champion.png) |

Os números vêm da sessão já aberta no computador. Não há cota fixa no código, e nenhum token fica neste repositório. Uma leitura fica em cache por 60 segundos. Se a sessão não puder ser lida, o cartaz ainda sai e o log da bandeja diz que a cota não foi lida.

Qual conta é lida depende da janela da frente, não de um aplicativo só aberto atrás. Cursor na frente lê o Cursor. Claude na frente lê o Claude.

### Discord

Com a janela do Discord na frente, o teclado mostra esse cartaz: **ON** ou **OFF**, **CONECTADO** ou **LIVRE** (em inglês, **IN CALL** ou **IDLE**), e o microfone. Os nomes dos executáveis são `discordApps` em `config/screen.json`. O cartaz de exemplo está na fileira acima.

Durante uma chamada de voz, o teclado reveza esse cartaz com o que apareceria no lugar (Claude, Cursor, Spotify, o cartaz do campeão ou o relógio), cerca de 10 segundos cada. Saiu da chamada, o teclado fica no que está na frente. Discord na frente, e fora de chamada, mostra só esse cartaz.

Online significa que o Discord tem uma conexão TCP ativa. Em chamada significa que o log de voz do próprio aplicativo terminou em conectado. O microfone é a sessão de captura do Windows desse processo, e só aparece durante a chamada: aberto, mudo, ou sem sessão de captura. Nada da conta é gravado neste repositório.

### Spotify

O cartaz lê a sessão de mídia do Windows para os aplicativos em `spotifyApps`. Sem conta do Spotify e sem token. O cartaz de exemplo está na fileira acima.

Enquanto uma faixa está **tocando**, este cartaz substitui o relógio. Cursor, Claude e uma partida de League na frente ficam na frente dele. Durante uma chamada do Discord, este cartaz ainda entra na vez dele quando teria substituído o relógio. Se o Spotify for a janela da frente, o cartaz também mostra uma faixa em pausa, ou **SEM MUSICA** / **NOTHING** quando não há faixa. O título quebra em duas linhas. Um nome maior é cortado com `..`.

### League

Com a janela do jogo na frente, e uma partida respondendo em `leagueLiveUrl`, o teclado mostra o campeão. Os nomes dos executáveis são `leagueApps` em `config/screen.json`. O nível no adesivo vem da mesma resposta. O cartaz de exemplo está na fileira acima, ao lado do Discord e do Spotify. O nome nessa foto é um exemplo. No teclado, é o campeão que a partida aberta devolve. Cursor e Claude ficam na frente. As luzes das skills ficam apagadas: a partida não diz se uma skill está pronta, e o pacote de luz do teclado ainda não foi capturado.

### Cursor

O editor guarda o login em `%APPDATA%\Cursor\User\globalStorage\state.vscdb`, na chave `cursorAuth/accessToken`. O Screen Studio abre esse banco só para leitura e envia o token como cabeçalho Bearer. Ele não copia o token para este projeto.

O pedido é um POST para a URL em `config/screen.json` (`usageUrl`), corpo `{}`, com `Content-Type: application/json` e `Connect-Protocol-Version: 1`. O endereço ao vivo é `GetCurrentPeriodUsage` em `api2.cursor.sh`.

Da resposta, o cartaz usa:


| Na tela                  | Campo                                                  |
| ------------------------ | ------------------------------------------------------ |
| Incluído, no canto       | `planUsage.includedSpend` dividido por `planUsage.limit` |
| API                      | `planUsage.apiPercentUsed`                             |
| Auto, na frente          | `planUsage.autoPercentUsed`                            |
| Dias restantes           | `billingCycleEnd`, convertido em dias inteiros         |


Esse endpoint devolve porcentagens do período de cobrança. Ele não devolve um contador bruto de tokens.

### Claude

O aplicativo de desktop guarda a sessão do claude.ai em `%LOCALAPPDATA%\Claude-Data\<profile>\`. O Screen Studio escolhe o perfil que tem `Network\Cookies` e `Local State`, usando o arquivo de cookies gravado por último. O id da organização é o cookie `lastActiveOrg`. O cookie de sessão precisa estar presente. Nenhum desses valores é gravado neste repositório.

Com o Claude aberto, ele trava o banco de cookies. O programa então lê o arquivo pelo handle que o aplicativo já tem, em vez de esperar o travamento cair. A chave em `Local State` é aberta com o DPAPI do Windows, e cada valor de cookie é decifrado com essa chave. Cookies de outros sites são ignorados.

O pedido é um GET para a URL em `config/screen.json` (`claudeUsageUrl`), com `{org}` trocado por essa organização. O endereço ao vivo é `https://claude.ai/api/organizations/{org}/usage`. A chamada é feita com um cliente parecido com o navegador. Uma biblioteca HTTP comum é barrada pela Cloudflare antes do JSON de uso voltar.

Da resposta, o cartaz usa:


| Na tela                              | Campo                                                                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Semana, todos os modelos, na frente  | `limits[]` em que `kind` é `weekly_all`, campo `percent`. Se essa lista faltar, `seven_day.utilization`       |
| Sessão, embaixo                      | `limits[]` em que `kind` é `session`, campo `percent`. Se essa lista faltar, `five_hour.utilization`          |
| Tempo até reiniciar, no adesivo      | `resets_at` do limite semanal, mostrado em minutos, horas ou dias                                            |


Uma organização que só tem acesso de API, e não a sessão do chat, não devolve esse uso. A janela do Claude precisa ser a da frente. Claude rodando atrás do Cursor ainda conta como Cursor.

Cada envio **acrescenta** uma imagem na memória da tela. Não substitui a anterior. A troca segue esta ordem:

1. Sobe a imagem nova enquanto a atual continua visível.
2. Troca a tela para essa imagem nova.
3. Apaga a anterior e pede a página de imagem de novo.

Apagar a imagem que está na tela, ou ficar sem nenhuma, joga o teclado no relógio roxo do firmware. Um cartaz de **CARREGANDO** fica guardado como primeira imagem para esse intervalo.

## Como rodar

Você precisa de Windows, do teclado no USB, e de nenhum outro programa usando o teclado.

### Screen Studio (uso do dia a dia)

Clone o repositório e instale as dependências:

```powershell
git clone https://github.com/RicckVale/titorion-custom-screen.git
cd titorion-custom-screen
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dê um duplo clique em `Screen Studio.bat`.

O programa abre sem janela. A logo fica perto do relógio (às vezes escondida na seta da bandeja). Duplo clique nela abre o preview, o log e o envio avulso de uma imagem. Fechar essa janela só esconde. **Sair**, no menu do ícone, é o que encerra e solta o teclado.

**PT** e **EN** nessa janela trocam o idioma dos cartazes e da janela. SEMANA vira WEEK, SESSAO vira SESSION, e os outros rótulos seguem. A escolha fica em `config/screen.json` (`language`) e o teclado recebe o cartaz novo no próximo envio.

### Iniciar com o Windows

Para o Screen Studio abrir no login, coloque um atalho de `Screen Studio.bat` em:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

Para desligar isso, apague o atalho `Titorion Screen` dessa pasta. Uma cópia que já está rodando continua até você escolher **Sair** na bandeja.

### No navegador

Abra `tools/web/index.html` no Chrome ou no Edge, conecte o teclado e envie uma imagem. Isso é um envio avulso. Não segue a janela em foco.

### Pelo terminal

```powershell
.\.venv\Scripts\python.exe src\check_device.py
.\.venv\Scripts\python.exe src\demo_static.py path\to\image.png
.\.venv\Scripts\python.exe src\demo_stats.py
```

`check_device.py` só lista o dispositivo HID. Não envia nada.

## Como fazer uma tela nova

Os passos estão em [`docs/tecnicos/tela.md`](docs/tecnicos/tela.md): o tamanho 128×128, onde desenhar, como uma troca de modo sai na hora, e a ordem de envio que evita o relógio.

## Mapa

```text
Screen Studio.bat          sobe o programa sem terminal
assets/                    logo do projeto e os previews das telas
config/screen.json         aplicativos observados, URLs de cota e idioma (pt ou en)
src/app.py                 bandeja e janela
src/i18n.py                rótulos em português e inglês
src/screen_frame.py        escolhe a imagem pela janela em foco
src/discord_status.py      Discord online, chamada e microfone
src/spotify_now.py         faixa do Spotify pela sessão de mídia do Windows
src/lol_match.py           campeão da partida aberta de League
src/stats_render.py        desenha os cartazes
src/titorion_screen.py     protocolo da tela
src/active_app.py          janela da frente
src/usage_quota.py         cota do Cursor
src/claude_quota.py        cota do Claude
docs/protocol.md           pacotes HID, fonte da verdade
docs/tecnicos/tela.md      como criar uma tela
tools/web/index.html       envio avulso no navegador
```

## Ainda não

GIF animado, e remapear uma tecla por aplicativo. Esses comandos ainda não foram capturados, então ficam de fora.

## Aviso

Fiz isto por pura curiosidade. Este projeto não é filiado, endossado nem autorizado por ninguém. As marcas citadas continuam dos respectivos donos. O programa só lê o que já está aberto neste computador para desenhar um cartaz.

Se você rodar este software, faz isso por livre e espontânea vontade e por sua conta e risco. Uma escrita ruim ou interrompida pode travar o visor até você reconectar o cabo. Feche qualquer outro programa que esteja usando o teclado antes de conectar por aqui.
