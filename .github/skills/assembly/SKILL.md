---
name: assembly
description: |
  Procedimento para Assembly no projeto: critérios para justificar uso, ABI AVR e ARMv8-A, preservação de registradores, contagem de ciclos medida e teste obrigatório em bancada.
  Triggers: "assembly", "asm", "AVR asm", "ARM asm", "AArch64", "Thumb-2", "ABI", "registrador", "ciclos", "inline asm", "bit-bang", "delay de ciclo", "ISR em asm".
  NOT for: lógica que C resolve (use embedded-c).
---

# Assembly — procedimento

## Portão de entrada

Assembly só entra se **uma** destas for verdadeira, escrita na descrição do commit:

1. Protocolo com janela de tempo que C não garante (bit-banged, WS2812, 1-Wire sem
   periférico).
2. Instrução/registrador sem intrínseco no compilador alvo.
3. Layout exigido por hardware: vetor de reset, bootloader, seção com endereço fixo.

Se não for uma das três: **não é assembly**. Reescreva em C.

## ABI — AVR

| Recurso | Regra |
|---|---|
| `r1` | zero constante; nunca usar como acumulador |
| `r0` | temporário de multiplicação |
| `r25:r24` | 1º argumento / retorno |
| `r23:r22`, `r21:r20`… | argumentos seguintes |
| `r18`–`r27`, `r30`, `r31` | call-clobbered: salvar antes de usar |
| `r26/r27` = X, `r28/r29` = Y, `r30/r31` = Z | ponteiros indiretos / frame |

- Em ISR, salve **tudo** que tocar. O compilador não sabe o que o asm usa.
- Preserve `SREG` sempre que alterar flags:

```asm
isr_snippet:
    push    r16
    in      r16, SREG
    push    r16
    /* corpo */
    pop     r16
    out     SREG, r16
    pop     r16
    reti
```

## ABI — AArch64 (Pi Zero 2W em 64-bit)

- `x0`–`x7`: argumentos e retorno. `x8`: indireto de resultado/syscall.
- `x9`–`x15`: temporários. `x19`–`x28`: callee-saved.
- `x29` = FP, `x30` = LR. **`sp` alinhado a 16 bytes** em toda chamada.

```asm
uk_delay_cycles:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    /* corpo */
    ldp     x29, x30, [sp], #16
    ret
```

## ABI — AArch32/Thumb-2 (se o SO for 32-bit)

- `r0`–`r3`: argumentos. `r4`–`r11`: callee-saved. `r13` = SP, `r14` = LR, `r15` = PC.
- Declare `.thumb`/`.arm` e respeite AAPCS.

## Escrita

- Cabeçalho obrigatório: alvo, ABI, propósito, autor, data, **custo medido em ciclos**.
- Comentário de **intenção** por bloco, não tradução da instrução.
- Constantes com `.equ`; nenhum número mágico no corpo.
- Rotina declara efeitos colaterais (flags, memória, periférico).
- Sem `nop` de enroscamento sem justificativa escrita.

## Timing

- Custo em ciclos **medido**, não estimado. Meça com pino de GPIO + osciloscópio ou com
  contador de ciclos, e registre o método.
- Documente `F_CPU` / frequência assumida.
- Ao trocar compilador, flags de otimização ou versão do assembler, **revalide** o timing.
- `_delay_loop_*` do `avr-libc` só com `F_CPU` correto; nunca copie o loop à mão.

## Interface com C

- Protótipo `extern "C"` no header.
- Teste de ABI: chamar de C e verificar argumentos, retorno e preservação de callee-saved.
- Se for inline asm, declare corretamente os operandos (`"=r"`, `"memory"`, clobbers) —
  inline asm errado é o bug mais difícil de achar do projeto.

## Teste

- Função Assembly exposta a C precisa de teste host quando portável.
- Quando não portável: teste de bancada com analisador lógico, com captura anexada ao PR.
- "Compila" não é evidência para Assembly. Precisa de execução observada.

## Não faça

- Inline asm para economizar 2 ciclos sem medição.
- Alterar `sp` sem restaurar exatamente.
- Usar callee-saved sem salvar.
- Depender de comportamento não documentado do assembler.
- Deixar Assembly sem teste de bancada.
