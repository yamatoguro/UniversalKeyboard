---
description: 'Regras para C++ do daemon uk-pi0: RAII, ownership, tratamento de sinais, systemd, USB HID gadget e limites de tempo real.'
applyTo: '**/*.{cpp,cc,cxx,hpp,hxx,ipp}'
---

# C++ — daemon e adaptadores

Padrão **C++17** (sem C++20/23 até o toolchain do Raspberry Pi OS estar confirmado).
Contexto: processo privilegiado, longevo, sem supervisão humana, no caminho de digitação.

## Ownership e recursos

- **RAII sempre.** Sem `new`/`delete` manual; `std::unique_ptr`/`std::shared_ptr`.
- Recurso de sistema (fd, socket, timer, thread) envolto em tipo com destrutor.
- Regra 0/3/5: prefira não declarar destrutor; se declarar, trate cópia/movimento.
- `shared_ptr` só quando o compartilhamento é real; sem ciclo.
- Sem alocação no caminho de evento: reserve capacidade antes (init ou pré-aquecimento).

```cpp
class SerialFd {
public:
    explicit SerialFd(const char* path);
    ~SerialFd() { if (fd_ >= 0) ::close(fd_); }
    SerialFd(const SerialFd&) = delete;
    SerialFd& operator=(const SerialFd&) = delete;
    int get() const noexcept { return fd_; }
private:
    int fd_{-1};
};
```

## Erros

- Exceção não atravessa fronteira de biblioteca C nem callback de sinal.
- Prefira `std::optional` ou código de erro; `tl::expected` só com ADR.
- `[[nodiscard]]` em retorno que não pode ser ignorado.
- `noexcept` explícito em destrutor e movimento.

## Concorrência

- `std::atomic` para flags/contadores; `std::mutex` + `lock_guard` para estado.
- Nunca segurar mutex durante I/O bloqueante ou syscall longa.
- Thread nomeada (`pthread_setname_np`); afinidade explícita quando a latência importa.
- `volatile` **não** é sincronização em C++.
- Laço principal em `epoll`/`poll` com timeout máximo definido por macro; nunca infinito cego.

## Sinais e encerramento

`SIGTERM`/`SIGINT` **devem** liberar todas as teclas antes de sair:

```cpp
static std::atomic<bool> g_stop{false};
static void on_signal(int) { g_stop.store(true); }   /* async-signal-safe */

while (!g_stop.load()) { /* epoll_wait com timeout */ }
release_all_keys();                                  /* fail-safe obrigatorio */
sd_notify(0, "STOPPING=1");
```

- Handler toca somente `std::atomic` lock-free / `sig_atomic_t`.
- Nada de `malloc`, `printf` ou mutex no handler.

## systemd

- `Type=notify` + `sd_notify(0, "READY=1")` só após o hardware estar pronto.
- `WatchdogSec=`: enviar `WATCHDOG=1` do laço. Laço travado ⇒ serviço reinicia.
- Log via journald (`sd_journal_send`); nunca `stdout` cru.
- Privilégio mínimo: capabilities específicas para `hidg`/`uinput`, não `root` pleno.
- Config em `/etc/uk`, estado em `/var/lib/uk`.
- **Ordem de shutdown importa**: liberar teclas → parar render → fechar gadget.

## USB HID

- Interface de teclado em **boot protocol** sempre disponível.
- Escrever no `hidg` pode bloquear: `O_NONBLOCK` + retry com timeout curto; nunca bloquear o
  laço de scan.
- `release_all()` antes de qualquer transição de falha; modificador nunca sozinho.
- Debounce/dwell aplicado em **um** lugar só (firmware **ou** parser), nunca nos dois.

## Render e tela

- Renderização em thread separada da captura de eventos.
- Fila de teclas sujas com limite fixo; se encher, **descarte a mais antiga e mescle**
  (coalescing), nunca bloqueie o produtor.
- Falha do driver de tela é degradação: logar, marcar contador, continuar digitando.

## Estilo

- `snake_case` para arquivo e função (consistência com o C do projeto); `PascalCase` para tipo.
- Namespace `uk::` para tudo do projeto.
- `#include`: próprio header → C++ std → C std → projeto.
- `clang-format` do repo; sem reformatação oportunista.

## Build limpo

`-Wall -Wextra -Werror -Wconversion -Wshadow -Wold-style-cast`.
`clang-tidy`: `bugprone-*`, subset de `cppcoreguidelines-*`, `performance-*`.
ASan/UBSan obrigatório no build de teste host.

## Proibido

- `using namespace std;` em header.
- `reinterpret_cast` sem comentário justificando layout.
- Capturar `this` em callback que sobrevive ao objeto.
- `std::endl` em log de laço.
- `system()`/`popen()` com string construída de entrada externa.
