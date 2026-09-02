# Trainer Relay — guia de instalação, testes e logs

Versão deste guia: `v0.1.0-experimental.21.probe.1`

## O que você vai precisar

- Um Steam Deck com Decky Loader e UniFiDeck instalados.
- Um atalho Epic ou GOG criado pelo UniFiDeck.
- Um trainer Windows confiável em arquivo `.exe`.
- O arquivo `TrainerRelay.zip` gerado localmente para `v0.1.0-experimental.21.probe.1`.

O Trainer Relay é complementar ao CheatDeck. Continue usando o CheatDeck para
jogos executados diretamente pelo Steam. Use o Trainer Relay somente nos
atalhos Epic/GOG reconhecidos do UniFiDeck.

Não use `.bat`, argumentos adicionais de trainer, launchers Ubisoft/Amazon ou
mais de uma sessão do mesmo jogo. Esses casos não fazem parte desta versão.

## 1. Conferir o ZIP

O pacote local determinístico candidato à `.19` tem 307.848 bytes e SHA-256:

```text
316C1D172CA3FF806D54ED6B831E92DA242D3354CB8149F1E9991C4A55FD16B1
```

Depois da publicação, o `SHA256SUMS.txt` do kit e o asset do GitHub devem
repetir exatamente esse valor. Se divergirem, não instale o arquivo.

Depois de copiar o ZIP para `Downloads` no Steam Deck, abra o Konsole e rode:

```bash
sha256sum "$HOME/Downloads/TrainerRelay.zip"
```

O valor mostrado precisa ser exatamente o SHA-256 do kit. Não instale o arquivo
`Source code.zip` criado automaticamente pelo GitHub.

## 2. Instalar no Decky

### Opção A — instalar o ZIP local

1. Entre no modo Desktop e copie o ZIP para `/home/deck/Downloads`.
2. Volte ao modo Gaming.
3. Abra o menu de acesso rápido pelo botão `...`.
4. Abra o Decky Loader e suas configurações.
5. Ative as opções de desenvolvedor, se a instalação local não estiver visível.
6. Escolha **Install Plugin from ZIP** ou o nome equivalente da sua versão.
7. Selecione `TrainerRelay.zip` em Downloads.
8. Recarregue o Decky ou reinicie o Steam Deck se o plugin não aparecer.

Os nomes exatos das opções podem variar entre versões do Decky. Sempre use o
ZIP completo, sem descompactá-lo manualmente.

### Opção B — instalar pela URL da release

Nas configurações do Decky, escolha **Install from URL** e informe:

```text
Não há URL de release para `.21.probe.1` antes da validação física. Use o ZIP local entregue com este build.

### Controles de cheat da `.21.probe.1`

Com o jogo UniFiDeck em execução, abra o Quick Access e selecione Trainer Relay.
Um trainer FLiNG reconhecido pelo SHA-256 mostra automaticamente seus cheats e
teclas. Pressione **A** ou toque na linha para enviar o atalho. A mensagem correta
para FLiNG é **Comando enviado; estado desconhecido**: ela confirma o helper, não
o estado interno do trainer.

Se o trainer não for reconhecido, use **Manual controls** na própria sidebar:
digite um nome de até 80 caracteres, escolha a tecla e a combinação finita de
modificadores, e adicione. Não existe campo para VK, comando, argumento ou script.
Trocar o `.exe` muda o SHA-256 e esconde os controles antigos automaticamente.

O executável `TrainerRelay.InputHelper` aparece apenas durante o clique, libera
as teclas e termina. Não use XTest, não adicione permissões root e não deixe o
helper rodando manualmente. Estados reais **Ativado/Desativado** só aparecerão
para trainers cooperativos que confirmem o protocolo v1; trainers FLiNG atuais
permanecem honestamente como estado desconhecido.
```

Não use URLs de outras versões. A `experimental.3` falha ao abrir a tela no
Decky 3.2.6. A `.4` abre, mas bloqueia incorretamente atalhos UniFiDeck cuja
launch option é somente `epic:<id>` ou `gog:<id>`. A `.5` corrige esse bloqueio,
mas depende do seletor modal do Decky. A `.6` adicionou um campo manual que não
atendia ao fluxo desejado. A `.7` porta o controle focável e somente leitura do
CheatDeck para abrir diretamente o navegador nativo do Decky. A `.8` mantém esse
controle e adiciona diagnóstico local em cada fronteira do seletor. O trace real
da `.8` mostrou apenas `plugin-loaded`: a ativação não alcançava o botão dentro
da página roteada. Antes da `.9`, foi auditada a estrutura completa das versões
oficiais `v0.5.1` até `v2.0.0` do CheatDeck: elas usam `SidebarNavigation`, uma
coluna `Focusable` por página e controles diretos; `PanelSection` e
`PanelSectionRow` ficam restritos ao painel de acesso rápido. A `.9` replica essa
arquitetura completa na rota do jogo, inclusive para o seletor. No teste físico,
os controles passaram a receber foco, mas ainda não ativavam. A causa era o
estado legado: migrações `ready` ou `blocked` definiam `disabled=true` também no
seletor. A `.10` libera navegação manual e edição de prefixo, salvando o trainer
desativado, mas o controle ainda combinava um campo desativado, focáveis
aninhados e um botão compacto. A `.11` substitui essa composição por uma única
linha de ação `ButtonItem`, o padrão nativo usado pelo CheatDeck para ações de
página ativadas pelo botão A. O diagnóstico CEF e o journal mostraram então a
causa real da falsa inatividade: na `.11`, o backend Python não iniciava porque
`trainer_relay` estava fora do diretório `py_modules` reconhecido pelo sandbox
do Decky. A `.12` corrige o layout do ZIP e faz a interface informar falha do
backend após cinco segundos, sem deixar os controles indefinidamente em loading.
A `.13` mantém essas correções e adiciona o modo diagnóstico persistente, a
página **Diagnostics**, journal circular de 50 MiB, eventos ao vivo no DevTools
e exportação TXT para Downloads. A `.14` identifica corretamente jogos cujo
`GAMEID` UMU é o genérico `umu-0` e separa o processo Wine real dos wrappers.
A `.15` corrige a revalidação: depois da aquisição rígida, o mesmo PID e start
time não é descartado apenas porque o jogo renomeou a thread principal. O evento
sanitizado `candidate_revalidated` permite confirmar essa transição. A `.16`
reconstrói a chamada UMU a partir da raiz de compatdata do UniFiDeck, sem
reutilizar o `WINEPREFIX=<raiz>/pfx` nem o
`STEAM_COMPAT_CLIENT_INSTALL_PATH` derivados do processo Proton, e garante uma
repetição automática quando a primeira execução termina antes de o watcher ter
observado `running`, mesmo com atraso de polling. Ela continua experimental até
os testes físicos Epic e GOG terminarem.
A `.17` prepara o atalho com `UMU_CONTAINER_NSENTER=1` e usa o caminho explícito
do UMU 1.4.4 para reentrar no container do jogo pelo serviço do mesmo prefixo.
Ela também captura somente caudas sanitizadas e limitadas da saída do processo
UMU, usando `UMU_LOG=info` para não despejar o ambiente derivado completo.
A `.18` corrige a consulta desse serviço: o `steam-runtime-launch-client` usa o
barramento da sessão do usuário Deck/Steam, não o endereço interno herdado do
processo do jogo. Uma falha de preflight fica travada para o mesmo PID e start
time; uma nova tentativa só ocorre pelo botão **Retry** ou numa nova sessão. O
diagnóstico registra apenas classe limitada, exit code, contagem e origem do
barramento, sem copiar stderr nem o ambiente completo.

## Steam Input radial probe

Quando os controles de cheat estiverem prontos na página roteada do jogo, o
Trainer Relay mostra o resumo opcional **Steam Input radial menu**. Esta versão
é somente uma sonda: ela exibe a contagem de comandos/páginas e controles
ignorados, oferece **Export safe probe report** e abre o configurador normal da
Steam. O botão **Generate layout** permanece desativado com o motivo
`Steam Input runtime not physically validated`.

O relatório exportado contém somente metadados sanitizados e é gravado em
`/home/deck/Downloads` com nome `TrainerRelay-steam-input-probe-...json`.
Não contém perfil gravável, payload de Steam, conta, token, caminho privado ou
nome completo do layout. Não aplique nenhuma alteração automaticamente; o
checkpoint físico do Steam Deck é obrigatório antes de qualquer futura versão
com clone de layout.

## 3. Preparar o trainer

1. Crie uma pasta simples, por exemplo `/home/deck/Trainers/NomeDoJogo`.
2. Coloque nela somente o trainer `.exe` que pretende testar.
3. Confirme que o arquivo abre no mesmo jogo/prefixo esperado.
4. Não renomeie `.bat`, `.dll` ou outro tipo de arquivo para `.exe`.

O caminho selecionado no plugin deve ser absoluto, por exemplo:

```text
/home/deck/Trainers/NomeDoJogo/trainer.exe
```

## 4. Configurar um jogo

1. Abra no Steam o atalho Epic/GOG criado pelo UniFiDeck.
2. Abra o menu Decky e entre em **Trainer Relay**.
3. Confira **Launch identity**:
   - Epic deve mostrar `epic:<game_id>`;
   - GOG deve mostrar `gog:<game_id>`.
4. Se aparecer **Unsupported shortcut**, não force a configuração. Confirme que
   o atalho veio do UniFiDeck e contém somente uma identidade literal.
5. Em **Trainer executable**, pressione `A` na linha com o ícone de pasta.
   Navegue pelas pastas do Deck, selecione o trainer `.exe` e confirme. A linha
   mostrará o caminho absoluto selecionado.
6. Deixe **Prefix override** vazio no primeiro teste. Assim será usado o prefixo
   padrão do UniFiDeck.
7. Pressione **Prepare UMU container re-entry**, revise a mudança e confirme.
   O plugin adiciona somente `UMU_CONTAINER_NSENTER=1`, relê os detalhes do
   atalho e habilita o relay apenas após a confirmação do Steam.
8. Se o jogo estava aberto, feche-o. Inicie novamente pelo mesmo atalho; a
   preparação não funciona retroativamente em um container já iniciado.

### Se aparecer migração legada

O plugin pode encontrar as variáveis antigas:

- `PROTON_REMOTE_DEBUG_CMD`;
- `PRESSURE_VESSEL_FILESYSTEMS_RW`.

Confira cuidadosamente o trainer mostrado. Se estiver correto, confirme a
migração. O Trainer Relay deve:

1. salvar a configuração desabilitada;
2. remover somente as duas variáveis antigas e adicionar
   `UMU_CONTAINER_NSENTER=1`;
3. preservar `%command%`, `epic:<id>`/`gog:<id>` e as demais opções;
4. reler os detalhes do atalho;
5. habilitar o trainer somente depois da confirmação do Steam.

Se o trainer mostrado estiver errado, cancele. Não edite as launch options no
meio da migração.

## 5. Estados esperados

| Estado | Significado | O que fazer |
| --- | --- | --- |
| `disabled` | Configuração desligada | Selecione o `.exe` e habilite |
| `waiting_for_game` | Ainda não encontrou uma sessão exata | Aguarde o jogo abrir |
| `launching` | Trainer iniciado; o plugin aguarda a confirmação exata de reentrada do UMU e três segundos de atividade | Aguarde pelo menos 3 segundos |
| `running` | A reentrada no container foi confirmada e o trainer permaneceu ativo | Teste uma função simples |
| `retrying` | Primeira execução terminou cedo | Aguarde a única repetição automática |
| `failed` | Trainer falhou sem afetar o jogo | Corrija o trainer e use Retry |
| `ambiguous` | Mais de uma sessão candidata | Feche instâncias duplicadas |
| `invalid_config` | Configuração, ambiente, UMU ou opções legadas inválidas | Anote o código e colete os logs |

Se o código for `container_reentry_missing`, finalize a preparação no plugin,
feche o jogo atual e abra novamente. O plugin não tenta anexar o trainer a uma
sessão antiga sem o serviço de container.

Se o código for `container_reentry_bus_missing`, o jogo recebeu a opção, mas o
serviço do mesmo prefixo não apareceu depois de no máximo cinco invocações
totais do launch-client entre todos os candidatos de sessão. Feche o
jogo, confirme que a preparação continua nas launch options, abra novamente e
gere um TXT. `container_reentry_unsupported` indica que o runtime/Proton ativo
não pôde ser identificado com segurança; `container_reentry_probe_failed`
indica falha ao consultar o serviço. Nesses três casos, nenhum trainer é
iniciado e o jogo fica intacto.

`container_reentry_identity_mismatch` significa que o App ID capturado não
confere com a identidade derivada do prefixo. `container_reentry_confirmation_failed`
significa que o serviço existia no preflight, mas o processo UMU não confirmou
a reentrada em até três segundos. Nesse segundo caso, o plugin encerra somente
o grupo de processos que ele próprio criou, deixa o jogo intacto e exige Retry
manual para a mesma sessão. No TXT, a sequência saudável é
`container_reentry_verified`, `trainer_spawned`,
`container_reentry_confirmed`, `trainer_running`.

## 6. Teste mínimo obrigatório

Faça primeiro com um jogo. Depois repita com um título da outra loja.

- [ ] O jogo chega ao menu principal antes do trainer.
- [ ] O status chega a `running`.
- [ ] Existe apenas uma instância do trainer.
- [ ] O trainer controla o jogo correto.
- [ ] Fechar o jogo também encerra o trainer.
- [ ] Uma falha do trainer não fecha o jogo.
- [ ] Force Sync do UniFiDeck não apaga a configuração.
- [ ] Epic e GOG passam separadamente.

Não promova nem trate esta versão como estável antes de um jogo Epic e um GOG
passarem por essa lista.

## 7. Coletar logs com segurança

### Método recomendado na `.13`: gerar o TXT no próprio plugin

1. Abra qualquer atalho que tenha a rota do Trainer Relay e entre na página
   **Diagnostics**. Ela é global e continua disponível mesmo se o atalho atual
   não for Epic/GOG reconhecido.
2. Ative **Persistent diagnostic mode**. A preferência permanece ativada após
   reiniciar o Steam/Decky até você desligá-la manualmente.
3. Abra o jogo e reproduza o problema. O journal mantém no máximo cinco arquivos
   de 10 MiB, totalizando 50 MiB.
4. Volte à página **Diagnostics** e confira os 20 eventos mais recentes.
5. Pressione **Export TXT to Downloads**. O caminho final aparece em **Last TXT
   export** e normalmente é
   `/home/deck/Downloads/TrainerRelay-diagnostics-AAAAMMDD-HHMMSS.txt`.
6. Envie esse TXT primeiro. Ele já contém identidade, PID/start time, decisões
   do watcher, prefixos/caminhos permitidos, UMU, spawn, retry e encerramento em
   ordem cronológica.

**Clear logs** pede confirmação e remove somente o journal rotativo e seus
metadados. Ele não apaga TXT já exportado, configuração de jogo, trainer,
prefixo, UniFiDeck ou logs de outros plugins.

O TXT/journal aceita apenas campos técnicos predefinidos. Não registra ambiente
completo, linha de comando completa, conteúdo de comando de debug legado,
credenciais, cookies, tokens ou autorização. Para diagnóstico do launcher,
pode registrar somente caudas pequenas e sanitizadas dos pipes stdout/stderr
herdados do processo UMU. Como Proton/Wine e o trainer podem herdar esses pipes,
revise essa pequena cauda antes de compartilhar o TXT.

Os comandos abaixo ficam como alternativas avançadas caso o próprio backend do
plugin não consiga iniciar. Faça o problema acontecer e, sem reiniciar o Deck,
entre no modo Desktop e abra o Konsole.

### Log filtrado do Decky — envie primeiro este

```bash
sudo journalctl -b 0 -u plugin_loader.service --no-pager \
  | grep -i -E 'trainer relay|trainer_relay|umu|unifideck' \
  > "$HOME/Downloads/trainer-relay-decky-filtrado.log"
```

### Log completo do Decky — guarde para diagnóstico

```bash
sudo journalctl -b 0 -u plugin_loader.service --no-pager \
  > "$HOME/Downloads/trainer-relay-decky-completo.log"
```

O log completo inclui outros plugins. Revise-o antes de compartilhar.

### Log frontend do Steam/CEF

Na versão `.13`, abra o Console do DevTools CEF, escolha **Default levels** no
filtro de nível. Para o fluxo do watcher, informe este texto em **Filter**:

```text
[TrainerRelay:diagnostic]
```

Cada linha é um evento sanitizado igual ao journal. A ponte funciona enquanto
o modo diagnóstico estiver ativado, mesmo com a página Diagnostics fechada. Um
erro de polling gera apenas `polling_unavailable` com backoff, sem expor a
exceção interna.

Para investigar especificamente o navegador de trainer, use:

```text
[TrainerRelay:picker]
```

Abra a tela do Trainer Relay e pressione o botão de pasta uma vez. A sequência
normal começa com `plugin-loaded`, `ui-activated`, `handler-enter`,
`home-requested`, `home-resolved` e `api-call`. Depois disso:

- `api-resolved` indica que o modal devolveu uma seleção;
- `api-rejected` indica cancelamento ou rejeição do modal;
- `handler-blocked` indica que a configuração ainda não estava pronta;
- `handler-failed` contém apenas uma razão limitada da falha;
- se `api-call` for a última mensagem, a promessa do modal ficou pendente.

O diagnóstico do seletor não registra o caminho completo escolhido nem o
ambiente do jogo. Fotografe ou copie toda a sequência filtrada.

Como alternativa, extraia o arquivo CEF:

```bash
grep -i -E 'trainer relay|trainer-relay|trainer_relay' \
  "$HOME/.steam/steam/logs/cef_log.txt" \
  > "$HOME/Downloads/trainer-relay-frontend.log"
```

Se o problema ocorreu antes de reiniciar o Steam, verifique também
`cef_log.previous.txt`.

### Localizar logs próprios do plugin/trainer

```bash
find "$HOME/homebrew/logs" -maxdepth 4 -type f \
  \( -iname '*trainer*relay*' -o -iname '*trainer-relay*' \) -print
```

Para cada arquivo encontrado, copie apenas as 500 linhas finais:

```bash
find "$HOME/homebrew/logs" -maxdepth 4 -type f \
  \( -iname '*trainer*relay*' -o -iname '*trainer-relay*' \) -print0 \
  | xargs -0 -r tail -n 500 \
  > "$HOME/Downloads/trainer-relay-plugin.log"
```

### Evidência limitada do processo

Com o jogo ainda aberto:

```bash
pgrep -af 'unifideck-launcher' \
  > "$HOME/Downloads/trainer-relay-launcher.txt"
```

Se você identificar manualmente o PID do processo Windows correto, substitua
`<PID>` somente nos comandos abaixo:

```bash
readlink -f "/proc/<PID>/exe"
stat -c '%d:%i:%Y:%n' "/proc/<PID>"
tr '\0' '\n' < "/proc/<PID>/environ" \
  | grep -E '^(STEAM_COMPAT_DATA_PATH|WINEPREFIX|SteamAppId|SteamGameId|GAMEID|STORE)='
```

Nunca envie a saída completa de `/proc/<PID>/environ`, `env`, `printenv`,
launch options privadas, cookies, tokens ou credenciais.

## 8. O que enviar no relatório

Copie e preencha:

```text
Trainer Relay: v0.1.0-experimental.21.probe.1
SteamOS:
Decky Loader:
UniFiDeck:
Loja: Epic / GOG
Launch identity exibida:
Jogo:
Trainer e versão:
Status final:
Código de diagnóstico, se houver:
O jogo abriu antes do trainer? sim/não
Quantas instâncias do trainer apareceram?
O trainer fechou junto com o jogo? sim/não
Force Sync preservou a configuração? sim/não
Passos exatos para reproduzir:
Resultado esperado:
Resultado observado:
```

Anexe preferencialmente:

- o TXT criado por **Diagnostics > Export TXT to Downloads**;
- `trainer-relay-decky-filtrado.log`;
- `trainer-relay-frontend.log`;
- `trainer-relay-plugin.log`, se existir;
- uma captura do status no plugin;
- o relatório preenchido.

Só envie o log completo após revisar o conteúdo.

## 9. Solução rápida de problemas

- Plugin não aparece: recarregue o Decky ou reinicie o Steam Deck.
- O botão de pasta não abre o navegador: confirme que a versão instalada é a
  `.12` ou posterior, filtre `[TrainerRelay:picker]` no Console e pressione o
  botão uma vez.
- `Unsupported shortcut`: recrie/sincronize o atalho pelo UniFiDeck.
- `waiting_for_game`: na `.17`, ative Diagnostics e procure
  `candidate_rejected`/`process_scan_summary`; não pressione Retry repetidamente
  durante o carregamento.
- `session_ended` seguido imediatamente de `owned_group_signal`: na `.17`,
  procure antes por `candidate_revalidated`. Ele confirma que o mesmo PID e
  start time foram mantidos mesmo se o jogo renomeou a thread principal.
- `ambiguous`: feche o jogo, launcher e instâncias duplicadas; abra novamente.
- `invalid_config (container_reentry_missing)`: confirme a preparação, feche o
  jogo aberto antes dela e inicie novamente.
- outro `invalid_config`: conclua a migração e remova variáveis legadas
  reintroduzidas pelo CheatDeck naquele atalho UniFiDeck.
- `failed`: confira se o caminho é absoluto, o arquivo é `.exe` regular e o
  trainer corresponde à versão do jogo.
- Trainer sem janela: use o botão Steam para alternar entre janelas abertas.

## 10. Desativar ou remover

Para interromper o uso em um jogo, desligue **Enabled**. Para remover o plugin,
use o gerenciador de plugins do Decky. O jogo e seu atalho UniFiDeck devem
continuar independentes do Trainer Relay.

Não apague prefixos Wine, `games.map`, UniFiDeck, Proton ou Steam Runtime como
parte do rollback.

## Links oficiais

- Build de validação: `v0.1.0-experimental.21.probe.1` (sem tag/release até o gate físico)
- Decky Loader: https://github.com/SteamDeckHomebrew/decky-loader
- Estrutura oficial de ZIP Decky: https://github.com/SteamDeckHomebrew/decky-plugin-template
