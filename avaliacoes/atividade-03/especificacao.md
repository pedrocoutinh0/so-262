# Especificação do gerenciador de processos

Simulador em modo usuário de um núcleo de sistema operacional, focado em processos, estados, PCB e escalonamento de CPU.

**Referência:** Tanenbaum, A. S.; Bos, H. *Sistemas Operacionais Modernos*. 4. ed. Pearson, 2016. Capítulo 2 — Processos e threads (ISBN 9788543005676).

**Objetivo deste documento:** servir de entrada para geração de código por harness (Claude Code, Open Code ou equivalente). A implementação deve seguir esta especificação sem inventar requisitos conflitantes.

---

## 1. Visão geral e arquitetura do simulador

### 1.1 Contexto

Um processo é a abstração de um programa em execução (Tanenbaum, cap. 2). O simulador reproduz **pseudoparalelismo**: uma única CPU virtual executa um processo por vez e alterna entre processos prontos, criando a ilusão de concorrência.

O programa roda **em modo usuário**. Não há kernel real, interrupções de hardware nem MMU. Relógio, CPU, E/S e o escalonador são objetos do simulador.

Fora de escopo nesta atividade: threads, memória virtual, sistema de arquivos real e IPC avançada (semáforos, mutexes). E/S é um evento fictício que apenas bloqueia e depois libera o processo.

### 1.2 Hardware simulado

| Componente | Papel |
|---|---|
| CPU virtual | Executa exatamente um processo por tick, se houver processo em execução. |
| Registradores | Conjunto mínimo salvo/restaurado na troca de contexto: `pc`, `acc` (acumulador) e `psw` (palavra de estado). |
| Contador de programa | Índice da próxima instrução do processo na sua lista de surtos (CPU/E/S). |
| Relógio lógico | Inteiro `tick`, inicia em 0 e avança de 1 em 1. Toda decisão do núcleo ocorre em um tick. |
| Dispositivo de E/S fictício | Fila simples. Um processo bloqueado por E/S torna-se pronto quando `tick` atinge o instante de conclusão da operação. |

A troca de contexto é explícita: salvar registradores e estado no PCB do processo atual, escolher o próximo pelo escalonador, restaurar registradores do escolhido. O custo da troca **não** consome ticks (simplificação), mas cada troca deve ser registrada no log.

### 1.3 Núcleo simulado (módulos)

```
Simulador
├── RelogioLogico
├── CpuVirtual
├── TabelaDeProcessos          (coleção de PCBs)
├── FilasDeEstado
│     ├── filaPronto
│     └── filaBloqueado
├── DispositivoES
├── Escalonador                (interface)
│     ├── RoundRobin
│     └── PrioridadeComEnvelhecimento
├── CarregadorDeTarefas        (lê o arquivo de tarefas)
└── Relatorio                  (Gantt, log, estatísticas)
```

O laço principal, a cada tick:

1. Avançar o relógio.
2. Processar E/S concluídas (`bloqueado` → `pronto`).
3. Admitir processos cujo tempo de chegada é o tick atual (`novo` → `pronto`).
4. Se o processo em execução esgotou o quantum, pediu E/S ou terminou, tratar a transição.
5. Se a CPU estiver ociosa e houver processo pronto, chamar o escalonador.
6. Se houver processo em execução, consumir 1 unidade do surto de CPU atual e atualizar tempos no PCB.
7. Registrar o ocupante da CPU no Gantt (PID ou `-` se ociosa).

Encerrar quando não restarem processos prontos, em execução ou bloqueados, e todos os processos do arquivo tiverem sido admitidos.

### 1.4 Linguagem e organização

- Linguagem: **Java** (mesma linha da atividade-02), JDK 11 ou superior.
- Pacote sugerido: `simulador`.
- Um processo por classe responsável; nomes completos, sem abreviações (`TabelaDeProcessos`, não `TDP`).
- Código gerado deve ser compilável com `javac` e executável por uma classe `Simulador` com `main`.

---

## 2. PCB e tabela de processos

O núcleo mantém uma **tabela de processos**: um registro por processo (Tanenbaum, fig. 2.4). No simulador, cada entrada é um PCB.

### 2.1 Campos obrigatórios do PCB

| Campo | Tipo | Descrição |
|---|---|---|
| `pid` | int | Identificador único, atribuído na criação, a partir de 1. |
| `nome` | String | Rótulo do processo no arquivo de tarefas (ex.: `P1`). |
| `estado` | enum | `NOVO`, `PRONTO`, `EM_EXECUCAO`, `BLOQUEADO`, `TERMINADO`. |
| `prioridadeBase` | int | Prioridade estática lida do arquivo. Maior valor = maior prioridade. Faixa 1–10. |
| `prioridadeAtual` | int | Usada pelo escalonador de prioridades; pode subir por envelhecimento. |
| `pc` | int | Índice do surto atual na lista de operações. |
| `acc` | int | Registrador de trabalho (pode permanecer 0 se não for usado pelas tarefas). |
| `psw` | int | Palavra de estado simplificada (bit 0 = em modo núcleo durante troca de contexto). |
| `tempoChegada` | int | Tick em que o processo entra no sistema. |
| `tempoInicio` | int | Primeiro tick em que ocupou a CPU; `-1` se ainda não executou. |
| `tempoTermino` | int | Tick em que passou a `TERMINADO`; `-1` se ativo. |
| `tempoCpuUsado` | int | Ticks efetivamente executados na CPU. |
| `tempoEspera` | int | Ticks em `PRONTO` aguardando CPU. |
| `tempoBloqueado` | int | Ticks em `BLOQUEADO`. |
| `quantumRestante` | int | Ticks que ainda pode usar no quantum corrente. |
| `pidPai` | int | `0` para processos criados pelo carregador; PID do pai em `fork` simulado. |
| `surtos` | lista | Sequência de operações `CPU n` ou `ES n` (n > 0). |
| `restanteNoSurto` | int | Unidades que faltam no surto apontado por `pc`. |

Campos de memória e arquivos da figura 2.4 do livro **não** são obrigatórios (não há MMU nem FS neste simulador).

### 2.2 Tabela de processos

- Armazenar todos os PCBs, inclusive terminados, para o relatório final.
- Consulta por PID em O(n) aceitável (N pequeno, típico ≤ 32 processos).
- Invariante: no máximo **um** PCB em `EM_EXECUCAO` em qualquer tick.
- Invariante: processo em `PRONTO` está na fila de prontos; em `BLOQUEADO`, na fila de bloqueados (ou na estrutura do dispositivo de E/S).

---

## 3. Ciclo de vida e grafo de transição de estados

Modelo clássico de três estados do livro (fig. 2.2), acrescido de `NOVO` e `TERMINADO` para criação e `exit`.

```
                    criação (arquivo ou fork)
                              │
                              v
                            NOVO
                              │
                              │ admissão (tick >= tempoChegada)
                              v
         ┌---------------- PRONTO ----------------┐
         │                    ^                   │
         │                    │                   │
         │     E/S concluída  │                   │ escalonador seleciona
         │                    │                   v
         │               BLOQUEADO         EM_EXECUCAO
         │                    ^                   │
         │                    │ pedido de E/S     │
         │                    └-------------------┤
         │                                        │
         │     quantum expirou / preemptado       │
         └----------------------------------------┤
                                                  │ exit / fim dos surtos
                                                  v
                                             TERMINADO
```

### 3.1 Transições obrigatórias

| Evento | De | Para | Quem dispara |
|---|---|---|---|
| Criação / `fork` | — | `NOVO` | Carregador ou processo que simula `fork` |
| Admissão | `NOVO` | `PRONTO` | Núcleo, no tick de chegada |
| Escalonamento | `PRONTO` | `EM_EXECUCAO` | Escalonador |
| Expiração de quantum | `EM_EXECUCAO` | `PRONTO` | Relógio (interrupção periódica simulada) |
| Pedido de E/S | `EM_EXECUCAO` | `BLOQUEADO` | Instrução `ES n` |
| E/S concluída | `BLOQUEADO` | `PRONTO` | Dispositivo fictício |
| `exit` / surtos esgotados | `EM_EXECUCAO` | `TERMINADO` | Processo |

Não existe transição direta `BLOQUEADO` → `EM_EXECUCAO`. A E/S concluída sempre passa por `PRONTO` (Tanenbaum, transição 4 da fig. 2.2).

### 3.2 Criação (`fork` simulado)

O arquivo de tarefas é a fonte principal de processos. Além disso, uma operação `FORK` na lista de surtos deve:

1. Criar um filho com novo PID.
2. Copiar os surtos **restantes após o FORK** para o filho (modelo simplificado, sem `exec`).
3. Filho nasce em `NOVO` com `tempoChegada` = tick atual e `pidPai` = PID do pai.
4. Pai continua no próximo surto.

Se o arquivo não usar `FORK`, a criação ocorre só pelo carregador — ainda assim o código da transição deve existir e ser testável.

### 3.3 Término (`exit`)

Quatro causas no livro: saída normal, erro fatal, erro interno, morto por outro processo. O simulador implementa **saída normal**: o processo termina ao consumir o último surto ou ao executar `EXIT`. Não é necessário `kill` nesta versão.

---

## 4. Escalonador de CPU

O escalonador escolhe, entre os processos em `PRONTO`, quem vai para `EM_EXECUCAO`. A política é **intercambiável** em tempo de execução (argumento de linha de comando).

Pontos em que o livro exige decisão de escalonamento (seção 2.4.1): criação, término, bloqueio e interrupção (aqui: relógio e E/S concluída).

### 4.1 Interface

```text
interface Escalonador
    String nome()
    Pcb selecionar(List<Pcb> prontos, Pcb atual, int tick)
    void onQuantumExpirado(Pcb atual)
    void onEntradaNaFila(Pcb pcb, int tick)
```

O núcleo **não** contém `if (algoritmo == RR)`. Novos algoritmos entram como novas implementações da interface.

### 4.2 Round Robin (chaveamento circular)

Conforme seções 2.4.3 e fig. 2.42:

- Fila circular (FIFO) de processos prontos.
- Quantum `Q` configurável (padrão **4** ticks). Faixa válida: 1–20.
- O processo em execução usa a CPU até: terminar o quantum, bloquear em E/S, ou terminar.
- Quantum esgotado: o processo vai para o **fim** da fila; o da frente é o próximo.
- Se o processo bloqueia ou termina antes do fim do quantum, a CPU é redistribuída imediatamente (não se espera o quantum acabar).
- Novo processo pronto entra no fim da fila.
- Empate: ordem de chegada na fila (estável).

### 4.3 Prioridades com envelhecimento (prevenção de inanição)

Conforme “Escalonamento por prioridades” (p. 110–111):

- Sempre executa o processo pronto de **maior `prioridadeAtual`**.
- Empate: Round Robin entre os de mesma prioridade (fila FIFO + quantum).
- Prioridades **dinâmicas** para evitar starvation: a cada `AGING_INTERVAL` ticks (padrão **8**), todo processo em `PRONTO` que não está em execução recebe `+1` em `prioridadeAtual`, até um teto (padrão **10**).
- Ao ser selecionado para a CPU, `prioridadeAtual` volta para `prioridadeBase` (reset após receber serviço).
- Quantum também se aplica (preempção por relógio), senão um processo de alta prioridade CPU-bound monopoliza a CPU (alerta do livro).

Prioridades estáticas puras **não** atendem o requisito de prevenção de inanição. O envelhecimento é obrigatório nesta política.

### 4.4 Seleção na linha de comando

```text
java simulador.Simulador --algoritmo rr --quantum 4 tarefas.txt
java simulador.Simulador --algoritmo prioridade --quantum 4 --aging 8 tarefas.txt
```

`--algoritmo` aceita `rr` ou `prioridade`. Arquivo de tarefas é o último argumento posicional.

---

## 5. Entradas, casos de teste e entrega

### 5.1 Arquivo de tarefas

Texto UTF-8, uma declaração de processo por bloco. Linhas vazias e linhas iniciadas por `#` são ignoradas.

Gramática:

```text
processo <nome> chegada <tick> prioridade <1-10>
  CPU <n>
  ES <n>
  FORK
  EXIT
```

Regras:

- `nome` é único no arquivo.
- `chegada` ≥ 0.
- Pelo menos um surto `CPU` ou um `EXIT`.
- `CPU n` e `ES n` com `n` inteiro > 0.
- `FORK` é opcional; `EXIT` no fim é opcional (fim da lista = exit implícito).
- Ordem dos surtos é a ordem de execução do “programa” do processo.

Exemplo `tarefas.txt`:

```text
# dois processos CPU-bound e um com E/S
processo P1 chegada 0 prioridade 3
  CPU 5
  ES 3
  CPU 4

processo P2 chegada 1 prioridade 1
  CPU 10

processo P3 chegada 2 prioridade 5
  CPU 2
  ES 2
  CPU 2
```

### 5.2 Saída do simulador

Três seções obrigatórias no stdout (e as mesmas gravadas em `saida.txt` no diretório de execução):

**A) Log de transições** — uma linha por evento:

```text
[tick=0007] P1 EM_EXECUCAO -> BLOQUEADO (pedido de E/S, duracao=3)
[tick=0008] P2 PRONTO -> EM_EXECUCAO (escalonador=rr)
```

**B) Gantt textual** — uma célula por tick:

```text
Tick:  0  1  2  3  4  5  6  7  8  9 10
CPU:  P1 P1 P1 P1 P2 P2 P2 P2 P1 P1 --
```

`--` indica CPU ociosa.

**C) Estatísticas**

Para cada processo: tempo de espera, tempo de CPU, tempo de retorno (`tempoTermino - tempoChegada`), tempo de bloqueio.

Globais: utilização de CPU = ticks em que a CPU não esteve ociosa / ticks totais até o último término; número de trocas de contexto; algoritmo e quantum usados.

Incluir na primeira linha da saída o nome do(s) aluno(s).

### 5.3 Casos de teste mínimos

| ID | Objetivo | Entrada resumida | Resultado esperado |
|---|---|---|---|
| T1 | RR básico | 2 processos só CPU, chegada 0, quantum 4, bursts 5 e 5 | Alternância a cada 4 ticks; ambos terminam; Gantt sem ociosidade inicial. |
| T2 | Bloqueio e E/S | 1 processo `CPU 2 / ES 3 / CPU 1` | Após 2 ticks vai a bloqueado; CPU ociosa ou outro processo; volta a pronto no tick de fim da E/S. |
| T3 | Quantum | 1 processo CPU 10, quantum 4, sozinho | Não há preempção útil (único pronto), mas `quantumRestante` é renovado; processo termina em 10 ticks de CPU. |
| T4 | Prioridade + starvation | P_alto prioridade 9 CPU 20; P_baixo prioridade 1 CPU 2; aging 8 | P_baixo **não** espera indefinidamente; em algum tick executa após envelhecer. |
| T5 | Fork | P1 faz `CPU 1 / FORK / CPU 1` | Surge um filho com PID novo; ambos aparecem no Gantt e no relatório. |
| T6 | Arquivo inválido | `CPU -1` ou nome duplicado | Encerrar com código ≠ 0 e mensagem clara em stderr; não gerar Gantt parcial como sucesso. |

Os casos T1–T5 devem ser reproduzíveis (mesma entrada → mesmo Gantt). Não usar `Math.random` no núcleo.

### 5.4 Diretrizes de entrega

- Pasta: `avaliacoes/atividade-03/`
- Este arquivo de especificação em Markdown (obrigatório).
- Código-fonte gerado a partir deste documento (implementação posterior).
- Evidência: print ou captura da execução com o nome do aluno visível na saída.
- Equipe: no máximo 3 componentes; cada um publica o documento no próprio GitHub.
- Não versionar `.class` (já cobertos pelo `.gitignore` da raiz).

### 5.5 Critérios de aceite para o harness

O código gerado está aceito se:

1. Compila sem erros.
2. Lê o arquivo de tarefas no formato da seção 5.1.
3. Implementa as transições da seção 3.1.
4. Oferece `rr` e `prioridade` sem alterar o núcleo.
5. Imprime log, Gantt e estatísticas.
6. Passa nos casos T1–T5 com as invariantes da seção 2.2.
7. Nomes de classes não abreviados.

---

## Apêndice A — Mapeamento livro → simulador

| Conceito (Tanenbaum, cap. 2) | Onde no simulador |
|---|---|
| Processo como CPU virtual | `CpuVirtual` + PCB com registradores |
| Fig. 2.2 estados e transições | Enum de estado + seção 3 |
| Fig. 2.4 tabela/PCB | Seção 2.1 |
| Interrupção de relógio | Tick + quantum |
| Surtos de CPU vs E/S (fig. 2.39) | Arquivo de tarefas |
| Quando escalonar (2.4.1) | Laço da seção 1.3 |
| Round robin e quantum (fig. 2.42) | Seção 4.2 |
| Prioridades e inanição (p. 110–111) | Seção 4.3 |
| `fork` / `exit` (2.1.2 e 2.1.3) | Seção 3.2 e 3.3 |
