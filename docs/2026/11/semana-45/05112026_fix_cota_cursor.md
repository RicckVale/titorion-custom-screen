# Cota do Cursor na tela

## Contexto

O Cursor passou a gravar o login cifrado em `state.vscdb`, com o prefixo `cursor-safe-storage:v1:`. O Screen Studio enviava esse texto como Bearer. A API de uso respondia 401 e o cartaz ficava em "SEM COTA".

## Correção

A leitura continua só no banco local. Quando o valor está cifrado, ele é aberto na memória com a chave de `Local State` e descartado em seguida. Nada de token entra neste repositório. Uma sessão antiga, ainda em texto, segue o caminho de antes.

## Verificação

Com a sessão deste computador, `GetCurrentPeriodUsage` voltou a responder 200 e os campos de Auto, API e incluído.
