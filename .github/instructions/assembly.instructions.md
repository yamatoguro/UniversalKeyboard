---
description: 'Regras para Assembly (AVR e ARMv8-A): ABI, preservação de registradores, contagem de ciclos, uso restrito e documentação obrigatória.'
applyTo: '**/*.{s,S,asm,inc}'
---

# Assembly — regras

Assembly é a **última** ferramenta, não a primeira. Antes de escrever, responda por escrito
na descrição do commit **por que** C não resolve:

- timing de ciclo exato comprovado (protocolo bit-banged com janela apertada),
- instrução sem intrínseco no compilador alvo,
- bootloader / vetor de reset / seção com layout exigido pelo hardware.

Se a resposta não for uma das três, **não é assembly** — reescreva em C.

## ABI — AVR (`avr-gcc`)

- `r1` = zero. Nunca use como acumulador.
- `r0` = temporário de multiplicação; `r1:r0` no retorno de 16 bits.
- Argumentos: `r25:r24` (1º), `r23:r22` (2º), …; retorno em `r25:r24`.
- Registradores `r18`–`r27`, `r30`, `r31` são **call-clobbered**: salve antes de usar.
- `r28`/`r29` = `Y`, `r26`/`r27` = `X`, `r30`/`r31` = `Z` (ponteiros de frame e indiretos).
- Em ISR, salve/restaure **todo** registrador que tocar — o compilador não sabe o que você usa.

```asm
/* Preserva SREG: interrupções podem alterar flags. */
isr_snippet:
    push    r16
    in      r16, SREG
    push    r16
    /* ... corpo ... */
    pop     r16
    out     SREG, r16
    pop     r16
    reti
```

## ABI — ARMv8-A (AArch64, Pi Zero 2W 64-bit)

- `x0`–`x7`: argumentos e retorno; `x8`: indireto de resultado/syscall.
- `x9`–`x15`: temporários (call-clobbered). `x19`–`x28`: callee-saved.
- `x29` = FP, `x30` = LR, `sp` alinhado a **16 bytes** em toda chamada.
- `xzr` = zero; `w` registers acessam os 32 bits baixos.

```asm
/* Preserva callee-saved e alinhamento. */
uk_delay_cycles:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    /* ... corpo ... */
    ldp     x29, x30, [sp], #16
    ret
```

## AArch32/Thumb-2 (se o alvo for 32-bit)

- `r0`–`r3`: argumentos; `r4`–`r11`: callee-saved; `r13` = SP; `r14` = LR; `r15` = PC.
- Respeite a diretiva `.thumb`/`.arm` e o estado `AAPCS`.

## Regras de escrita

- Cabeçalho obrigatório no arquivo: alvo, ABI, propósito, autor, data, custo em ciclos.
- Cada bloco tem comentário de **intenção**, não de tradução da instrução.
- Constantes nomeadas com `.equ`; sem número mágico no corpo.
- Sem `nop` de enroscamento sem justificativa escrita.
- Rotina com efeito colateral declara o que altera (flags, memória, periférico).
- Chamadas entre C e Assembly: protótipo `extern "C"` no header e teste de ABI.

## Timing

- Cada rotina crítica declara o custo **medido** em ciclos, não estimado.
- Documente a frequência de clock assumida (`F_CPU`).
- `_delay_loop_*` do `avr-libc` só com `F_CPU` correto; nunca copie o loop à mão.
- Ao alterar compilador ou otimização, revalide o timing — o inline asm pode mudar de
  contexto.

## Teste

- Função Assembly exposta a C precisa de teste host (quando portável) ou de teste de
  bancada com analisador lógico.
- Nunca aceitar "compila" como evidência para Assembly. Precisa de execução observada.

## Proibido

- Assembly inline em C para economizar 2 ciclos sem medição.
- Alterar `sp` sem restaurar exatamente.
- Usar registrador callee-saved sem salvar.
- Depender de comportamento não documentado do assembler.
