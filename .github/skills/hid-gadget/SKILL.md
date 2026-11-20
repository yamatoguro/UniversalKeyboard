---
name: hid-gadget
description: |
  Procedimento para o teclado USB: gadget composto no Pi Zero 2W (configfs/libcomposite), interface boot keyboard sempre ativa, NKRO por bitmap, interface vendor-specific transacional, release-all em toda falha e checklist BIOS/UEFI/KVM.
  Triggers: "USB HID", "gadget", "configfs", "libcomposite", "dwc2", "hidg", "boot protocol", "report protocol", "NKRO", "6KRO", "descriptor", "modificador preso", "BIOS", "UEFI", "KVM", "vendor interface".
  NOT for: protocolo serial com o Arduino (use serial-link).
---

# HID gadget — procedimento

## Regra zero

**Boot protocol sempre funciona.** BIOS, UEFI, menu de boot, KVM e instalador usam 8 bytes e
6 keycodes. Se isso falha, nada mais importa.

## Composição do dispositivo

| Interface | Classe | Função | Obrigatória |
|---|---|---|---|
| 0 | HID boot keyboard | digitação | sim |
| 1 | HID report NKRO | bitmap 120 bits | recomendada |
| 2 | HID vendor-defined | layout, macros, imagens, stats | sim (para o `uk-gui`) |

- Host que só fala boot protocol deve funcionar sem configuração.
- NKRO nunca substitui boot protocol; coexistem.
- Interface vendor indisponível não pode impedir digitação.

## Estrutura no Linux

```text
/sys/kernel/config/usb_gadget/uk/
├── idVendor, idProduct, bcdDevice
├── strings/0x409/{manufacturer,product,serialnumber}
├── configs/c.1/config
│   ├── strings/0x409/configuration
│   └── MaxPower
├── functions/hid.usb0   ← boot keyboard
├── functions/hid.usb1   ← NKRO
├── functions/hid.usb2   ← vendor
└── UDC                  ← bind ao controlador
```

- `dwc2` em modo peripheral (`dtoverlay=dwc2`); carregue `libcomposite`.
- Script de init **idempotente**: se o gadget já existe, apenas validar e religar o `UDC`.
- Desconexão do host ⇒ recrear o gadget, não reiniciar o daemon.

## Escrita no `hidg`

- Abrir `O_NONBLOCK`; `EAGAIN` = buffer cheio ⇒ retry com timeout curto.
- Nunca `while (1)` esperando o host consumir.
- Não escreva relatório idêntico ao anterior: compare e descarte duplicado.
- Falha persistente de escrita ⇒ estado degradado, mas **não** bloqueie o laço de scan.

## Release-all obrigatório

Disparado por: `SIGTERM`/`SIGINT`, perda de link com o Arduino, timeout de heartbeat, erro
irrecuperável, shutdown, watchdog.

```text
1. enviar relatorio: modifiers=0, keycodes={0,0,0,0,0,0}  (ou bitmap zerado)
2. aguardar aceite com timeout curto
3. registrar no journal
4. somente entao encerrar
```

Se o write falhar, ainda assim tentar **uma vez** mais e logar. Um modificador preso
inutiliza a máquina do usuário.

## Interface vendor-specific

- Toda mensagem: `version`, `opcode`, `len`, `payload`, `crc`.
- Transacional: `BEGIN` → fatias com `seq`/`offset` → `COMMIT`. Nada aplicado antes do
  `COMMIT`.
- `GET_REPORT` responde em tempo constante, sem alocar.
- Validar tamanho e faixa **antes** de qualquer uso. Report é entrada externa hostil.
- Limite de tamanho por report é pequeno: nunca assumir transferência inteira de uma vez.

## Descritores

- Um descritor por função, com `bInterval` coerente com o uso.
- Alterar descritor é mudança de contrato: exige ADR e novo teste em BIOS/KVM.
- Nunca reutilize `report ID` entre funções.

## Checklist antes de "pronto"

- [ ] Enumera e digita em BIOS/UEFI real.
- [ ] Funciona em IP-KVM.
- [ ] Funciona no instalador de SO.
- [ ] Windows, Linux e macOS, ABNT2 e US.
- [ ] Desconectar/reconectar host não deixa modificador preso.
- [ ] Suspender/retomar host não deixa modificador preso.
- [ ] `SIGTERM` no daemon libera teclas.
- [ ] Perda de link libera teclas.

## Não faça

- Enumerar só NKRO.
- Modificador sem keycode.
- `SET_REPORT` bloqueante no laço principal.
- Report parcial na interface boot.
- Assumir que o host entende bitmap NKRO.
