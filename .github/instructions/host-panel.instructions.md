---
description: 'Regras para o painel uk-gui no host: detecção de layout do SO, fingerprint de máquina, canal HID vendor-specific e requisitos de performance multiplataforma.'
applyTo: '**/uk-gui/**'
---

# uk-gui — painel do host

## Papel

Painel multiplataforma que (a) descobre qual layout o SO do host está usando, (b) envia
esse layout ao teclado, (c) edita macros, camadas e o que aparece em cada tela, (d) gerencia
o driver. Referência conceitual: VIA para QMK, mas com layout reativo ao SO e destino
multi-tela.

## Stack: em aberto

Requisitos declarados: **mais próximo do kernel possível, baixo custo computacional,
extrema performance**, multiplataforma. Candidatos: Rust, C++, C + toolkit nativo.

Regra: **não crie código de `uk-gui` antes da stack estar decidida em ADR.** A escolha muda
todo o resto. Ao ser perguntado, apresente as opções com prós/contras e registre em ADR.

## Detecção de layout

### Obrigações por plataforma

| SO | Fonte | Reavaliar quando |
|---|---|---|
| Windows | `GetForegroundWindow` → `GetWindowThreadProcessId` → `GetKeyboardLayout` | `WM_INPUTLANGCHANGE`, troca de janela em foco |
| Linux X11 | `XkbGetState` / `xkbcommon` | evento de grupo do teclado |
| Linux Wayland | `gsettings get org.gnome.desktop.input-sources` (GNOME) ou API do compositor | mudança de settings |
| macOS | `TISGetInputSourceProperty` (`kTISPropertyInputSourceID`) | `kTISNotifySelectedKeyboardInputSourceChanged` |

- Layout é **por janela em Windows e X11**: reavaliar no foco, não só no arranque.
- Wayland não expõe layout global por design. Documente a limitação; não finja que existe.
- Normalize para um identificador estável do projeto (`uk_layout_id_t`), não para a string
  crua do SO. Tabela de mapeamento explícita e versionada.

### Fingerprint

- Windows: `MachineGuid` (HKLM) + versão do SO.
- Linux: `/etc/machine-id` + `ID`/`VERSION_ID` de `/etc/os-release`.
- macOS: `IOPlatformUUID`.

Fingerprint identifica **máquina**, não layout. Nunca derive layout do fingerprint.

## Canal com o teclado

- Somente **HID vendor-specific** no mesmo USB do teclado. Sem socket, sem driver de kernel.
- `SET_HOST_LAYOUT` idempotente: reenviar o mesmo layout não deve causar redesenho.
- Envio transacional: `BEGIN` → fatiado com `seq`/`offset` → `COMMIT`. Falha ⇒ teclado mantém
  o estado anterior.
- Reconexão: ao detectar o dispositivo de volta, reenviar layout e perfil ativo.
- Sem o painel, o teclado opera com o último perfil persistido. O painel é **opcional para
  digitar** — nunca introduza dependência.

## Performance

- Processo ocioso não deve consumir CPU mensurável: use evento do SO, não polling.
- Polling de layout é aceitável apenas com intervalo ≥ 250 ms e comparação de valor anterior.
- Nenhuma operação de rede. Nenhum telemetria por padrão.
- Leitura de HID bruto no mínimo necessário; não abrir o dispositivo em modo que impeça o
  teclado de funcionar.

## UX mínima

- Pré-visualização das teclas usa o mesmo modelo de dados do teclado (mesmo `key_idx`,
  mesmo `usage_id`, mesmo layout) — sem duplicar a tabela de mapeamento.
- Editor de macro mostra os keycodes resultantes, não só os caracteres.
- Aviso claro quando o layout detectado não é suportado, com opção de fixar manualmente.

## Proibido

- Assumir layout a partir do idioma do SO ou da localidade do sistema.
- Enviar caractere em vez de usage ID.
- Duplicar a tabela usage → legenda em dois lugares.
- Introduzir dependência que exija serviço em background no host.
- Bloquear o teclado enquanto uma atualização de imagem está em andamento.
