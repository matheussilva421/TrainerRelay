# Decky Loader: instalação/reload local e evidências de ativação

**Data da pesquisa:** 2026-09-05
**Pesquisador:** Davos
**Escopo:** `C:\Users\slvma\Downloads\Github\TrainerRelay`, build experimental instalada a partir de ZIP no Steam Deck.
**Limite operacional:** pesquisa read-only. Nenhum comando foi executado no Steam Deck; nenhum arquivo do Deck foi alterado. Neste repositório, o único arquivo criado por esta tarefa é este relatório. O diretório preexistente `.codex-remote-attachments/` não foi lido nem tocado. Não houve commit nem push.

## Resposta curta

O caminho upstream é:

1. Produzir um ZIP de plugin válido, com **um diretório de primeiro nível** contendo `plugin.json`, `dist/index.js` e, quando houver backend Python, `main.py`; `package.json` fornece a versão. Essa é a estrutura descrita pelo [template oficial de plugin](https://github.com/SteamDeckHomebrew/decky-plugin-template#readme).
2. Preservar antes da troca uma cópia íntegra do ZIP conhecido-bom e um hash SHA-256. O instalador do Decky aceita um artefato local `file://` e pode validar o hash informado, mas, se o plugin já existe, o código upstream desinstala a cópia anterior antes de extrair a nova. Portanto, **a reversibilidade não é um backup automático do Decky**; ela depende de manter o artefato anterior e, se necessário, uma cópia da pasta instalada/configuração relevante fora de `~/homebrew/plugins/`.
3. No Deck, com Developer Mode habilitado, escolher a instalação local do ZIP no Developer/Plugin settings e confirmar. No código upstream, o fluxo local lê o arquivo, extrai no diretório de plugins, ajusta permissões, importa o backend e conclui a instalação; o fluxo de URL é separado.
4. Para iteração sem nova instalação, usar a ação upstream de reload do plugin no Decky. O loader descarrega o frontend anterior, importa novamente `dist/index.js` com cache-buster e atualiza o estado da lista; a rota de reload do backend enfileira o `main.py` para ser reiniciado. Para recarregar tudo, o template oficial também fornece a tarefa `restartdecky`, que executa `systemctl restart plugin_loader`.
5. Validar por camadas, nesta ordem: hash/arquivo copiado → plugin reconhecido pelo loader → processo/backend carregado e respondendo → bundle frontend importado e painel ativo. A presença do ZIP, o nome no menu ou uma pasta de log isoladamente não provam a cadeia inteira.

## O que é oficialmente documentado e o que é inferência de rollback

O README do [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/README.md) documenta o uso de plugins pelo menu Decky, incluindo instalar, atualizar, desinstalar e recarregar; também diz que, para desenvolvimento, é necessário buildar, fazer deploy e recarregar a cada ciclo. O README remete ao wiki Deckbrew e ao template oficial, mas não descreve ali todos os detalhes do sideload local.

O [template oficial](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/README.md) documenta a estrutura do ZIP e o fluxo de desenvolvimento via tarefas. A tarefa oficial [`.vscode/tasks.json`](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/.vscode/tasks.json#L76-L119) copia `out/` para `~/homebrew/plugins`, extrai o ZIP e compõe `builddeploy`; a tarefa [de restart](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/.vscode/tasks.json#L141-L146) reinicia `plugin_loader`.

O código upstream torna explícito o caminho local: [`browser.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/browser.py#L158-L193) trata `file://` como ZIP local e lê o arquivo; [`browser.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/browser.py#L53-L59) calcula SHA-256 quando um hash foi fornecido e extrai o arquivo; [`browser.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/browser.py#L237-L268) mostra a sequência de substituir a instalação existente e chamar `import_plugin`.

Daí a distinção importante:

- **Oficial:** formato do ZIP, instalação local/URL, extração, permissões, importação e reload.
- **Camada reversível recomendada:** salvar ZIP conhecido-bom + hash antes da operação; opcionalmente copiar a pasta instalada e registrar os diretórios de dados/configuração. Isso é uma salvaguarda operacional derivada do comportamento destrutivo da substituição upstream, não uma promessa de rollback transacional do Decky.

## Procedimento local experimental com rollback preservado

Os passos abaixo são um procedimento para execução futura; não foram executados nesta pesquisa.

### 1. Preparar e verificar o artefato no PC

No `TrainerRelay`, gerar o ZIP usando o fluxo do projeto e confirmar o layout com os checks locais já existentes. Antes de transferir:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath .\TrainerRelay.zip
```

No próprio Deck, depois da transferência, repetir a verificação com `sha256sum`. A evidência é o mesmo hash do arquivo em trânsito e do arquivo que será selecionado. Não usar o `Source code.zip` automático do GitHub: o template oficial exige um ZIP de distribuição com a pasta/arquivos de runtime.

Estado local observado durante esta pesquisa, sem alteração:

- `plugin.json.name`: `Trainer Relay`;
- `package.json.version`: `0.1.0-experimental.23`;
- `TrainerRelay.zip`: 754.825 bytes, SHA-256 `83FF43CE6F935371847E54C50061BFB73304732E3D05BDC745431ABAA9A494C1`.

Esses valores identificam o artefato local observado; não são evidência de que ele esteja instalado ou ativo no Deck.

### 2. Criar o ponto de rollback antes de instalar

Fora de `~/homebrew/plugins/`, manter:

- o ZIP conhecido-bom atualmente instalado e seu SHA-256;
- o ZIP experimental e seu SHA-256;
- se a instalação atual tiver dados importantes, uma cópia separada da pasta do plugin e um inventário dos diretórios de settings/data/logs que devem permanecer.

Não apagar a instalação anterior antes de existir essa cópia. O código do instalador upstream chama `uninstall_plugin` quando encontra o mesmo plugin; essa rotina para o processo, remove a pasta do plugin e limpa entradas de estado do loader. O README upstream também limita a remoção do uninstall aos arquivos do plugin, não a arquivos que o plugin tenha criado; portanto rollback de código e rollback de dados são coisas diferentes.

### 3. Instalar o ZIP experimental

No Steam Deck:

1. Ativar Developer Mode, se a seção Developer não estiver visível.
2. Abrir a opção upstream de instalação de plugin local/ZIP e selecionar o arquivo transferido.
3. Conferir o nome/versão exibidos e confirmar somente depois de comparar o hash.
4. Aguardar a conclusão; não considerar “selecionar o arquivo” como prova de instalação.

O caminho implementado em [`browser.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/browser.py#L176-L181) distingue `file://` de URL. Depois, [`browser.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/browser.py#L248-L268) extrai, procura a pasta pelo `plugin.json`, aplica permissões, registra a instalação e chama o carregamento do backend. Se já havia uma cópia instalada, a remoção anterior ocorre antes da extração nova; por isso o backup do passo 2 é obrigatório para um rollback realmente reversível.

### 4. Recarregar sem reinstalar

Quando apenas os arquivos de uma build já instalada foram atualizados:

- usar o reload do plugin no Decky para a iteração normal;
- se a mudança for de backend e a ação disponível for somente frontend, reiniciar o loader inteiro pelo mecanismo do template oficial (`systemctl restart plugin_loader`) e depois reabrir o Decky;
- não iniciar uma segunda instância manual do `PluginLoader` enquanto o serviço estiver ativo.

O backend expõe a rota websocket [`loader/reload_plugin`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/loader.py#L80-L90), que coloca novamente o arquivo do plugin na fila de reload em [`loader.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/loader.py#L177-L180). O frontend, ao receber a importação, descarrega o plugin anterior e importa `http://127.0.0.1:1337/plugins/<nome>/dist/index.js?t=<timestamp>` antes de atualizar o estado, conforme [`plugin-loader.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/plugin-loader.tsx#L369-L437).

### 5. Rollback

Se a build experimental falhar:

1. Não apagar dados do jogo, Steam, Proton, UniFiDeck ou outros plugins.
2. Reinstalar pelo mesmo caminho o ZIP conhecido-bom previamente preservado, validando o SHA-256 antes da confirmação.
3. Recarregar o plugin; se o loader inteiro estiver inconsistente, usar o restart upstream do `plugin_loader`.
4. Revalidar as quatro camadas abaixo e comparar a versão observada com a versão do ZIP conhecido-bom.

Se for preciso restaurar exatamente uma pasta, a substituição deve ser feita com o serviço parado e uma cópia ainda mantida; essa restauração direta é uma operação administrativa de recuperação, não o procedimento de instalação documentado pelo Decky. Não remover a cópia de rollback até o teste do estado restaurado terminar.

## Evidências autoritativas por camada

| Camada | Evidência forte | O que ainda não prova |
|---|---|---|
| **Arquivo copiado** | Hash SHA-256 igual no PC e no Deck; listagem do ZIP mostra uma pasta de primeiro nível e os arquivos exigidos (`plugin.json`, `dist/index.js`, `main.py` quando aplicável). O layout é definido pelo [template oficial](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/README.md). | Não prova que o arquivo foi extraído no diretório correto, reconhecido ou executado. Uma cópia em `Downloads` é apenas transporte. |
| **Plugin reconhecido** | No log do serviço, `plugin_path: ...`, `import plugins from ...` e `found plugin: <diretório>`; ou resposta de `loader/get_plugins` contendo `name`, `version`, `load_type` e `disabled`. A enumeração está em [`loader.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/loader.py#L117-L119) e [`loader.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/loader.py#L171-L176). | Ainda pode ser um plugin passivo/sem backend. O loader consegue registrar metadados sem provar que o processo Python permanece vivo. |
| **Backend carregado** | Log `Loaded <nome> (v<versão>)` após `plugin.start()`; o start cria um processo separado em [`plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/plugin.py#L123-L129). A evidência mais forte é uma chamada RPC inofensiva do frontend que retorna sucesso: [`execute_method`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/plugin.py#L113-L121) envia pelo socket e [`sandboxed_plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py#L178-L200) despacha a chamada para o método Python. | `Loaded` prova que o processo foi iniciado naquele instante, não que uma operação posterior funcionará. A existência de `~/homebrew/logs/<plugin>` sozinha não prova backend: o diretório é criado no construtor do wrapper, antes do `start`, em [`plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/plugin.py#L63-L70). |
| **Frontend ativo** | O loader importa o bundle ESM, chama o export default e adiciona o plugin à lista em [`plugin-loader.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/plugin-loader.tsx#L417-L437); o plugin aparece como item renderizável e abre seu conteúdo em [`PluginView.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/components/PluginView.tsx#L23-L39) e [`PluginView.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/components/PluginView.tsx#L50-L60). A conexão do frontend com a API do loader também registra `Plugin <nome> connected to loader API` em [`plugin-loader.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/plugin-loader.tsx#L634-L686). | Nome/ícone visível isoladamente não basta: em erro de importação o loader também cria um item de erro com o nome do plugin, conforme [`plugin-loader.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/plugin-loader.tsx#L473-L506). É necessário abrir o painel e confirmar que o conteúdo esperado renderiza sem o bloco de erro. |

## Sequência de coleta no Deck, sem ambiguidade

Para uma validação futura, capturar evidências sem misturar camadas:

1. **Artefato:** hash do ZIP selecionado e listagem dos caminhos.
2. **Reconhecimento:** trecho do `journalctl` do `plugin_loader` contendo `found plugin`, além da versão retornada em `loader/get_plugins`/exibida pelo loader.
3. **Backend:** linha `Loaded ...` e uma chamada RPC segura que retorne sucesso; se houver log próprio, registrar somente o trecho sanitizado necessário.
4. **Frontend:** log `Trying to load` seguido de `Loaded ... in ...ms`, ausência de `Error loading plugin`, abertura do item no Decky e renderização do painel.
5. **Rollback gate:** manter o ZIP anterior e verificar que ele continua disponível antes de encerrar a validação.

Uma falha em uma camada interrompe a conclusão: por exemplo, “ZIP tem os arquivos” não autoriza concluir “backend carregado”; “backend responde” não autoriza concluir “frontend novo está ativo”; e “painel abriu” não prova que o backend respondeu a uma ação específica.

## Limites e estado desta pesquisa

- As fontes usadas para o procedimento e para a cadeia de carregamento são somente o [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader), o [template oficial de plugins](https://github.com/SteamDeckHomebrew/decky-plugin-template) e o código oficial hospedado nesses repositórios; o README do Decky remete ao [wiki Deckbrew](https://wiki.deckbrew.xyz/en/plugin-dev/getting-started), mas o detalhe verificável aqui veio do código/repositórios upstream.
- O README upstream diz que a documentação de desenvolvimento ainda não é completa; portanto não há uma garantia única de rollback transacional para uma atualização local.
- A análise não executou instalação, reload, `systemctl`, SSH, transferência, teste físico, consulta de logs do Deck ou chamada RPC no dispositivo.
- A análise não prova que `0.1.0-experimental.23` esteja instalado/ativo; somente identifica o artefato local observado no `TrainerRelay`.
- `TrainerRelay.zip` permaneceu intocado. Nenhum teste, build, embalagem, commit ou push foi executado nesta pesquisa.

## Handoff/retomada

Para continuar com autorização explícita de validação física: ler este relatório, conferir o hash do ZIP conhecido-bom e do experimental no Deck, criar o rollback externo, instalar pelo Developer/ZIP, coletar as quatro evidências na ordem indicada, e parar no primeiro gate que não for demonstrado. Se o estado falhar, reinstalar o ZIP conhecido-bom preservado antes de qualquer nova tentativa.
