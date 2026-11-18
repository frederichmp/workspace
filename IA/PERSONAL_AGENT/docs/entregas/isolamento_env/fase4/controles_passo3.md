# Controles do Passo 3 (fase 4, Achado 4)

Sessão principal (claude-opus-5-5). Cópia de HEAD f5692f0 (rag_search.py = b0ce169, conferido com git diff --quiet), .env só de sentinela, sem ORACLE_SANDBOX.

```
E       AssertionError: DotEnv construído com caminho durante _obter_vectorstore: ['.env']
E       assert ['.env'] == []
FAILED tests/test_rag_search_env.py::test_obter_vectorstore_nao_le_env - Asse...
1 failed, 1 passed, 16 warnings in 3.73s
== mutacao env_file=None
FAILED tests/test_rag_search_env.py::test_obter_vectorstore_nao_le_env - Asse...
1 failed, 1 passed, 16 warnings in 4.24s
```

- Controle direto (rag_search de b0ce169): test_obter_vectorstore_nao_le_env falha com 1 DotEnv('.env').
- Mutação I2 (env_file=None, a sugestão do Gemini): mesma falha; a forma sem sublinhado é ignorada pelo pydantic-settings.
- test_contador_ve_o_env_do_diretorio_corrente passa nas três bases (controle do próprio teste).
- Depois da verificação (verificacao_passo3.md, item 2(a)), só o comentário de rag_search.py mudou, para o grep 'env_file=None' dar 1 linha.
