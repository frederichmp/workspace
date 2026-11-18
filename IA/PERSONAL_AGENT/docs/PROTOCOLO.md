# Protocolo de subagentes

## Instrução (sessão principal -> subagente)
T:<tarefa>  A:<arquivos permitidos>  R:<arquivo com a regra>  S:<campos de saída>

- T: identificador curto da tarefa (ex.: impl-item1).
- A: lista separada por vírgula. O agente não toca em arquivo fora dela.
- R: caminho de arquivo com a regra completa. O agente lê esse arquivo; não espera a regra na mensagem.
- S: campos da resposta, separados por vírgula (ex.: hash,diff_stat,pytest_n).

## Resposta (subagente -> sessão principal)
Uma linha:
- OK|hash|pytest_p/s/f|arquivos_n|arq:<caminho do detalhe>
- ERRO|etapa|motivo_curto|arq:<caminho do detalhe>

Detalhe (saída de teste, diff, greps) vai para arq, nunca para o chat.

## Regras
- Decisão de autorização (seguranca): instrução em prosa curta, com R: obrigatório. Sem código.
- Tarefa mecânica (mecanico, verificador): código T/A/R/S.
- Subagente novo por tarefa. Não reutilizar com SendMessage para outra tarefa.
- Se a instrução não tiver R: para o agente e pergunta.
