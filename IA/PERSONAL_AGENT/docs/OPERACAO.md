# Regras de operação do PERSONAL_AGENT

Regras que o código não consegue garantir sozinho e que valem na estação do operador. Origem: R1 ampliada, fase 2
(`docs/plans/1.11-R1-ampliada.md` §9.8 e §9.9; `docs/entregas/1.11/r1_ampliada/fase2/decisao_c1.md` §4 e §8).

## 1. Coordenador local (porta 11434), residual R-d

O código só trata o coordenador como local quando o cliente aponta para `http://127.0.0.1:11434/v1` (ou `[::1]`),
criado pela fábrica `criar_cliente_coordenador_local()`, sem proxy de ambiente ou do sistema e sem seguir
redirecionamento (K5). Com o coordenador local, os dados do banco (sessões, SQL, planos) vão ao LLM. O que o código
não vê é para onde a porta 11434 leva. Por isso:

1. **O Ollama escuta só em loopback.** `OLLAMA_HOST` ausente ou `127.0.0.1`; nunca `0.0.0.0` nem IP de rede. No Docker,
   `-p 127.0.0.1:11434:11434`.
2. **Nenhum encaminhamento da 11434.** Sem `ssh -L` ou `-R`, sem `netsh interface portproxy`, sem túnel nem proxy
   reverso. Um encaminhamento em `127.0.0.1:11434` para outra máquina faria o tráfego com dados do banco sair da
   estação com o agente achando que é local.
   - Conferir: `netstat -ano | findstr :11434` mostra só `127.0.0.1` ou `[::1]` em LISTENING, pelo processo do Ollama;
   - `netsh interface portproxy show all` não lista a 11434.
3. **Proxy:** o cliente do coordenador local ignora `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` e o proxy do sistema
   (K5, `trust_env=False`). Isso não vale para os outros clientes HTTP do processo (o Gemini usa o proxy normalmente).
4. **Nome:** o coordenador usa o IP literal `127.0.0.1`, igual à sonda; o arquivo `hosts` e a resolução de `localhost`
   não mudam o destino.
5. **Variáveis:** nenhuma variável muda o destino do coordenador local (`OLLAMA_BASE_URL`, `OLLAMA_HOST` e
   `OPENAI_BASE_URL` não são lidos para isso).
6. Depois de mudar qualquer item acima, reiniciar a CLI ou a Web.

## 2. Encerramento de sessão (gate `OPS_KILL_PKG_VERSAO`)

- O encerramento de sessão só fica disponível com `OPS_KILL_PKG_VERSAO=2` **no ambiente da sessão** (shell), depois do
  `PKG_OPS_KILL` v2 instalado no banco. O gate não confirma a versão no banco (residual).
- No `.env`, a chave é **descartada** na carga, com aviso (D1). Definida no perfil do Windows, ela vale como ambiente:
  toda subida com o kill habilitado mostra o aviso "Encerramento de sessão HABILITADO nesta subida" (P4). Se o aviso
  aparecer sem intenção, remover a variável do perfil e reiniciar.
- Para desligar numa sessão: `OPS_KILL_PKG_VERSAO=0` (ou ausente) no shell antes de subir a CLI ou a Web.

## 3. Residuais aceitos (plano 9.8.3)

- **R-b:** os textos ao LLM não citam `OPS_KILL_AUDIT`; a auditoria fica no banco e no log local.
- **R-c:** o retorno das ferramentas de SO leva o tipo da exceção (por exemplo, `FileNotFoundError`), o que revela a
  existência ou não do caminho; o texto e o caminho vão só ao log local (K3). O disco só aceita raiz de unidade local
  (D3); uma letra mapeada para rede pelo próprio usuário ainda é consultada.
- **R-d:** a seção 1 deste documento.
