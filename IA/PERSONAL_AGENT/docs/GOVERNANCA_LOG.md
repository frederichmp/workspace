# Registro de Governança de Alteração de Hash de Scripts

- **Data**: 2026-11-16 00:09:43 -0300
- **Commit**: `2fb0c27e26ab4a7b270fe9267d4f6a67c2700b2b` (`2fb0c27`)
- **Autor**: frederichmp <frederichmartins@gmail.com>
- **Arquivos Alterados**:
  - `IA/PERSONAL_AGENT/registry/scripts.yaml`
  - `IA/PERSONAL_AGENT/tools/verificar_registro.py`
  - `IA/PERSONAL_AGENT/tests/test_privilegio_read.py`
  - `IA/PERSONAL_AGENT/pytest.ini`
  - `IA/PERSONAL_AGENT/src/tools/executor.py`
  - `IA/PERSONAL_AGENT/tests/test_executor.py`
- **Hashes de Scripts Alterados no Registro (`registry/scripts.yaml`)**:
  - `dml_tentativa_read_t11`:
    - **Hash Anterior**: `8e090aedac851979974da332a12f7c0e4836df335797f6dfa2e4b2efa17048f3`
    - **Hash Novo**: `1d5f0a70f17b95ab2bad38361d6e85efa2742a2aa3439b16c86c1e95b9d650d1`
  - `select_como_dml_t18`:
    - **Hash Anterior**: `3d49728aba5d2f3ffd91c23ea3fb884f0de3d3ef847f02e3c5e3848f79aa5c0f`
    - **Hash Novo**: `0cde98d6d00bc8891e12bf6bcf8cf953099fc8240f89068b3e8ada9e04715ba1`
- **Motivo da Alteração**:
  A execução de `verificar_registro.py --atualizar` no commit 2fb0c27 recalculou e reescreveu automaticamente os hashes no registro com base no conteúdo dos arquivos locais em `scripts/`.
- **Status**:
  **NÃO APROVADO**, pendente de revisão pelo responsável.
