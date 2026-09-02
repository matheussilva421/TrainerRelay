# Automação de menu radial do Steam Input para cheats

Data: 2026-09-02

## Pergunta

O Trainer Relay pode criar automaticamente, para um atalho Epic/GOG do
UniFiDeck, um menu radial do Steam Input como o configurado manualmente pelo
usuário, preenchendo cada item com o nome e a tecla de um cheat?

## Resposta curta

É tecnicamente possível construir uma integração **experimental**, porém não
existe uma API pública e suportada para um plugin Decky alterar diretamente o
layout pessoal ativo do Steam Input. A solução mais segura é manter os controles
dinâmicos do próprio Trainer Relay como rota principal e, opcionalmente, gerar
um layout separado para o usuário revisar e aplicar no configurador normal do
Steam. Aplicação automática por interfaces internas deve ser opt-in, manter
backup/rollback e falhar fechada.

## Evidência primária

### Contrato público da Valve

A documentação oficial permite que desenvolvedores Steamworks criem arquivos de
ações/configurações, exportem um layout no modo de desenvolvimento, descarreguem
uma configuração por `steam://dumpcontrollerconfig?appid=...` e empacotem a
configuração no depot do jogo. Esse fluxo pressupõe integração do jogo e acesso
de desenvolvedor; ele não documenta uma operação para um plugin externo mutar o
layout pessoal de um atalho não-Steam:

- [Valve: Action Manifest Files](https://partner.steamgames.com/doc/features/steam_controller/action_manifest_file)
- [Valve: In-Game Actions File](https://partner.steamgames.com/doc/features/steam_controller/iga_file)

A própria documentação recomenda não forçar usuários que já criaram layouts a
reconstruí-los quando a configuração muda. Isso sustenta uma política de
preservação e confirmação, não sobrescrita silenciosa.

### Superfície interna visível ao Decky

Os tipos mantidos pelo projeto oficial do Decky expõem interfaces internas do
cliente Steam capazes de:

- iniciar/parar edição de uma configuração;
- alterar action sets, activators, bindings, source modes e misc settings;
- salvar/exportar a configuração editada;
- selecionar uma configuração para um AppID/controlador;
- abrir o configurador normal do Steam.

Fonte: [SteamDeckHomebrew/decky-frontend-lib, `Input.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/globals/steam-client/Input.ts)
e [`App.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/globals/steam-client/App.ts).

Essa superfície não é um contrato público da Valve. Muitos parâmetros estão
tipados como `any`, os payloads de edição são protobufs internos, e o próprio
arquivo adverte que registrar determinada mensagem de configuração pode quebrar
a seleção de layouts. Portanto, uma atualização do cliente Steam pode alterar o
schema, os métodos ou o ciclo de salvamento sem compatibilidade.

### Precedente em atalhos não-Steam

O plugin [Decky Metadata](https://github.com/beallio/Decky-Metadata) demonstra que
é possível estender a UI do Steam para mostrar, em um atalho não-Steam, layouts
oficiais/comunitários associados ao AppID Steam equivalente. O usuário ainda
visualiza e escolhe o layout pelos controles normais do Steam. Isso é precedente
para **descobrir/oferecer** layouts, não prova uma API estável para fabricar e
sobrescrever um menu radial pessoal.

## Alternativas

### 1. Controles dinâmicos no Quick Access do Trainer Relay — recomendada

O plugin já descobre os cheats/hotkeys por adapter ou fallback manual. Pode
mostrar botões controller-first no Quick Access e enviar a hotkey pelo helper
Win32 efêmero. Não toca no layout do jogo, funciona com quantidade variável de
cheats e permanece independente do schema privado do Steam Input.

Limite: abre-se o painel do Trainer Relay em vez do menu radial do Steam.

### 2. Gerar um layout Steam Input separado e abrir o configurador — viável

O plugin geraria um VDF de layout chamado, por exemplo, `Trainer Relay — <jogo>`,
com um menu radial e um item por hotkey. Em seguida abriria o configurador para o
AppID correto. O usuário revisaria e aplicaria o layout uma vez.

Requisitos de segurança:

- nunca modificar o layout ativo in-place;
- vincular a geração a `AppID + LaunchIdentity + trainer SHA-256`;
- limitar e validar labels, teclas e número de itens;
- preservar/exportar a configuração anterior;
- exibir diff/resumo antes da aplicação;
- oferecer rollback explícito;
- regenerar quando o hash ou catálogo mudar, sem aplicar silenciosamente.

Risco: ainda depende do formato VDF aceito pelo cliente e precisa de validação
física por versão do SteamOS/Steam Client.

### 3. Gerar e aplicar automaticamente via APIs internas — possível, experimental

O frontend poderia usar `SteamClient.Input` para iniciar a edição, construir os
payloads protobuf de bindings/menu radial, salvar e selecionar a nova
configuração. É a experiência de um clique mais próxima da pergunta.

Riscos:

- APIs e protobufs privados/instáveis;
- possibilidade de corromper ou substituir um layout pessoal;
- conflitos com sincronização do Steam Cloud;
- identidade variável de controlador e de AppID de atalho não-Steam;
- necessidade de testes físicos e adaptadores por versão do cliente;
- manutenção frequente após atualizações do Steam.

Esta opção só é aceitável atrás de uma flag `experimental`, com feature probe,
backup verificável, confirmação humana e rollback automático. Se qualquer etapa
não puder ser comprovada, o plugin deve apenas abrir o configurador.

### 4. Editar diretamente arquivos ativos do Steam — não recomendada

Editar arquivos do usuário enquanto o Steam está executando disputa com o estado
em memória e com a sincronização de configurações. O formato/localização pode
variar por controlador, conta, AppID e versão. Mesmo com backup, não há uma API
oficial de commit/reload para esse fluxo. Deve permanecer fora do contrato do
Trainer Relay.

## Recomendação

Implementar em duas fases:

1. **Atalho assistido seguro:** botão `Criar menu radial no Steam Input`, que
   gera uma nova configuração a partir dos cheats atuais e abre o configurador
   do AppID correto para revisão/aplicação manual. Nunca substitui o layout atual.
2. **Aplicação automática experimental**, somente depois de capturar no Deck os
   payloads e lifecycle reais para o mesmo cliente Steam, com backup, rollback,
   feature detection e teste de atualização/cloud sync.

O menu dinâmico do próprio Trainer Relay continua sendo a rota principal e mais
resiliente. O menu radial gerado é uma conveniência opcional; ele não substitui o
catálogo/hotkey authority do plugin e não deve prometer estado real do cheat.

## Validação necessária no Deck

- AppID do atalho UniFiDeck permanece estável entre reinícios e Force Sync;
- layout gerado aparece apenas no jogo correto;
- layout existente não é alterado antes da confirmação;
- radial envia NumLock/Numpad/F-keys corretamente com jogo em foco;
- Steam Cloud não restaura/sobrescreve inesperadamente a seleção;
- rollback restaura exatamente o layout anterior;
- atualização do cliente Steam causa fallback para `Abrir configurador`, não
  tentativa cega de editar payload interno.
