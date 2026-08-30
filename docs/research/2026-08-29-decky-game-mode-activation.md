# Ativação de controles em rotas Decky no Game Mode

Data: 2026-08-29
Escopo: investigação somente documental; nenhuma alteração de produção ou de testes foi feita por esta pesquisa.

## Conclusão executiva

**Fato confirmado:** no contrato atual de `@decky/ui`, foco de navegação e ativação são capacidades separadas. `DialogButton` documenta que `disabled` impede a invocação dos handlers, enquanto `focusable` controla se o elemento pode ser alcançado pela navegação de gamepad/teclado. Portanto, “o controle recebe foco, mas A não faz nada” é compatível com um `DialogButton` desabilitado; foco visual não prova que `onClick` será chamado. [Contrato de `DialogButton`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Dialog.ts#L10-L31)

**Fato confirmado:** `ButtonItem` é o padrão usado pelo template oficial para uma linha de ação nativa no painel: ele recebe `onClick` diretamente e não é colocado dentro de um `Field`/`Focusable` adicional. [Template oficial, `src/index.tsx`](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/src/index.tsx#L28-L44)
**Fato confirmado:** o CheatDeck atual usa esse mesmo padrão para sua ação simples de adicionar (`ButtonItem`) e usa `ToggleFilePicker` com `ToggleField` + `Field` + `Focusable` + `DialogButton` apenas para o botão secundário de abrir o seletor depois que o toggle está ativo. [CheatDeck, `AddOptionButton.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/AddOptionButton.tsx#L1-L19), [CheatDeck, `ToggleFilePicker.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/ToggleFilePicker.tsx#L1-L102)

**Inferência aplicada ao TrainerRelay:** para a ação primária “Choose trainer”, uma linha única com `ButtonItem` é a forma mais direta e menos ambígua de reproduzir a ação nativa do CheatDeck. O `DialogButton` aninhado não é intrinsecamente inválido — ele é usado pelo CheatDeck —, mas sua ativação depende de duas camadas de foco (`Focusable` externo e interno) e de o botão não estar `disabled`. Se a intenção é que A ative a linha atualmente focada, `ButtonItem` deve ser preferido; se o layout exige o campo de caminho e um ícone separado, o `DialogButton` deve continuar habilitado e a árvore deve seguir exatamente o padrão do CheatDeck. [Contrato de `ButtonItem`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/ButtonItem.ts#L1-L10), [contrato de `Focusable`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Focusable.ts#L1-L18)

## Contratos primários do Decky

### Rotas e ciclo de foco

**Fato confirmado:** `routerHook.addRoute` registra uma rota React com um componente e props de `react-router`; o loader injeta as rotas registradas no array de rotas do Gamepad UI. [Tipagem oficial do loader API](https://github.com/SteamDeckHomebrew/loader-api/blob/main/src/types.ts#L1-L11), [implementação do `RouterHook`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/router-hook.tsx#L259-L315)

**Fato confirmado:** no Game Mode, o Decky Loader espera o modo `EUIMode.GamePad`, localiza o router React do Steam UI, envolve a árvore com `DeckyGamepadRouterWrapper` e injeta as rotas registradas como componentes `Route` dentro de `ErrorBoundary`. [Loader, patch do router Gamepad](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/router-hook.tsx#L69-L118), [Loader, wrapper e `processList`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/router-hook.tsx#L196-L235), [Loader, criação das rotas](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/router-hook.tsx#L259-L307)

**Fato confirmado:** `SidebarNavigation` recebe uma lista de páginas com `title`, `content`, `icon` e `hideTitle`, além de props de navegação como `page` e `onPageRequested`. A tipagem não afirma que ele converte qualquer descendente arbitrário em uma ação ativável; o conteúdo continua responsável por fornecer os elementos focáveis/ativáveis. [Contrato de `SidebarNavigation`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/SidebarNavigation.ts#L5-L28)

**Fato confirmado:** `Focusable` é um contêiner do sistema de navegação; seu contrato expõe `onActivate`, `onCancel`, preferências de entrada (`navEntryPreferPosition`, `preferredFocus`) e callbacks de gamepad (`onOKButton`, `onButtonDown`, `onGamepadFocus`, etc.) via `FooterLegendProps`. [Contrato de `Focusable`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Focusable.ts#L5-L18), [contrato de `FooterLegendProps`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/FooterLegend.ts#L1-L7)

**Inferência:** `Focusable` sozinho não transforma necessariamente um `onClick` React de um descendente em uma ativação funcional. Ele fornece o host de foco e os callbacks de gamepad; a ação concreta deve ser uma ação SteamUI reconhecida (`ButtonItem`, `DialogButton`, `Field` focável ou um `onActivate`/`onOKButton` explicitamente tratado). Esta é uma inferência do contrato tipado: o arquivo não promete propagação automática de `A` para todo `onClick` descendente. [Contrato de `Focusable`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Focusable.ts#L5-L18), [contrato de eventos de gamepad](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/FooterLegend.ts#L3-L7)

### `disabled`, foco e ativação

**Fato confirmado:** `DialogButtonProps.disabled` diz que os métodos `on*` atribuídos não serão invocados quando clicado. A mesma definição alerta que, dependendo do contexto, um botão desabilitado ainda pode receber foco. [Contrato de `DialogButton`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Dialog.ts#L10-L22)

**Fato confirmado:** `DialogButtonProps.focusable` é independente de `disabled`: ele controla a navegação baseada em foco; com `focusable={false}`, o botão não é alcançável por gamepad/teclado, embora ainda possa ser clicado e focado até ser navegado para longe. [Contrato de `DialogButton`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Dialog.ts#L10-L22)

**Fato confirmado:** `ButtonItemProps` herda `ItemProps` e declara `onClick` e `disabled`; `ItemProps` fornece `highlightOnFocus`, mas não declara um callback de gamepad adicional. [Contrato de `ButtonItem`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/ButtonItem.ts#L1-L10), [contrato de `ItemProps`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Item.ts#L1-L14)

**Fato confirmado:** `FieldProps` também possui `disabled`, `focusable`, `onActivate` e `onClick`. Assim, `Field` pode ser uma entrada focável sem filhos ativáveis, mas `Field` e `DialogButton` continuam sendo contratos diferentes. [Contrato de `Field`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Field.ts#L1-L1)

**Fato confirmado:** `ToggleField` declara `checked`, `disabled` e `onChange`; o CheatDeck passa `highlightOnFocus` e `disabled` diretamente ao `ToggleField`. [Contrato de `ToggleField`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/ToggleField.ts#L1-L1), [CheatDeck, `Normal.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/Normal.tsx#L34-L56)

## Padrão funcional do CheatDeck

**Fato confirmado:** a rota do CheatDeck é registrada com `routerHook.addRoute("/cheatdeck/:appid", PageRouter, { exact: true })` e removida no `onDismount`. [CheatDeck, `src/index.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/index.tsx#L9-L25)

**Fato confirmado:** `PageRouter` envolve o conteúdo em `SettingsProvider` e `OptionsProvider`, monta `SidebarNavigation` e passa cada página como `content`, com `hideTitle: false`. [CheatDeck, `PageRouter.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/PageRouter.tsx#L14-L49)

**Fato confirmado:** cada página funcional (`Normal`, `Advanced`, `Custom`) retorna um `Focusable` vertical como raiz. A rota não coloca `PanelSection`/`PanelSectionRow` ao redor do conteúdo de Game Mode. [CheatDeck, `Normal.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/Normal.tsx#L34-L84), [CheatDeck, `Advanced.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/Advanced.tsx#L38-L92), [CheatDeck, `Custom.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/Custom.tsx#L50-L91)

**Fato confirmado:** o picker do CheatDeck segue esta estrutura: `ToggleField` nativo; quando ativo, `Focusable` externo; `Field` com `childrenLayout="below"`; `Focusable` interno para a linha; `TextField disabled={true}`; e `DialogButton disabled={disabled} onClick={onBrowse}`. [CheatDeck, `ToggleFilePicker.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/ToggleFilePicker.tsx#L55-L101)

**Fato confirmado:** ações de linha simples do CheatDeck usam `ButtonItem` diretamente. `AddOptionButton` não envolve a ação em `Field`, `PanelSectionRow` ou `DialogButton`; ele passa `onClick` diretamente ao `ButtonItem`. [CheatDeck, `AddOptionButton.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/AddOptionButton.tsx#L1-L19)

**Fato confirmado:** o CheatDeck atual e as tags locais inspecionadas (`v0.5.1`, `v1.0.0`, `v1.1.6`, `v1.2.1`, `v2.0.0`) mantêm o mesmo desenho arquitetural: `SidebarNavigation` na rota, `Focusable` na página e controles nativos diretamente abaixo. Os hashes/tags locais pertencem ao clone upstream presente no worktree e foram usados para verificar a continuidade histórica; a implementação atual é também visível nos links `main` acima. [Histórico local do CheatDeck](../../.git), [CheatDeck `PageRouter.tsx` em `main`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/PageRouter.tsx)

## Comparação com TrainerRelay

### Estado rastreado no HEAD `.10`

**Fato confirmado:** `TrainerRelay` registra `/trainer-relay/:appid` com `routerHook.addRoute(..., { exact: true })` e remove a rota no `onDismount`, o mesmo contrato básico do CheatDeck. [TrainerRelay, `src/index.tsx`](../../src/index.tsx), [CheatDeck, `src/index.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/index.tsx#L9-L25)

**Fato confirmado:** `PageRouter` no HEAD `.10` retorna um `SidebarNavigation` de uma página, com `showTitle={true}`, `hideTitle: false` e `RelayPage` como `content`. Isso corresponde estruturalmente ao padrão de rota do CheatDeck. [TrainerRelay, `src/views/PageRouter.tsx`](../../src/views/PageRouter.tsx), [CheatDeck, `PageRouter.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/PageRouter.tsx#L19-L49)

**Fato confirmado:** no HEAD `.10`, `RelayPage` retorna um `Focusable` vertical como raiz dos estados `loading`, `error`, `unsupported` e `supported`; os `PanelSection`/`PanelSectionRow` que existiam antes da correção `.9` não estão mais no conteúdo roteado. [TrainerRelay, `src/views/RelayPage.tsx`](../../src/views/RelayPage.tsx), [mudança local `.8` → `.9`](../../.git)

**Fato confirmado:** no HEAD `.10`, `TrainerFilePicker` usa um `Focusable` externo, `Field`, `Focusable` interno, `TextField disabled={true}` e `DialogButton disabled={disabled} onClick={handleBrowse}`. Esta forma é semanticamente equivalente ao picker do CheatDeck, inclusive no ponto crítico de `disabled`. [TrainerRelay, `src/components/TrainerFilePicker.tsx`](../../src/components/TrainerFilePicker.tsx), [CheatDeck, `ToggleFilePicker.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/ToggleFilePicker.tsx#L55-L101), [HEAD `.10`, commit `bf6703f`](https://github.com/matheussilva421/TrainerRelay/blob/bf6703f/src/components/TrainerFilePicker.tsx)

**Fato confirmado:** no HEAD `.10`, a expressão `configurationDisabled` cobre apenas `busy`, `migrationBusy` e erro de configuração; a migração legada não desabilita mais o picker. O `ToggleField` continua condicionado a `model.controls.enable`, preservando o bloqueio de enablement. [TrainerRelay, `RelayPage.tsx`](../../src/views/RelayPage.tsx), [TrainerRelay, `viewModel.ts`](../../src/domain/relay/viewModel.ts), [TrainerRelay, `relayActions.ts`](../../src/hooks/relayActions.ts)

**Inferência:** antes da correção `.10`, a combinação de `model.migration.status !== "none"` em `controlsDisabled` e `DialogButton disabled={controlsDisabled}` explicava diretamente o sintoma reportado: SteamUI podia focar visualmente o botão, mas o contrato do `DialogButton` impedia `onClick`; por isso o log `ui-activated` não aparecia. [Diff local `.9` → `.10`](../../.git), [contrato de `DialogButton`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Dialog.ts#L10-L22)

### Variante não commitada observada durante a pesquisa

**Fato confirmado:** enquanto este relatório era preparado, outro agente modificou, sem commit, `src/components/TrainerFilePicker.tsx` para substituir o layout aninhado por um único `ButtonItem` com `label`, descrição, `highlightOnFocus`, `disabled` e `onClick={handleBrowse}`. O teste correspondente também foi alterado; essas mudanças não foram feitas por esta pesquisa e foram preservadas. [Estado local, `TrainerFilePicker.tsx`](../../src/components/TrainerFilePicker.tsx), [estado Git do worktree](../../.git)

**Inferência:** essa variante reduz a árvore de foco e alinha a ação “Choose trainer” ao padrão de ação simples do template/CheatDeck (`ButtonItem`). Ela é uma hipótese de correção plausível para a ativação por A, mas a presença de `ButtonItem` por si só não prova sucesso no dispositivo: se `disabled` permanecer verdadeiro, o contrato ainda bloqueia `onClick`, e a confirmação final precisa ser física no Game Mode. [Template oficial](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/src/index.tsx#L28-L44), [CheatDeck, `AddOptionButton.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/AddOptionButton.tsx#L1-L19), [contrato de `ButtonItem`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/ButtonItem.ts#L1-L10)

## Diferenças materiais encontradas

| Área | CheatDeck funcional | TrainerRelay HEAD `.10` | Avaliação |
|---|---|---|---|
| Registro da rota | `routerHook.addRoute`, rota exata, remoção no desmonte | Igual | Não é a causa provável. |
| Host da rota | `SidebarNavigation` | `SidebarNavigation` de uma página | Estruturalmente alinhado desde `.9`. |
| Raiz da página | `Focusable` vertical | `Focusable` vertical | Alinhado desde `.9`. |
| Wrappers de Quick Access | Ausentes nas páginas roteadas | Ausentes no HEAD `.10` | Alinhado desde `.9`; a versão `.8` diferia. |
| Ação simples | `ButtonItem` direto (`AddOptionButton`) | HEAD: `DialogButton` dentro de dois `Focusable` e `Field`; variante não commitada: `ButtonItem` direto | Diferença material de simplicidade/árvore de foco; `ButtonItem` é a hipótese mais direta para uma ação primária. |
| Picker composto | `DialogButton` dentro do `ToggleFilePicker` | HEAD: mesma forma; variante: substituída por `ButtonItem` | A forma aninhada é oficialmente usada, mas é sensível a `disabled` e à árvore de foco. |
| `disabled` | CheatDeck passa `disabled` quando opções não são editáveis | HEAD `.10`: picker habilitado para configuração segura; toggle permanece bloqueado quando necessário | A correção de `.10` removeu o bloqueio excessivo. |
| Callbacks explícitos de gamepad | Nenhum no picker; controles nativos recebem o contrato SteamUI | Nenhum no picker | Não há evidência primária de que adicionar `onOKButton` seja necessário para `ButtonItem`/`DialogButton`. |
| Patch de app page | Nenhum no CheatDeck | Nenhum no TrainerRelay | Não há diferença material encontrada nessa área. |

## Resposta direta à pergunta causal

1. **A rota:** a diferença antiga era material: TrainerRelay `.8` misturava `PanelSection`/`PanelSectionRow` em uma página roteada e não tinha o mesmo host de `SidebarNavigation` do CheatDeck. Isso foi corrigido em `.9`; no `.10`, a rota já corresponde ao padrão funcional.
2. **O foco:** estar focado significa que a navegação encontrou o elemento; não significa que o handler será invocado.
3. **A ativação:** o contrato primário mais forte é `disabled`: `DialogButton` pode receber foco mesmo desabilitado, mas seus handlers não são chamados. Esse foi o mecanismo causal mais bem sustentado para o sintoma pós-`.9`.
4. **`ButtonItem` versus `DialogButton` aninhado:** `ButtonItem` é preferível para uma ação primária de linha única e reduz a profundidade da árvore. O layout aninhado de `DialogButton` é um padrão legítimo e usado pelo CheatDeck para picker composto; ele não deve ser considerado defeituoso por si só. Em ambos os casos, `disabled` deve ser falso no momento em que o usuário pressiona A.
5. **Limite da evidência:** os fontes tipados explicam o contrato, mas não substituem a confirmação no Steam Deck. A prova final é observar, em Game Mode, o evento `ui-activated` e a abertura do picker após pressionar A com o controle habilitado.

## Fontes primárias consultadas

- [Decky Loader — `router-hook.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/router-hook.tsx)
- [Decky Loader — `plugin-loader.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/plugin-loader.tsx)
- [Decky Loader — `PluginView.tsx`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/frontend/src/components/PluginView.tsx)
- [Decky loader API — `types.ts`](https://github.com/SteamDeckHomebrew/loader-api/blob/main/src/types.ts)
- [`@decky/ui` — `Dialog.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Dialog.ts)
- [`@decky/ui` — `ButtonItem.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/ButtonItem.ts)
- [`@decky/ui` — `Field.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Field.ts)
- [`@decky/ui` — `Focusable.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/Focusable.ts)
- [`@decky/ui` — `FooterLegend.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/FooterLegend.ts)
- [`@decky/ui` — `SidebarNavigation.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/SidebarNavigation.ts)
- [`@decky/ui` — `ToggleField.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/ToggleField.ts)
- [`@decky/ui` — `TextField.ts`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/src/components/TextField.ts)
- [`@decky/ui` — `CHANGELOG.md`](https://github.com/SteamDeckHomebrew/decky-frontend-lib/blob/main/CHANGELOG.md)
- [Template oficial — `src/index.tsx`](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/src/index.tsx)
- [CheatDeck — `src/index.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/index.tsx)
- [CheatDeck — `PageRouter.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/PageRouter.tsx)
- [CheatDeck — `Normal.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/views/Normal.tsx)
- [CheatDeck — `ToggleFilePicker.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/ToggleFilePicker.tsx)
- [CheatDeck — `AddOptionButton.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/AddOptionButton.tsx)
- [CheatDeck — `CustomOptionItem.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/components/CustomOptionItem.tsx)
- [CheatDeck — `patch.tsx`](https://github.com/SheffeyG/CheatDeck/blob/main/src/patch.tsx)
