---
name: bench-test
description: |
  Procedimento de validação em hardware real: checklist de bancada, medição de scan, medição de banda do barramento de display, matriz completa, BIOS/UEFI/KVM, perda de link, modificador preso e evidências exigidas.
  Triggers: "bancada", "bench", "HIL", "hardware real", "validar no Pi", "testar no arduino", "osciloscópio", "analisador lógico", "medir", "BIOS", "UEFI", "KVM", "tecla presa", "modificador preso", "evidência".
  NOT for: teste de unidade host (use cross-build), CI (use workflow-release).
---

# Bancada — procedimento

## Regra

Nada é considerado pronto sem execução observada no hardware. Em especial: **nada de
Assembly, HID ou driver de display** sem bancada.

## Equipamento mínimo

- Pi Zero 2W com o teclado montado.
- Arduino com a matriz completa (120 teclas).
- Host de teste (idealmente 2: um moderno, um com BIOS legada).
- Analisador lógico (pelo menos 8 canais).
- Osciloscópio (para settle da matriz e integridade do barramento).
- Fonte com medição de corrente (para detectar brownout no boot dos displays).

## Checklist de bring-up (ordem)

1. **Alimentação**: tensão estável em carga máxima dos 120 displays; sem brownout no boot.
2. **Matriz**: cada uma das 120 teclas individualmente; depois pares e tríades simultâneas
   (verifica diodo).
3. **Scan**: medir duração completa; registrar min/média/máx.
4. **Barramento de display**: medir vazão real; registrar bytes/s. Comparar com o orçamento.
5. **Render**: 1 tecla, 10 teclas, tela cheia; medir tempo observado.
6. **Link serial**: conectar, heartbeat, forçar perda (desligar Arduino) e reconectar.
7. **HID**: enumerar no host; digitar; testar em BIOS/UEFI; testar em KVM.
8. **Layout**: ABNT2 e ANSI US reais; conferir cada legenda contra o caractere produzido.
9. **Fail-safe**: `kill -TERM` no daemon → modificadores liberados?
10. **Suspender/retomar** host → estado do teclado?

## Teste de modificador preso (obrigatório)

```text
1. Segurar Shift fisicamente (ou injetar evento).
2. Matar o daemon com SIGTERM.
3. Verificar no host que Shift foi liberado.
4. Repetir com: perda de link, desconexão USB do host, reboot do Pi.
```

Qualquer cenário que deixe modificador ativo é **bug bloqueante**.

## Evidência exigida no PR

- Comando/roteiro usado.
- Números medidos (não "ficou rápido").
- Foto ou captura de tela quando for visual.
- Captura do analisador lógico quando for timing.
- Versão de firmware, commit e build usados.

Sem isso, o item permanece "não verificado" — e deve ser reportado como tal.

## Medições que valem registrar

| Medição | Onde |
|---|---|
| Duração do scan (min/média/máx) | firmware, log de boot |
| Vazão do barramento de display | driver, log de boot |
| Tempo de render por tecla | daemon stats |
| Latência evento → relatório HID | analisador lógico |
| Contagem de erro CRC | daemon stats |
| Corrente de pico no boot dos displays | fonte |

## Quando não há bancada

É legítimo não ter. O que **não** é legítimo:

- afirmar que funciona sem ter executado;
- marcar checklist como completo sem evidência;
- fechar issue de hardware sem validação.

Reporte explicitamente: "implementado e testado no host; **não validado em bancada**", com a
lista do que falta verificar.

## Não faça

- Testar "no escuro" por analogia com outro hardware.
- Considerar `compila` como evidência.
- Deixar o teste de modificador preso para depois.
- Medir com o sistema em carga diferente da real.
