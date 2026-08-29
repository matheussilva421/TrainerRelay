# Trainer Relay — guia de instalação, testes e logs

Versão deste guia: `v0.1.0-experimental.7`

## O que você vai precisar

- Um Steam Deck com Decky Loader e UniFiDeck instalados.
- Um atalho Epic ou GOG criado pelo UniFiDeck.
- Um trainer Windows confiável em arquivo `.exe`.
- O arquivo `TrainerRelay-v0.1.0-experimental.7.zip`.

O Trainer Relay é complementar ao CheatDeck. Continue usando o CheatDeck para
jogos executados diretamente pelo Steam. Use o Trainer Relay somente nos
atalhos Epic/GOG reconhecidos do UniFiDeck.

Não use `.bat`, argumentos adicionais de trainer, launchers Ubisoft/Amazon ou
mais de uma sessão do mesmo jogo. Esses casos não fazem parte desta versão.

## 1. Conferir o ZIP

O arquivo correto tem:

- tamanho: `176394` bytes;
- SHA-256:
  `6375AF2391AB01179103F1A3E9A374CF56C69C0E4D377FC43E337B40CFEA6B73`.

Depois de copiar o ZIP para `Downloads` no Steam Deck, abra o Konsole e rode:

```bash
sha256sum "$HOME/Downloads/TrainerRelay-v0.1.0-experimental.7.zip"
```

O valor mostrado precisa ser exatamente o SHA-256 acima. Não instale o arquivo
`Source code.zip` criado automaticamente pelo GitHub.

## 2. Instalar no Decky

### Opção A — instalar o ZIP local

1. Entre no modo Desktop e copie o ZIP para `/home/deck/Downloads`.
2. Volte ao modo Gaming.
3. Abra o menu de acesso rápido pelo botão `...`.
4. Abra o Decky Loader e suas configurações.
5. Ative as opções de desenvolvedor, se a instalação local não estiver visível.
6. Escolha **Install Plugin from ZIP** ou o nome equivalente da sua versão.
7. Selecione `TrainerRelay-v0.1.0-experimental.7.zip` em Downloads.
8. Recarregue o Decky ou reinicie o Steam Deck se o plugin não aparecer.

Os nomes exatos das opções podem variar entre versões do Decky. Sempre use o
ZIP completo, sem descompactá-lo manualmente.

### Opção B — instalar pela URL da release

Nas configurações do Decky, escolha **Install from URL** e informe:

```text
https://github.com/matheussilva421/TrainerRelay/releases/download/v0.1.0-experimental.7/TrainerRelay.zip
```

Não use URLs de outras versões. A `experimental.3` falha ao abrir a tela no
Decky 3.2.6. A `.4` abre, mas bloqueia incorretamente atalhos UniFiDeck cuja
launch option é somente `epic:<id>` ou `gog:<id>`. A `.5` corrige esse bloqueio,
mas depende do seletor modal do Decky. A `.6` adicionou um campo manual que não
atendia ao fluxo desejado. A `.7` porta o controle focável e somente leitura do
CheatDeck para abrir diretamente o navegador nativo do Decky.

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
5. Em **Trainer executable**, pressione o botão compacto com ícone de pasta.
   Navegue pelas pastas do Deck, selecione o trainer `.exe` e confirme. O campo
   ao lado é somente leitura e mostrará o caminho selecionado.
6. Deixe **Prefix override** vazio no primeiro teste. Assim será usado o prefixo
   padrão do UniFiDeck.
7. Se não houver migração legada, ative manualmente **Enabled**.
8. Inicie o jogo pelo mesmo atalho.

### Se aparecer migração legada

O plugin pode encontrar as variáveis antigas:

- `PROTON_REMOTE_DEBUG_CMD`;
- `PRESSURE_VESSEL_FILESYSTEMS_RW`.

Confira cuidadosamente o trainer mostrado. Se estiver correto, confirme a
migração. O Trainer Relay deve:

1. salvar a configuração desabilitada;
2. remover somente as duas variáveis antigas;
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
| `launching` | Trainer iniciado, ainda no período de confirmação | Aguarde pelo menos 3 segundos |
| `running` | Trainer permaneceu ativo e foi aceito | Teste uma função simples |
| `retrying` | Primeira execução terminou cedo | Aguarde a única repetição automática |
| `failed` | Trainer falhou sem afetar o jogo | Corrija o trainer e use Retry |
| `ambiguous` | Mais de uma sessão candidata | Feche instâncias duplicadas |
| `invalid_config` | Configuração, ambiente, UMU ou opções legadas inválidas | Anote o código e colete os logs |

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

Faça o problema acontecer e, sem reiniciar o Deck, entre no modo Desktop e
abra o Konsole.

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
Trainer Relay: v0.1.0-experimental.7
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

- `trainer-relay-decky-filtrado.log`;
- `trainer-relay-frontend.log`;
- `trainer-relay-plugin.log`, se existir;
- uma captura do status no plugin;
- o relatório preenchido.

Só envie o log completo após revisar o conteúdo.

## 9. Solução rápida de problemas

- Plugin não aparece: recarregue o Decky ou reinicie o Steam Deck.
- O botão de pasta não abre o navegador: confirme que a versão instalada é a
  `.7`, reinicie o Steam e colete o log frontend/CEF antes de tentar novamente.
- `Unsupported shortcut`: recrie/sincronize o atalho pelo UniFiDeck.
- `waiting_for_game`: aguarde o processo real do jogo; não pressione Retry
  repetidamente durante o carregamento.
- `ambiguous`: feche o jogo, launcher e instâncias duplicadas; abra novamente.
- `invalid_config`: conclua a migração e remova variáveis legadas reintroduzidas
  pelo CheatDeck naquele atalho UniFiDeck.
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

- Release recomendada: https://github.com/matheussilva421/TrainerRelay/releases/tag/v0.1.0-experimental.7
- Decky Loader: https://github.com/SteamDeckHomebrew/decky-loader
- Estrutura oficial de ZIP Decky: https://github.com/SteamDeckHomebrew/decky-plugin-template
