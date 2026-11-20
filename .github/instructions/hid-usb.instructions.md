---
description: 'Regras para USB HID: gadget no Pi Zero 2W, boot vs report protocol, NKRO, interface vendor-specific e compatibilidade com BIOS/UEFI/KVM.'
applyTo: '**/hid/**, **/usb/**, **/*hid*.{c,h,cpp,hpp}, **/*gadget*.{c,h,cpp,hpp}'
---

# USB HID — regras

## Princípio

O teclado precisa funcionar **antes de existir driver, SO ou agente**: BIOS, UEFI, menu de
boot, KVM e instalador usam *boot protocol*, 8 bytes, 6 keycodes. Se isso não funciona, o
resto é irrelevante.

## Estrutura do dispositivo (composto)

| Interface | Classe | Função |
|---|---|---|
| 0 | HID boot keyboard | digitação; funciona em BIOS/UEFI |
| 1 | HID report (NKRO) | bitmap de 112 bits; usado quando o host suporta |
| 2 | HID vendor-defined | controle: layout, macros, imagens, stats |

- Boot protocol **sempre** enumerado. Nunca remova em troca de NKRO.
- Host que fala apenas boot protocol cai para 6KRO automaticamente; não force NKRO.
- Interface vendor-specific é opcional para digitar: seu `SET_REPORT` não pode travar o
  laço principal.

## Relatório

```text
byte 0     : modificadores (bitmask)
byte 1     : reservado (0x00)
byte 2..7  : keycodes (boot)  |  bitmap (report/NKRO)
```

- Modificador nunca é enviado sem keycode correspondente.
- Transição para `SAFE`, shutdown ou perda de link ⇒ enviar relatório de
  **todas-as-teclas-liberadas** e confirmar que foi aceito.
- Reenvio do mesmo relatório é desperdício de banda: compare com o último enviado e só
  escreva se mudou.
- Erro de `write` no `hidg` ⇒ `EAGAIN` significa buffer cheio: retry com timeout curto,
  nunca `while(1)`.

## Boot vs NKRO

- Detecte o protocolo ativo (`USB_REQ_SET_PROTOCOL`/`GET_PROTOCOL`) e mantenha os dois
  relatórios coerentes.
- NKRO via bitmap é o padrão moderno; host antigo pode não entender bitmap — a interface
  boot cobre esse caso.

## Interface vendor-specific

- Todo report tem `version`, `opcode`, `len`, `crc`.
- Escrita é **transacional**: nada é aplicado antes de `COMMIT`.
- Payload grande é fatiado em `offset` + `seq`; montagem validada antes do `COMMIT`.
- `GET_REPORT` de status pode ser chamado a qualquer momento: responda em tempo constante e
  sem alocar.
- Nunca execute comando recebido sem validar tamanho e faixa.

## Gadget no Linux (Pi Zero 2W)

- `configfs` + `libcomposite`; `dwc2` em modo peripheral.
- Configuração idempotente no boot: script/unit que cria gadget se ausente, sem depender de
  estado sujo de execução anterior.
- Escrita no `hidg` em `O_NONBLOCK`; fila pequena e timeout.
- Se o host desconectar, o gadget precisa ser recriado sem reiniciar o daemon.

## Compatibilidade — checklist obrigatório

Antes de considerar o HID pronto:

- [ ] Enumera e digita em BIOS/UEFI de uma máquina real.
- [ ] Funciona em KVM/IP-KVM.
- [ ] Funciona com o instalador de SO (ambiente mínimo, sem hotplug).
- [ ] Funciona em Windows, Linux e macOS com layout ABNT2 e US.
- [ ] Host desconectado/reconectado não deixa modificador preso.
- [ ] Suspender/retomar o host não deixa modificador preso.

## Proibido

- Modificador preso em qualquer caminho de erro.
- Report parcial (menos de 8 bytes) na interface boot.
- `SET_REPORT` bloqueante dentro do laço de scan.
- Assumir que o host entende NKRO.
- Enumerar apenas NKRO.
