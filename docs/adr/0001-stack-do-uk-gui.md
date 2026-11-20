# ADR-0001 — Stack do `uk-gui`

- **Status:** Proposto
- **Data:** 2026-11-20
- **Decisores:** autor do projeto (`tau` propõe, decisão humana)
- **Substitui:** —
- **Substituído por:** —

## Contexto

O `uk-gui` é o painel multiplataforma do teclado: detecta o layout ativo do SO do host,
envia-o ao teclado pelo canal HID vendor-specific, edita macros e layouts e pré-visualiza
as 120 teclas.

Requisitos declarados pelo autor:

1. "O mais próximo do kernel possível."
2. Baixo custo computacional.
3. Extrema performance.
4. Multiplataforma: Windows, Linux e macOS.

Análise que separa os requisitos em dois caminhos distintos:

| Caminho | Necessidade real | Consequência |
|---|---|---|
| **I/O de sistema** — ler layout ativo, falar HID bruto | Precisa de chamada direta à API do SO, latência baixa, sem runtime intermediário | Aqui "próximo do kernel" é requisito de verdade |
| **Interface de edição** — 120 pré-visualizações, editor de macro | Precisa de UI responsiva; 120 tiles são leves para qualquer toolkit | Aqui "próximo do kernel" não traz benefício mensurável |

Conclusão da análise: o requisito de performance se aplica ao **caminho de I/O**, não à UI.
Escolher uma stack pesada para a UI não viola o requisito, desde que o núcleo de I/O seja
nativo. Isso amplia o espaço de solução e evita otimizar a parte errada.

### Restrições de plataforma que a stack precisa cobrir

| SO | Detecção de layout | HID bruto |
|---|---|---|
| Windows | `GetKeyboardLayout` (Win32) + `WM_INPUTLANGCHANGE` | HidD_* / SetupAPI |
| Linux X11 | `xkbcommon` / `XkbGetState` | `hidraw` |
| Linux Wayland | API do compositor (sem padrão único) | `hidraw` |
| macOS | Carbon TIS (`TISGetInputSourceProperty`) | IOHIDManager |

Nenhuma dessas APIs tem binding oficial multiplataforma: **sempre haverá uma camada de FFI
por plataforma**. A stack deve tornar essa camada barata e segura.

## Decisão

**Rust**, com o núcleo de I/O em uma crate própria e independente de UI:

```text
uk-host (crate)
├── layout/    deteccao por SO: windows-rs | x11rb + xkbcommon | objc2 + core-foundation
├── hid/       canal vendor: hidapi (ou nusb) atras de trait
└── protocol/  mensagens do protocolo vendor (ADR-0003), sem I/O

uk-gui (binario)
└── UI sobre uk-host
```

- O núcleo (`uk-host`) não depende de toolkit e é testável sem tela.
- A UI é escolhida separadamente. **Recomendação:** Slint ou egui (nativo, sem WebView).
  Tauri fica como alternativa caso se prefira UI web.
- Detecção e HID atrás de traits, para permitir dublê em teste e implementação nativa por SO.

Decisão **ainda não ratificada** pelo autor. Este ADR registra a proposta e o critério.

## Alternativas consideradas

| Alternativa | Prós | Contras | Por que não (por ora) |
|---|---|---|---|
| **Rust + UI nativa (Slint/egui)** | Segurança de memória, FFI barato, binário único, cross-compile simples, sem runtime pesado | Ecossistema de UI menos maduro que Qt; curva de aprendizado | **Recomendada** |
| Rust + Tauri | UI web madura, produtividade alta | WebView por plataforma (WebKitGTK, WebView2); peso e variação de comportamento | Só se a UI web for prioridade |
| C++ + Qt 6 | UI nativa madura, uma base de código | Dependência grande; distribuição complexa; ABI por plataforma | Válido se a equipe já domina Qt |
| C + toolkit nativo por SO | Controle máximo, menor footprint | Três UIs distintas = três vezes o custo de manutenção | Custo de manutenção desproporcional |
| Electron + TS | Prototipagem rápida | Runtime pesado, contraria requisito 2 e 3 | Descartado |

## Consequências

**Positivas**

- Um núcleo puro, sem toolkit, testável com dublês de SO e de HID.
- FFI explícito e localizado: cada plataforma em um módulo pequeno e revisável.
- Distribuição como binário único por plataforma; sem serviço em background.
- Trocar a UI não exige tocar no núcleo.

**Negativas**

- Adoção de Rust exige ferramental (`rustup`) e curva de aprendizado.
- Bindings de `xkbcommon` e Carbon TIS exigem manutenção quando o SO muda.
- UI em Slint/egui não tem aparência nativa perfeita.

**Mitigações**

- Manter a superfície de FFI mínima: só o necessário para layout e HID.
- Testes de contrato por plataforma em CI (matriz Win/Linux/macOS).
- Se a UI nativa se mostrar custosa, Tauri pode substituí-la sem tocar em `uk-host`.

## Verificação

A decisão está certa se, rodando no host:

1. Detecção de layout responde a troca de janela em **< 50 ms** (Windows/X11).
2. Processo ocioso consome **< 1% de CPU** (uso de evento, não polling).
3. Binário distribuível **sem instalador de runtime** adicional.
4. Uma única base de código cobre as três plataformas.

## Referências

- [`docs/context-map.md`](../context-map.md) §5 e §7
- ADR-0003 (protocolo HID vendor-specific)
