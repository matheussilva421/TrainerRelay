# Running lifecycle — pesquisa local

## Conclusão

No `.22/current`, `trainer_running` não é um heartbeat do executável Windows
real. Em `trainer_relay/runner.py`, `spawn()` cria um `Popen` para
`umu-run <trainer>` e guarda esse processo externo; `poll()` consulta somente
`handle.process.poll()` ([runner.py](../../trainer_relay/runner.py#L281-L364)).
Os descendentes são apenas nomes coletados para diagnóstico, não uma condição
de vida.

Em `trainer_relay/watcher.py`, depois da confirmação textual de reentrada, o
watcher passa a `running` quando o `poll()` externo ainda retorna `None` e o
tempo mínimo de três segundos foi atingido ([watcher.py](../../trainer_relay/watcher.py#L758-L837), [watcher.py](../../trainer_relay/watcher.py#L922-L937)). Portanto, se o trainer Windows desaparecer enquanto `umu-run`/a camada
de reentrada continuar viva, o estado pode permanecer `trainer_running` até o
processo externo terminar ou até a sessão do jogo ser perdida. Não há, nessa
transição, revalidação do PID/start-time do trainer, da janela ou de um
descendente vivo.

## O que `trainer_exited` prova

`trainer_exited` é emitido somente quando `runner.poll()` deixa de retornar
`None`; seu `exit_code` e `elapsed_ms` descrevem o término observado do
processo externo guardado pelo `RunnerHandle` ([watcher.py](../../trainer_relay/watcher.py#L938-L980)). Isso prova que a invocação monitorada de `umu-run` terminou; não prova, isoladamente, que o executável Windows real acabou naquele instante, nem que estava vivo antes do término. `umu_exit_diagnostics` e os nomes de grupo/descendentes são evidência auxiliar limitada, não uma prova de liveness.

## Limite da evidência atual

Após o reboot, o jogo `PID 24119` foi rejeitado por
`container_reentry_missing`. Não houve `trainer_spawned` após
`plugin_loaded` às 10:37. A janela sem nome observada é
`EOSOverlayRenderer CrBrowserMain`, `PID 24251`. Logo, esta pesquisa de
lifecycle não explica a sessão atual: ela não alcançou o caminho que poderia
produzir `trainer_running`/`trainer_exited`.

## Estado de retomada

- Escopo somente local; nenhuma alteração de produção, SSH, credencial ou
  anexos foi feita.
- Teste pendente preservado: `tests_backend/test_window_probe.py` já estava
  modificado e não foi executado, editado ou staged.
- Nenhum teste foi executado nesta pesquisa; nenhum commit ou push foi feito.
- Para uma sessão futura com `trainer_spawned`, correlacionar o PID/start-time
  real do trainer com o handle externo antes de atribuir significado a
  `trainer_running` ou `trainer_exited`.
