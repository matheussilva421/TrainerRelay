# Relatório final — Mortal Shell Epic + FLiNG / Trainer Relay

Data: 2026-09-07  
Estado: encerrado a pedido do usuário; problema não corrigido de forma reproduzível.

## Resumo executivo

O projeto chegou a uma prova manual de que o Mortal Shell, o prefixo real e o FLiNG podem coexistir no Steam Deck: a janela completa do trainer apareceu, ficou selecionável pelo botão Steam e há um registro anterior de `Infinite Stamina` funcionando e revertendo. Isso não foi transformado em uma receita automática estável.

Na integração do Trainer Relay, o resultado repetido foi: o jogo abre, o trainer pode aparecer, e em poucos segundos o jogo ou ambos encerram. A última execução `.36` confirmou a reentrada do contêiner por um ACK real, mas o jogo encerrou aproximadamente 6 segundos depois. A causa do encerramento não foi identificada.

Os problemas de clique são separados: em algumas sessões a UI apareceu, sliders responderam, mas toque e trackpad acertaram coordenadas erradas ou a região “English”; em outras a janela ficou preta/branca ou não apareceu no seletor. Não existe um PASS reproduzível de clique físico no toggle.

## O que foi comprovadamente bem-sucedido

- O caminho GOG/UniFiDeck foi usado como baseline funcional e preservado.
- Remover Force Compatibility fez o jogo voltar a iniciar depois de uma tentativa que o havia quebrado. Force Compatibility não deve ser reativado.
- O SSH para `deck@192.168.1.247` foi restabelecido. A impressão digital verificada foi `SHA256:YkrB6o3zby/e8NdZ/Kzx3yBDH01ZFQEg9XBTl/0/8mI`.
- A janela nativa completa do FLiNG apareceu em um lançamento manual privado usando GE-Proton11-6, Mono privado e o prefixo real. O usuário conseguiu alternar entre jogo e trainer pelo seletor Steam nessa execução.
- Houve um registro histórico de cheat funcionando e revertendo; o método exato não ficou reconstituído como teste de clique físico. O último estado observado para cliques foi falho.
- O atalho original do UniFiDeck foi restaurado para `epic:0055e45ce7654c55aade646467349e83`; GOG permaneceu habilitado.
- As versões `.34`, `.35` e `.36` foram instaladas pelo fluxo oficial do Decky com hashes conferidos e backups de rollback. A `.36` confirmou reentrada real, sem usar Force Compatibility.
- A correção de ACK da `.36` eliminou uma falsa confirmação local: o evento passou a ser emitido dentro do `steam-runtime-launch-client` e validado por sessão/barramento.

## O que falhou

### Execução automática

- `.28`: perfil privado não selecionado por uma suposição incorreta sobre `lib64`; caiu na rota errada.
- `.29`: o trainer falhou com `Bad server socket 22 : Bad file descriptor` por herdar `WINESERVERSOCKET`.
- `.30`: removeu o socket inválido, mas o jogo encerrou pouco depois do attach.
- `.31`: o atraso de 30 segundos não resolveu a instabilidade.
- `.32`/`.33`/`.34`: o trainer chegou a abrir em algumas execuções, mas o jogo encerrou primeiro ou ambos fecharam em poucos segundos.
- `.35`: a reentrada oficial foi usada, mas a sessão continuou instável.
- `.36`: sequência observada: `container_reentry_verified` → `trainer_spawned` → `container_reentry_confirmed` → `trainer_running` → `session_ended`; o jogo encerrou primeiro, sem `trainer_exited` anterior.

### Janela e entrada

- A janela do FLiNG ficou preta, branca ou parcialmente renderizada em várias tentativas.
- Quando a UI ficou visível, sliders responderam, mas toggles por toque/trackpad não responderam corretamente.
- O clique podia selecionar outra parte da janela, inclusive “English”, indicando divergência de superfície, foco, escala ou coordenadas absolutas.
- O patch upstream do Gamescope para escala de input absoluto foi localizado, mas não foi aplicado nem validado no Steam Deck.

### Última tentativa `.37`

- Pacote local: `0.1.0-experimental.37`.
- SHA-256: `85842928c2e0aae2367ce460485a2eb02acf595a12c07873db31de8328ea919a`.
- O ZIP foi transferido ao Deck e o prompt oficial do Decky aceitou versão/hash.
- Após a instalação, o probe encontrou `plugin_version: null` e o diretório `/home/deck/homebrew/plugins/TrainerRelay` continuava ausente. Portanto, a `.37` não foi considerada instalada/carregada.
- O motivo dessa não-aparição não foi investigado até o fim porque a investigação foi encerrada a pedido do usuário.

## Diagnóstico técnico alcançado

### Demonstrado localmente

- A raiz de compatdata usada pelo UMU e o prefixo Wine observado (`.../pfx`) são contratos diferentes. O runner antigo podia entregar a raiz ao Wine direto.
- `--directory=` vazio fazia o launch-client herdar o diretório do serviço, em vez de usar explicitamente o diretório do trainer.
- Sanitizar o ambiente externo não garantia um ambiente limpo na fronteira interna do launch-client.
- O avaliador antigo classificava uma saída real aos poucos segundos como `INVALID/stability_window_incomplete`, ocultando um `FAIL` verdadeiro.
- Antes da `.36`, a telemetria podia marcar reentrada antes de existir confirmação produzida dentro do contêiner.

### Não demonstrado

- Que o prefixo raiz incorreto foi a causa do encerramento físico.
- Que Wine Mono, sozinho, matou o jogo. A asserção `gpath.c:115` apareceu no trainer, mas não identifica o causador do encerramento do jogo.
- Que Steam, gamescope, wineserver ou um reaper externo foram responsáveis; os logs disponíveis não identificaram o emissor.
- Que aumentar atraso, instalar .NET/Winetricks, trocar Proton ou alterar Mono global resolveria o caso.
- Que o problema de coordenadas e o encerramento do jogo têm a mesma causa.

## Alterações locais desta última fase

Foi aplicada uma correção TDD local, sem concluir validação física:

- avaliador de sessão: saída válida e vinculada passou a ser `FAIL` mesmo antes de 60 s;
- runner: prefixo observado separado da raiz UMU;
- runner: ambiente interno usa `env -i` com conjunto explícito;
- runner: `--directory` aponta para o diretório do trainer;
- perfil de runtime: diretórios multiarch opcionais foram considerados;
- coletor sanitizado de sessão `/proc`, prefixo, identidade e módulos carregados;
- testes para identidade, redaction de ambiente, prefixo, watcher e avaliador;
- versão local incrementada para `.37`.

Essas alterações ainda estão no working tree junto com alterações anteriores do projeto. Não usar `git reset --hard`, `git restore` amplo ou staging global.

## Validação local

- Avaliador: 11/11 testes passaram.
- Runner/watcher: 81/81 testes passaram no foco executado.
- Backend focado após os contratos novos: 107 testes passaram.
- Coletor sanitizado: 3/3 testes passaram.
- Packaging: 8/8 testes passaram.
- `python -m compileall trainer_relay tools\diagnostics`: passou.
- Empacotador Python direto gerou o ZIP `.37` com o hash acima.
- `pnpm run package` não foi usado como prova de falha do código: o launcher foi bloqueado porque não conseguiu verificar a assinatura do pacote `pnpm@11.5.0` no registry.

Validação física final: incompleta/RED. Não há evidência suficiente para declarar “corrigido”.

## Estado seguro para encerramento

- Não reativar Force Compatibility.
- Não alterar Proton global, Mono global, prefixo real ou UniFiDeck para tentar mais uma vez.
- Não assumir que a `.37` está instalada: o último probe não encontrou o plugin carregado.
- Não executar novos ensaios cegos nem clicar repetidamente em toggles sem primeiro resolver a instalação/observabilidade.
- O rollback da tentativa `.37` foi criado em `/home/deck/Downloads/TrainerRelay-rollback-20260907-37/`; as configurações foram copiadas para esse diretório.
- O working tree local está deliberadamente sujo. As alterações de produto, testes e documentos anteriores pertencem ao histórico de investigação e não foram descartadas.

## Retomada futura, se desejada

1. Começar pelo motivo do Decky não ter deixado a `.37` carregada; não testar jogo/trainer antes disso.
2. Usar o avaliador novo e o coletor sanitizado para distinguir saída do jogo, saída do trainer e perda de observação.
3. Revalidar A0 (jogo original sem sidecar) antes de qualquer reentrada.
4. Comparar uma única diferença por vez: ambiente/prefixo, launch-client, runtime privado, Mono e FLiNG.
5. Só depois de estabilidade: seletor Steam, janela visível, foco/coordenadas, clique físico, toggle ON/OFF, efeito real e regressão GOG.

## GitHub e arquivos

- Branch: `feat/trainer-relay`.
- HEAD observado: `a418003`, sincronizado com `origin/feat/trainer-relay` antes deste relatório.
- Commits documentais anteriores relevantes: `fb4b503` e `a418003`.
- O relatório atual e o handoff atualizado devem ser os únicos documentos novos deste encerramento; nenhum código deve ser promovido como release.

## Conclusão

O problema permanece aberto. A pesquisa reduziu o espaço de hipóteses e corrigiu contratos locais demonstrados, mas não produziu uma versão física estável. A última evidência confiável é: o FLiNG pode funcionar manualmente no Deck; a integração automática ainda encerra o jogo ou perde a sessão; cliques físicos não estão validados; e a instalação `.37` não foi confirmada como carregada.
