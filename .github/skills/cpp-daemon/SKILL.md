---
name: cpp-daemon
description: |
  Procedimento para o daemon uk-pi0: estrutura de processo, laço epoll, threads (captura/render), tratamento de sinais com release-all, systemd com watchdog, privilégio mínimo e persistência de perfil.
  Triggers: "daemon", "uk-pi0", "systemd", "epoll", "thread", "render thread", "SIGTERM", "watchdog", "sd_notify", "privilégio", "capabilities", "perfil persistido", "RAII", "C++".
  NOT for: C de MCU (use embedded-c), HID descritores (use hid-gadget).
---

# Daemon uk-pi0 — procedimento

## Responsabilidades

1. Ler eventos do link serial (thread de captura).
2. Manter estado: layout ativo, camada, modificadores, macros.
3. Traduzir evento → relatório HID e enviar ao host.
4. Marcar teclas sujas e alimentar a thread de render.
5. Receber comandos do `uk-gui` pela interface vendor.
6. Supervisionar o link (heartbeat) e entrar em `SAFE` quando perder.
7. Persistir perfil por fingerprint de host.

## Estrutura de processo

```text
main
├── parse argv / config (/etc/uk/config.toml)
├── instalar handlers de sinal (antes de qualquer thread)
├── init: link, display driver, hid gadget
├── sd_notify(READY=1)
├── threads
│   ├── capture  (epoll no serial + vendor interface)
│   └── render   (fila de teclas sujas)
└── loop principal: watchdog + supervisao
```

- Handlers de sinal instalados **antes** de criar threads.
- Se o daemon não é single-threaded, use `signalfd` em vez de handler: evita corrida.
- Nenhuma thread faz `fork`/`exec`.

## Laço e tempo

- `epoll_wait` com timeout máximo (`UK_TICK_MAX_MS`, ex.: 50 ms). Nunca `-1` cego.
- Todo timeout é derivado do heartbeat; nada de constante solta sem nome.
- `WATCHDOG=1` enviado do laço principal. Se o laço travar, systemd reinicia — e o
  `ExecStopPost`/init garante release-all.

## Sinais e encerramento

```text
SIGTERM/SIGINT ->
  1. parar de aceitar novos eventos
  2. release_all_keys() no hidg
  3. sd_notify(STOPPING=1)
  4. flush de perfil se houver alteracao pendente
  5. stop nas threads, join com timeout
  6. exit 0
```

- Timeout no join: se a thread de render não parar, sai mesmo assim (é degradação, não
  bloqueio).
- Nunca `_exit` antes do release.

## Privilégio

- Unit com `User=uk` e capabilities específicas para `hidg`/`uinput` quando possível.
- Se precisar de `root` para criar o gadget, faça a criação num helper separado e rode o
  daemon sem privilégio.
- `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`,
  `ReadWritePaths=/var/lib/uk`.
- Nunca `chmod 777` em `/dev/hidg*`.

## Estado e persistência

- Config em `/etc/uk/`, estado em `/var/lib/uk/`.
- Perfil salvo por fingerprint de host; escrita atômica (tmp + `rename`).
- Nunca perder o perfil por crash: escrita atômica e um arquivo `.bak`.
- Layout persistido é o fallback quando o `uk-gui` não está presente.

## Observabilidade

Exponha, via `GET_STATS` e journald:

- frames descartados (CRC, tamanho, timeout);
- profundidade da fila de render e teclas sujas pendentes;
- duração do ciclo de render (p50/p99 aproximado);
- taxa de barramento medida;
- reconexões do gadget e do link serial.

## Teste

- Teste host com fakes de `hidg`, serial e display driver.
- Teste de sinal: enviar `SIGTERM` e verificar que `release_all` foi chamado e que o relatório
  enviado tem modificadores zerados.
- Teste de perda de link: parar heartbeat e verificar transição para `SAFE`.

## Não faça

- Bloquear o laço principal em I/O de render.
- Segurar mutex durante `write` no hidg.
- `volatile` como sincronização.
- Alocar no caminho de evento.
- Depender do `uk-gui` para digitar.
