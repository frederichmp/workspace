# Design dos Payloads de Dados (Edge Filtering)

Para preservar a janela de contexto de 8k tokens do Qwen 2.5 local e manter o tempo de resposta abaixo de 5 segundos, todas as ferramentas (*tools*) Python aplicam o princípio de **Filtro na Borda (Edge Filtering)**:
- Agregações (`GROUP BY`) e limites (`FETCH FIRST 3 ROWS ONLY` / `Top N`) acontecem no SO ou no Banco de Dados.
- Pré-cálculo de flags booleanas e alertas no Python para poupar raciocínio aritmético do LLM.

---

## 1. Payload de SO e Hardware (~150 tokens)

### Hardware Base (`coleta: "hardware_base"`)
```json
{
  "status": "sucesso",
  "coleta": "hardware_base",
  "dados": {
    "cpu_percentual": 12.5,
    "ram_total_gb": 32.0,
    "ram_usada_gb": 18.2,
    "ram_livre_gb": 13.8,
    "ram_percentual": 56.8
  }
}
```

### Disco Local (`coleta: "disco_local"`)
```json
{
  "status": "sucesso",
  "coleta": "disco_local",
  "dados": {
    "unidade": "C:\\",
    "total_gb": 1024.0,
    "livre_gb": 145.5,
    "percentual_usado": 85.7,
    "alerta_capacidade": true
  }
}
```

---

## 2. Payload de Banco de Dados: Health Check Inicial (~300 tokens)

```json
{
  "status": "sucesso",
  "instancia": "PRDMV",
  "metricas_globais": {
    "sessoes_ativas": 42,
    "bloqueios_ativos": 1,
    "top_wait_event": "enq: TX - row lock contention"
  },
  "top_3_ofensores": [
    {
      "sid_serial": "1045,59302",
      "usuario": "APP_SISTEMA",
      "sql_id": "8m4x7b9q2zv1c",
      "evento_espera": "enq: TX - row lock contention",
      "tempo_espera_segundos": 1450,
      "status_bloqueador": "Bloqueando 1 sessão"
    }
  ]
}
```

---

## 3. Payload de Plano de Execução / DBMS_XPLAN (~400 tokens)

```json
{
  "status": "sucesso",
  "sql_id": "8m4x7b9q2zv1c",
  "plan_hash_value": "392817392",
  "custo_total": 85400,
  "alerta_arquitetura": "Encontrado alto custo e varredura total.",
  "operacoes_criticas": [
    {
      "id_operacao": 4,
      "tipo": "TABLE ACCESS FULL",
      "objeto": "NOTAS_FISCAIS_ENT",
      "custo": 82000,
      "linhas_estimadas": 15000000
    }
  ],
  "plano_truncado_para_ia": true
}
```
