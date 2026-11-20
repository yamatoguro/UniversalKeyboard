---
name: layout-adaptation
description: |
  Procedimento para adaptar o teclado ao layout do host: diferença entre usage ID e caractere, detecção por SO (Win32/XKB/Wayland/macOS), fingerprint de máquina, normalização para uk_layout_id_t e tabela usage->legenda por layout.
  Triggers: "layout do host", "ABNT2", "ANSI", "US internacional", "detectar layout", "GetKeyboardLayout", "xkbcommon", "TISGetInputSource", "fingerprint", "machine-id", "usage id", "keycode", "legenda", "adaptação".
  NOT for: como desenhar a legenda (use key-rendering), protocolo HID (use hid-gadget).
---

# Adaptação de layout — procedimento

## A confusão que precisa ser evitada

| Camada | O que trafega |
|---|---|
| Teclado → host | **usage ID** (ex.: `0x04` = `a`) |
| Host | aplica o **layout ativo** e produz caractere |
| Tela da tecla | precisa mostrar a **legenda que o host vai produzir** |

Um teclado não pode "enviar `ç`". Ele envia o usage ID que o host, sob ABNT2, traduz para
`ç`. Se o host estiver em US, o **mesmo** usage ID produz `;`.

Portanto: **legenda correta = f(usage_id, layout_ativo_do_host)**.

## Onde a detecção vive

No `uk-gui`, no host. Nunca no firmware nem no daemon.

Motivo: só o SO do host sabe qual layout está ativo, e ele só informa isso para um processo
rodando nele com acesso à API de entrada.

## Detecção por plataforma

### Windows

```text
GetForegroundWindow()
  -> GetWindowThreadProcessId()  -> thread id
  -> GetKeyboardLayout(thread_id) -> HKL
```

- `HKL` baixo = `LANGID`. ABNT2 = `0x0416` (pt-BR), US = `0x0409`.
- Layout é **por thread**: trocar de janela pode trocar layout. Reavaliar em
  `WM_INPUTLANGCHANGE` e em foco.
- `GetKeyboardLayoutList` para listar as instaladas.

### Linux X11

```text
XkbGetState(dpy, XkbUseCoreKbd, &state) -> state.group
xkb_state_key_get_one_sym() -> keysym -> caractere
```

- Requer `libxkbcommon` / `libX11-xcb`.
- Grupo muda por janela e por atalho do usuário.

### Linux Wayland

- **Não existe API universal.** Wayland não expõe layout global por design.
- Caminhos possíveis, por compositor:
  - GNOME: `gsettings get org.gnome.desktop.input-sources` (`mru-sources` dá a ordem).
  - KDE: `org.kde.keyboard` via D-Bus.
  - wlroots: protocolo `virtual_keyboard` só em versões recentes.
- Declare a limitação na UI. Ofereça escolha manual. Não invente detecção.

### macOS

```text
TISCopyCurrentKeyboardInputSource()
TISGetInputSourceProperty(src, kTISPropertyInputSourceID)  // "com.apple.keylayout.ABNT2"
Notificação: kTISNotifySelectedKeyboardInputSourceChanged
```

## Normalização

Nunca propague a string crua do SO. Mapeie para um identificador do projeto:

```c
typedef enum {
    UK_LAYOUT_UNKNOWN = 0,
    UK_LAYOUT_ABNT2,
    UK_LAYOUT_ANSI_US,
    UK_LAYOUT_ANSI_US_INTL,
    UK_LAYOUT_ISO_UK,
    UK_LAYOUT__COUNT
} uk_layout_id_t;
```

Tabela de mapeamento explícita, versionada, com caso `UNKNOWN` que não quebra nada.

## Fingerprint de máquina

| SO | Fonte |
|---|---|
| Windows | `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` + versão |
| Linux | `/etc/machine-id` + `ID`/`VERSION_ID` de `/etc/os-release` |
| macOS | `IOPlatformUUID` |

- Serve para **lembrar o perfil por computador**, não para inferir layout.
- Sem correspondência: usa o layout padrão configurado e sinaliza que é palpite.
- Nunca envie o fingerprint para a rede. Ele é local.

## Tabela usage → legenda

- Uma entrada por `(layout_id, usage_id)` → glifo + rótulo textual.
- Fonte de verdade única, compartilhada entre `uk-gui` (preview) e o teclado (render).
- Versionada; mudança exige bump e ADR, porque quebra perfis salvos.
- Casos que sempre quebram: `AltGr`, teclas mortas (`´`, `~`, `^`), `ç` do ABNT2, tecla
  `ABNT_C1`/`ABNT_C2`, e a diferença de forma do Enter (ISO vs ANSI).

## Teclas que não existem no layout atual

A matriz física é fixa (120). Se o layout ativo não usa uma posição:

- marcar `active = false` no `key_state_t`;
- renderizar como inativa (nunca invisível);
- **não** enviar usage ID dessa tecla.

## Envio ao teclado

- `SET_HOST_LAYOUT` idempotente: mesmo layout ⇒ não redesenhar.
- Transacional: `BEGIN` → fatiado → `COMMIT`.
- Sem `uk-gui`: o teclado mantém o último layout persistido e sinaliza "layout fixo".
- Reavaliar no arranque e em cada evento de troca; nunca só uma vez.

## Checklist

- [ ] Detecção implementada na plataforma certa, com fallback declarado.
- [ ] `UK_LAYOUT_UNKNOWN` tratado sem quebrar.
- [ ] Fingerprint não usado para inferir layout.
- [ ] Tabela unique e versionada.
- [ ] Teclas inativas renderizadas e não enviadas.
- [ ] Testado com ABNT2 e ANSI US reais, não só simulados.
