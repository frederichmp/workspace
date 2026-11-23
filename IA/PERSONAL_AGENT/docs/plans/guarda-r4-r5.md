# Plano: R4 também no shell e R5 para a fiação do guarda (`guarda-r4-r5`)

## 1. Contexto

**Pedido do responsável (2026-11-19):** fechar as lacunas 1 a 3 da validação das regras dos agentes, feita só por leitura nesta sessão.
1. **R4 só em Write e Edit.** Em `tools/guarda_agentes.py:304-321`, `Bash` e `PowerShell` retornam antes da checagem de pasta, então o `seguranca` e o `verificador` gravam em qualquer lugar por redirecionamento ou cmdlet.
2. **O `mecanico` não tem trava mecânica de arquivo.** O guarda só aplica R2 e R3 a ele.
3. **`.claude/agents/*.md` e `.claude/settings*.json` estão fora do mapa do §2.** A fiação do hook e os limites dos agentes não passam pela regra "só Opus".

**Decisões do responsável (2026-11-19):**
- Lacuna 1: heurística no guarda mais ajuste de texto. Gravação por interpretador (`python -c`, script) fica como residual aceito, detectado pelo `git status` (L12).
- Lacunas 2 e 3: só a fiação do guarda, com R5. Nenhum subagente grava em `.claude/**` nem em `tools/guarda_agentes.py`, nem com autorização literal: é uma exceção à regra do CLAUDE.md, só para esses caminhos. O resto do §2 continua por prompt e revisão do diff. `.claude/` entra no mapa do §2.

**Fora deste plano, já anotados na validação:**
- modelo padrão Sonnet em `.claude/settings.json`;
- modelo informado pelo agente, que se confirma na transcrição.

## 2. Base
- Branch `main`, HEAD `011e023`, árvore rastreada limpa.
- Baseline: 614 passed e 16 skipped (última linha do `docs/GOVERNANCA_LOG.md`).
- Modelo da sessão: claude-opus-5-5. O código é do §2, então só Opus o escreve.
- Não rastreados previstos: `docs/_tmp/`, `docs/plans/1.11-item1-B-refeito.md`, `docs/entregas/**` de tarefas anteriores e `docs/entregas/guarda-r4-r5/`.

## 3. Desenho

### D1. R4 no shell (`seguranca` e `verificador`)
Uma função pura, `destinos_de_gravacao(comando) -> list[str] | None`, extrai os destinos das formas comuns:
- Bash: `>`, `>>`, `>|`, `&>`, `1>`, `tee [-a]`, `cp`, `mv`, `rm`, `mkdir`, `touch`, `sed -i`, `dd of=`, `truncate`.
- PowerShell: `Out-File`, `Set-Content`, `Add-Content`, `New-Item`, `Copy-Item`, `Move-Item`, `Remove-Item`, `Rename-Item`, `Clear-Content`, `[IO.File]::Write*`, `Tee-Object`, e os aliases `ni`, `cpi`, `mi`, `ri`, `del`, `sc`, `ac`.

A regra aplica os destinos assim:
- Liberados: `/dev/null`, `$null`, `NUL`, `2>&1` e `>&2`.
- Só nos perfis `seguranca` e `verificador`, destino fora de `docs/entregas/` e fora da pasta temporária (`tempfile.gettempdir()`, onde fica o scratchpad) é bloqueado como R4.
- Falha fechado: destino com `$`, `%`, crase ou `~`, sem o caminho expandido, também é bloqueado (L27).
- Reaproveita `sem_comentarios`, `_tokens`, `_abs` e `dentro_de`.

O `verificacao_padrao.py` e o `controle_mutacao.py` gravam por Python, então continuam passando.

### D2. R5, a fiação do guarda (todos os perfis)
Gravação em `.claude/**` ou em `tools/guarda_agentes.py` é bloqueada como R5 em todo perfil. Vale para:
- Write e Edit;
- os destinos de D1 em Bash e PowerShell.

O caminho é resolvido por `_abs`, o que pega também `IA/PERSONAL_AGENT/.claude` e o estilo `/c/...` do Git Bash.

### D3. Mapa e textos
- `docs/PROCESSO.md` §2 ganha a linha "Definição dos agentes e hooks": `.claude/agents/*.md`, `.claude/settings*.json`.
- §3 ganha R4 no shell, o R5 e os residuais.
- O `.claude/agents/mecanico.md` recebe a lista do §2 atualizada e a menção ao R5.
- `seguranca.md` e `verificador.md` passam a dizer o que o guarda cobre. Gravação por interpretador fica como regra de prompt, detectada pelo `git status`.
- "Junte comandos independentes" ganha a ressalva da L37.

## 4. Arquivos e passos

| Passo | Quem (modelo) | Arquivos |
|---|---|---|
| 0 | sessão principal (Opus) | `docs/plans/guarda-r4-r5.md` (cópia deste plano), `docs/entregas/guarda-r4-r5/levantamento.md` |
| 1 | `seguranca` (opus, xhigh) | `docs/entregas/guarda-r4-r5/decisao.md` |
| 2 | sessão principal (Opus) | `tests/test_guarda_agentes.py`, `tools/guarda_agentes.py` |
| 3 | sessão principal (Opus) | os mesmos dois |
| 4 | sessão principal | `docs/entregas/guarda-r4-r5/mutacoes.json` e as saídas |
| 5 | `seguranca` (opus, high) | `docs/entregas/guarda-r4-r5/conferencia.md` |
| 6 | sessão principal (Opus) | `docs/PROCESSO.md`, `.claude/agents/{mecanico,seguranca,verificador}.md` |
| 7 | `verificador` (haiku) | `docs/entregas/guarda-r4-r5/` |
| 8 | sondas (`verificador`, `mecanico`) | `docs/entregas/guarda-r4-r5/sondas.md` |
| 9 | sessão principal | `docs/GOVERNANCA_LOG.md`, `docs/PROCESSO.md` §7 |

Tudo em sequência, sem agentes em paralelo (L35). Nenhum agente roda durante o `/plan` (L19).

0. **Levantamento (só leitura).** Nas transcrições `~/.claude/projects/<projeto>/*.jsonl`, listo os comandos Bash e PowerShell dos subagentes que gravam por shell, com destino e perfil. Assim D1 não barra uso legítimo; o critério de ausência segue a L25. Resumo em `levantamento.md`.
1. **Decisão do `seguranca`.** Ele ataca D1 e D2:
   - aspas e escape;
   - here-string;
   - `cmd /c`, `bash -c` e `powershell -c` aninhados;
   - `-FilePath` e `-Path` posicional;
   - pipe para `tee`;
   - link e 8.3 (residual já aceito);
   - Edit de `.claude/settings.local.json`.

   Ele também lista os residuais. Se o veredito for NÃO CONFORME ou PENDENTE, volto ao responsável antes do passo 2.
2. **R4 no shell.** Os testes vêm primeiro e devem falhar no HEAD (controle negativo):
   - parametrizados de destino liberado e bloqueado por perfil;
   - `mecanico` livre de R4;
   - `$null` e `2>&1` liberados;
   - destino com `$VAR` bloqueado.

   Depois implemento D1, rodo `tests/test_guarda_agentes.py` e a suíte uma vez.
   Commit: `fix(tools): guarda aplica o R4 tambem em Bash e PowerShell`.
3. **R5.** Os testes vêm primeiro:
   - Write, Edit e shell em `.claude/agents/x.md`, `.claude/settings.json` e `tools/guarda_agentes.py`, bloqueados nos três perfis;
   - leitura desses caminhos liberada.

   Depois implemento D2.
   Commit: `fix(tools): guarda bloqueia gravacao na fiacao do guarda (R5)`.
4. **Controle de mutação.** Uso `python -I tools/controle_mutacao.py --tarefa guarda-r4-r5 --rotulo mut --alvo tools/guarda_agentes.py --teste tests/test_guarda_agentes.py`, rodado antes de cada commit, sobre o arquivo daquele passo. Cada mutação deve dar DETECTADA:
   - m1: tira a chamada de R4 no shell;
   - m2: libera todo destino;
   - m3: tira o R5 de Write e Edit;
   - m4: tira o R5 do shell;
   - m5: deixa de tratar `$` como não expandido.
5. **Conferência do `seguranca`** sobre o diff dos passos 2 e 3. Se não vier CONFORME, nada segue.
6. **Textos de D3.** O YAML do frontmatter é validado com PyYAML (L11).
   Commit: `docs: R4 no shell, R5 e .claude no mapa do PROCESSO e nos agentes`.
7. **Verificação**, pela seção 6.
8. **Sondas ao vivo**, uma chamada por comando (L37). Grava com Write o texto que cita comando barrado (L39).
   - `verificador`: `echo x > docs/entregas/guarda-r4-r5/sonda_ok.txt` liberado; `echo x > sonda_fora.txt` bloqueado (R4).
   - `mecanico`: Write em `.claude/sonda_r5.txt` bloqueado (R5); Write em `docs/entregas/guarda-r4-r5/sonda_mec.txt` liberado.

   Arquivo de sonda que vazar, a sessão principal apaga e registra.
9. **Registro.** Linha no GOVERNANCA_LOG e lições novas no §7.
   Commit: `docs: registra guarda-r4-r5 no GOVERNANCA_LOG e licoes`.

Todo commit traz `git diff` mostrado, caminhos explícitos e `Co-Authored-By: Claude Opus 5.5`. Sem `git push`.

## 5. Decisões do responsável
- **Aprovadas (2026-11-19):** D1 com heurística mais texto; D2 só para a fiação (`.claude/**`, `tools/guarda_agentes.py`), como exceção à autorização literal.
- **Pendentes, se o `seguranca` levantar:** aceitar novos residuais de D1, por exemplo shell aninhado ou alias não listado.
- **Aprovadas depois do passo 1 (2026-11-19), sobre `docs/entregas/guarda-r4-r5/decisao.md` §9:**
  - **A1, entra neste plano como 1º commit.** No PowerShell, `\` com quebra de linha burla o R1 e o R2. A sessão principal confirmou com o S1: `gs.decidir` devolve `False` para `git commit` e para `grep -rn` na linha seguinte, e o controle sem a barra devolve `True`. A correção junta a continuação por dialeto, `\` só no Bash e crase só no PowerShell, com o teste S1 e uma mutação. Passo 1b, com o commit `fix(tools): guarda junta continuacao de linha por dialeto`.
  - **N8, R5 estendido ao interpretador do hook:** `sitecustomize.py`, `usercustomize.py`, `*.pth` sob `site-packages`, executáveis `python*` e `py` (`.exe`, `.bat`, `.cmd`, `.ps1`), e as pastas `sys.prefix` e `sys.base_prefix`.
  - **N7, hash antes e depois de cada delegação** de `.claude/**` do projeto e de `~/.claude/agents/**` e `~/.claude/settings*.json`. Entra no PROCESSO §3 no passo 6. O S2 confirmou que `.claude/settings.local.json` é ignorado (`.gitignore:37`).
  - **N1 e N6 aceitos como residuais:**
    - N1: programas que gravam por opção própria fora da lista, e alias ou função definidos fora do comando;
    - N6: no `mecanico`, destino não resolvido sem menção textual à fiação.
  - **Decisões do `seguranca` que só apertam o bloqueio**, adotadas:
    - R5 em qualquer `.claude`, inclusive o de `<HOME>`;
    - R5 antes do R4;
    - `NOME_DECISAO` no shell do `seguranca`;
    - `realpath` no R4 do Write e do Edit;
    - bloqueio quando a pasta temporária se sobrepõe à raiz.
- **Escopo reduzido e fechado (2026-11-19).** O responsável recusou o parser completo do `decisao.md` §2 a §6, estimado em 1.000 a 1.500 linhas. A referência continua sendo o `decisao.md`, e o que fica é:
  - A1;
  - R5 completo em Write, Edit e ferramenta desconhecida, com o N8;
  - no shell, um lexer simples por dialeto: aspas, redirecionamento, heredoc e here-string descartados, e as formas comuns de gravação;
  - variável só do prefixo de atribuições literais, e `cd` só com alvo literal.

- **Depois da conferência do passo 5 (2026-11-23):** veio NÃO CONFORME, com 16 classes D1 a D16 em `conferencia.md`. A sessão principal confirmou todas no HEAD `83a5aa2` e nos shells reais (`experimento_shell.md`). Decisões do responsável:
  - R1: `robocopy` e `xcopy` entram na lista de utilitários que gravam, com o 2º posicional como destino recursivo.
  - R2: o N1 **não** se estende à divergência de parser; divergência achada é defeito.

  As correções P1 a P11 da conferência e o R1 entram como commit próprio (passo 5b), com testes que falham no HEAD e mutações. Depois, nova conferência do `seguranca` sobre o diff do passo 5b.
- **Depois da reconferência do passo 5b (2026-11-23):** veio NÃO CONFORME. D1 a D16 fecharam, mas surgiram as famílias E1 a E15 (`conferencia_5b.md`), cada vez mais deliberadas. O responsável decidiu pelo critério **acidente contra evasão**, coerente com o PROCESSO §3 ("guarda contra acidente, não sandbox"):
  - **Fecham-se no passo 5c os E plausíveis por acidente:**
    - E2: `cd x && y &`;
    - E5: `| bash` e `pwsh -c -`;
    - E10: `-D` e `-N` ambíguos;
    - E11: vírgula com espaço;
    - E12: `timeout` e `stdbuf` com opção;
    - E13: robocopy com `//E`, `/MOVE` e `/LOG:`;
    - E14: ferramenta com `destination`, `append` ou `put`.
  - **Viram residual "evasão deliberada"** E1, E3, E4, E6, E7, E8, E9 e E15. A detecção é o `git status` e o hash da fiação (N7).
  - A conferência seguinte julga por esse critério.
  O que for complexo bloqueia: shell aninhado, `eval` e `iex`, `xargs` e `-exec`, `cmd /c`, splat, `$(` ou crase no destino, aspas abertas. No `seguranca` e no `verificador`, isso é bloqueio R4. No `mecanico`, é R5 quando o texto cita a fiação. Os testes são um subconjunto dos casos L, B e F, as mutações são um subconjunto da m1 à m22, e o falso positivo é aceito.

## 6. Verificação
```bash
python -I tools/verificacao_padrao.py --tarefa guarda-r4-r5 --base 011e023 --esperado <614+N>/16 \
  --previsto 'docs/plans/guarda-r4-r5.md'
```
O N é a contagem de testes novos, informada exata no pedido. A verificação roda depois dos commits, com a árvore rastreada limpa.

Checagens próprias do plano:
- `git diff --stat 011e023 -- registry/ db/ src/ app.py` vazio;
- `git diff --name-only 011e023` igual à lista da seção 4;
- PyYAML faz parse dos três frontmatters;
- `grep -n "R5" .claude/agents/*.md docs/PROCESSO.md` com ao menos uma linha por arquivo.

## 7. GOVERNANCA_LOG (linha prevista)
`2026-11-19 | <commits> | frederichmp | tools/guarda_agentes.py, tests/test_guarda_agentes.py, docs/PROCESSO.md (§2, §3, §7), .claude/agents/*.md, docs/plans/guarda-r4-r5.md | Guarda: R4 no shell e R5 para a fiação | <detalhe do §6 do PROCESSO> | aguardando revisão`

## 8. Fora de escopo
- Trava de arquivo do `mecanico` no resto do §2: decidida "só a fiação".
- Gravação por interpretador (`python -c`, script): residual, detectado pelo `git status`.
- Modelo padrão em `.claude/settings.json`.
