# Evidência do teste de processo preexistente

## Conclusão

O novo teste não demonstra temporalidade. Ele expressa a expectativa de rejeitar um processo que existia antes do relay, mas não modela o instante de spawn do relay, um limite temporal ou uma identidade observada antes desse limite. O fixture apenas cria `SessionIdentity(31304, 9001)` e injeta um `verify_process` que retorna essa mesma identidade para qualquer chamada (`tests_backend/test_window_probe.py:113-125`).

Na implementação, qualquer retorno não nulo do verificador é inicialmente aceito como janela pertencente (`trainer_relay/window_probe.py:155-163`). A mesma identidade mockada também passa a revalidação imediatamente antes da escrita (`trainer_relay/window_probe.py:182-200`). Portanto, a falha observada — 1 teste executado, 1 falha, com uma escrita registrada — prova somente que o caminho de associação não rejeita uma identidade aprovada pelo mock. Não prova que um processo real foi comparado temporalmente com o spawn do relay.

## O que falta

`SessionIdentity` carrega apenas `pid` e `start_time` (`trainer_relay/process.py:15-18`). O verificador real confirma estabilidade do `start_time` e, quando fornecida, igualdade com uma identidade esperada (`trainer_relay/process.py:108-131`), mas `associate_owned_windows` não recebe nem calcula um instante de spawn (`trainer_relay/window_probe.py:97-107`). Para demonstrar temporalidade seria necessário um limite de spawn observável e um caso controlado com processo anterior rejeitado e processo posterior aceito.

## Por que não prova visibilidade Epic

O teste usa janelas e propriedades X11 sintéticas, principalmente `_NET_WM_PID`, e verifica apenas se uma escrita `STEAM_GAME` ocorreria (`tests_backend/test_window_probe.py:117-128`; `trainer_relay/window_probe.py:155-163`, `196-225`). O código não observa o launcher Epic, a UI do Steam, a seleção no alternador de janelas ou a permanência visual da janela. Mesmo o snapshot separado apenas coleta propriedades X11, incluindo estado/ocultação quando disponíveis (`trainer_relay/window_probe.py:242-303`). Assim, não há evidência local de visibilidade Epic; isso exige validação runtime/visual independente.

## Bloqueio

O Deck está novamente inacessível. A validação runtime/visual independente não pode ser executada nesta sessão; a conclusão fica limitada às evidências locais acima.
