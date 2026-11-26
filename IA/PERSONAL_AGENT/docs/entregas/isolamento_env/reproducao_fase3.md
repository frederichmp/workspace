# Reprodução fase 3 — isolamento-env (passo 0, só leitura)

- Data de execução: 2026-11-18 13:32:59 até 13:33:26
- Modelo: claude-haiku-5-5
- Branch: isolamento-env; HEAD: ba598f0
- Fonte dos achados: docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md (B4, C1, A3)
- Versões: Python 3.15.2; streamlit 1.67.0; python-dotenv 1.2.4; openai 3.51.0
- Baseline da suíte: 199 passed, 16 skipped (não executada neste passo, conforme pedido).
- ORACLE_SANDBOX no processo de execução: antes=False, depois=False (presença; deve ser False).

## 1. Veredito por achado

| Achado | Cenário | Esperado se reproduz | Obtido | Veredito |
|---|---|---|---|---|
| B4 | Web (AppTest, rerun) | ORACLE_USER_KILL ausente após run1 e presente após run2 | run1=None; run2='kill_tardio_ficticio' | **REPRODUZ** |
| B4 | CLI (import main, sem rerun) | nada recarrega após alterar o .env | run1=None; após alterar=None; chamadas=1 | **CONFIRMADO: sem recarga (registro)** |
| C1 | load_dotenv mínimo (stream) | exceção e FOO_FIRST já em os.environ | excecao=ValueError: embedded null character; FOO_FIRST em environ=True | **REPRODUZ** |
| C1 | Web (AppTest, 2 reruns) | ORACLE_SANDBOX=1 permanece após run1 e/ou run2 sem WARNING DESCARTADA | run1: exc=['embedded null character'], ORACLE_SANDBOX='1', avisos=[] / run2: exc=['embedded null character'], ORACLE_SANDBOX='1', avisos=[] | **REPRODUZ** |
| C1 | CLI (import main) | exceção e ORACLE_SANDBOX=1 permanece em os.environ | excecao=ValueError: embedded null character; ORACLE_SANDBOX='1'; avisos=[] | **REPRODUZ** |
| A3 | CLI (src.tools.oracle_dba importado antes de main) | DIRETORIO e GEMINI_API_KEY iguais nas duas cópias | dir_iguais=False, key_iguais=False, src_key_vazia=True, tools_key_vazia=False / src antes da carga=['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search'] | **REPRODUZ** |
| A3 | Web (src.tools.oracle_dba importado antes do AppTest) | DIRETORIO e GEMINI_API_KEY iguais nas duas cópias | dir_iguais=False, key_iguais=False, src_key_vazia=True, tools_key_vazia=False / src antes da carga=['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search'] | **REPRODUZ** |
| A3 | CLI (só import main, ordem de produção) | uma só cópia, sem divergência | dir_iguais=True, key_iguais=True, src_key_vazia=False, tools_key_vazia=False / src antes da carga=[] | **NÃO REPRODUZIDO** |
| A3 | Web (só AppTest, ordem de produção) | uma só cópia, sem divergência | dir_iguais=True, key_iguais=True, src_key_vazia=False, tools_key_vazia=False / src antes da carga=[] | **NÃO REPRODUZIDO** |

## 2. Passo 0 e git status

Passo 0 (executado antes do driver, comando do PROCESSO §5, só nomes): `passo0_linhas=0` (nenhum nome com ORACLE_, EMAIL_, GEMINI_, AGENTDBA_ ou SCRIPTS_ no HKCU/HKLM). `ORACLE_SANDBOX` do shell: vazio.

**git status --short -- . ANTES (linhas fora do previsto: 0)**

```text
?? db/ops_kill.sqlbkp
?? docs/entregas/1.11/item1/abc/
?? docs/entregas/1.11/item1/diff_producao.diff
?? docs/entregas/1.11/item1/diff_revisao_gemini.diff
?? docs/entregas/1.11/item1/diff_testes.diff
?? docs/entregas/1.11/item1/diff_tests.txt
?? docs/entregas/1.11/item1/greps.txt
?? docs/entregas/1.11/item1/o1o2/
?? docs/entregas/1.11/item1/pytest_run1.txt
?? docs/entregas/1.11/item1/pytest_run2.txt
?? docs/entregas/1.11/item1/revisao_adversarial_gemini.md
?? docs/entregas/1.11/item1/verificacao.md
?? docs/entregas/processo-subagentes/
?? docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md
?? docs/plans/1.11-item1-B-refeito.md

Fora do previsto: []
Previstos ausentes: []
```

**git status --short -- . DEPOIS da execução e antes de gravar este relatório (fora do previsto: 0)**

```text
?? db/ops_kill.sqlbkp
?? docs/entregas/1.11/item1/abc/
?? docs/entregas/1.11/item1/diff_producao.diff
?? docs/entregas/1.11/item1/diff_revisao_gemini.diff
?? docs/entregas/1.11/item1/diff_testes.diff
?? docs/entregas/1.11/item1/diff_tests.txt
?? docs/entregas/1.11/item1/greps.txt
?? docs/entregas/1.11/item1/o1o2/
?? docs/entregas/1.11/item1/pytest_run1.txt
?? docs/entregas/1.11/item1/pytest_run2.txt
?? docs/entregas/1.11/item1/revisao_adversarial_gemini.md
?? docs/entregas/1.11/item1/verificacao.md
?? docs/entregas/processo-subagentes/
?? docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md
?? docs/plans/1.11-item1-B-refeito.md

Fora do previsto: []
Previstos ausentes: []
```

## 3. Método

- Cada cenário é um subprocesso `python -B filho.py ficticio.env`, com cwd na raiz do projeto.
- env do subprocesso = os.environ sem chaves ORACLE_, EMAIL_, GEMINI_, AGENTDBA_; acrescentado só o que o cenário pede (valores fictícios): AGENTDBA_LOG_DIR (temp, fora de A3), SCRIPTS_REGISTRY_PATH (como no modelo tests/test_carga_env_entrada.py) e PYTHONDONTWRITEBYTECODE=1.
- `ORACLE_SANDBOX=1` aparece somente dentro do .env fictício de C1 (Web e CLI).
- dotenv.load_dotenv é substituído por wrapper que chama o original com o .env fictício em TMP; o .env real nunca é aberto. O wrapper registra o caminho pedido pelo app.
- Handler de captura no logger raiz (INFO): basicConfig vira no-op. Nenhum FileHandler de execução.
- socket.create_connection levanta OSError (sem rede).
- A3 (ordem de produção): só `import main` ou só AppTest, sem pré-import; a instrumentação registra src.tools.* em sys.modules no momento de cada chamada de load_dotenv.

## 4. Saídas brutas por execução

### c1_min

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_min\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_min\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): []
- Chaves com prefixo proibido passadas ao subprocesso (nomes): []
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b''`
- .env fictício depois (repr): `b''`

**stdout**

```text
C1 min | excecao = ValueError: embedded null character
C1 min | FOO_FIRST em os.environ = True
RESULTADO_JSON={"excecao": "ValueError: embedded null character", "foo_first_em_environ": true}

```

**stderr**

```text
(vazio)
```

### b4_web

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\b4_web\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\b4_web\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['AGENTDBA_LOG_DIR', 'SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): ['AGENTDBA_LOG_DIR']
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'SENTINELA_FASE3=1\n'`
- .env fictício depois (repr): `b'SENTINELA_FASE3=1\nORACLE_USER_KILL=kill_tardio_ficticio\r\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
B4 web | apos run1 | os.environ ORACLE_USER_KILL = None | excecoes = []
B4 web | apos run2 | os.environ ORACLE_USER_KILL = kill_tardio_ficticio | excecoes = []
B4 web | chamadas de load_dotenv = 2
RESULTADO_JSON={"run1": null, "run2": "kill_tardio_ficticio", "e1": [], "e2": [], "chamadas": 2}

```

**stderr**

```text
2026-11-18 13:33:00.120 WARNING streamlit.runtime.scriptrunner_utils.script_run_context: Thread 'MainThread': missing ScriptRunContext! This warning can be ignored when running in bare mode.

```

### b4_cli

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\b4_cli\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\b4_cli\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['AGENTDBA_LOG_DIR', 'SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): ['AGENTDBA_LOG_DIR']
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'SENTINELA_FASE3=1\n'`
- .env fictício depois (repr): `b'SENTINELA_FASE3=1\nORACLE_USER_KILL=kill_tardio_ficticio\r\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
B4 cli | apos import main | os.environ ORACLE_USER_KILL = None
B4 cli | apos alterar o ficticio (sem rerun) | os.environ ORACLE_USER_KILL = None
B4 cli | chamadas de load_dotenv = 1
RESULTADO_JSON={"run1": null, "run2": null, "chamadas": 1}

```

**stderr**

```text
(vazio)
```

### c1_web

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_web\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_web\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['AGENTDBA_LOG_DIR', 'SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): ['AGENTDBA_LOG_DIR']
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'ORACLE_SANDBOX=1\nSENTINELA_C1=abc\x00def\n'`
- .env fictício depois (repr): `b'ORACLE_SANDBOX=1\nSENTINELA_C1=abc\x00def\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
────────────────────────── Traceback (most recent call last) ───────────────────────────
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\streaml  
  it\runtime\scriptrunner\exec_code.py:136 in exec_func_with_error_handling             
                                                                                        
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\streaml  
  it\runtime\scriptrunner\script_runner.py:936 in code_to_exec                          
                                                                                        
  c:\Users\<usuario>\OneDrive - <organizacao> -                         
  EPP\Workspace\IA\PERSONAL_AGENT\app.py:39 in <module>                                 
                                                                                        
     36 # ORACLE_SANDBOX só vale se definida pelo operador no shell (incidente 01:27):  
     37 # descartada aqui; o WARNING sai depois do logging.basicConfig (antes dele, a   
     38 _ORACLE_SANDBOX_DO_SHELL = "ORACLE_SANDBOX" in os.environ                       
  >  39 load_dotenv(ROOT_DIR / ".env", override=False)                                  
     40 _ORACLE_SANDBOX_DESCARTADA = False                                              
     41 if not _ORACLE_SANDBOX_DO_SHELL and "ORACLE_SANDBOX" in os.environ:             
     42 │   del os.environ["ORACLE_SANDBOX"]                                            
                                                                                        
  C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_web\filho.py:17 in _wrapper  
                                                                                        
    14 │   │   "src_tools_antes_da_carga": sorted(m for m in sys.modules if m.startswi  
    15 │   })                                                                           
    16 │   kwargs.setdefault("override", False)                                         
  > 17 │   return _ORIGINAL(ENV_FICTICIO, *args, **kwargs)                              
    18 dotenv.load_dotenv = _wrapper                                                    
    19 CAPTURA = []                                                                     
    20 class _Captura(logging.Handler):                                                 
                                                                                        
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\dotenv\  
  main.py:435 in load_dotenv                                                            
                                                                                        
    432 │   │   override=override,                                                      
    433 │   │   encoding=encoding,                                                      
    434 │   )                                                                           
  > 435 │   return dotenv.set_as_environment_variables()                                
    436                                                                                 
    437                                                                                 
    438 def dotenv_values(                                                              
                                                                                        
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\dotenv\  
  main.py:108 in set_as_environment_variables                                           
                                                                                        
    105 │   │   │   if k in os.environ and not self.override:                           
    106 │   │   │   │   continue                                                        
    107 │   │   │   if v is not None:                                                   
  > 108 │   │   │   │   os.environ[k] = v                                               
    109 │   │                                                                           
    110 │   │   return True                                                             
    111                                                                                 
  in __setitem__:735                                                                    
────────────────────────────────────────────────────────────────────────────────────────
ValueError: embedded null character
C1 web | run1 | excecoes = ['embedded null character']
C1 web | run1 | os.environ ORACLE_SANDBOX = 1
C1 web | run1 | avisos DESCARTADA = []
────────────────────────── Traceback (most recent call last) ───────────────────────────
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\streaml  
  it\runtime\scriptrunner\exec_code.py:136 in exec_func_with_error_handling             
                                                                                        
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\streaml  
  it\runtime\scriptrunner\script_runner.py:936 in code_to_exec                          
                                                                                        
  c:\Users\<usuario>\OneDrive - <organizacao> -                         
  EPP\Workspace\IA\PERSONAL_AGENT\app.py:39 in <module>                                 
                                                                                        
     36 # ORACLE_SANDBOX só vale se definida pelo operador no shell (incidente 01:27):  
     37 # descartada aqui; o WARNING sai depois do logging.basicConfig (antes dele, a   
     38 _ORACLE_SANDBOX_DO_SHELL = "ORACLE_SANDBOX" in os.environ                       
  >  39 load_dotenv(ROOT_DIR / ".env", override=False)                                  
     40 _ORACLE_SANDBOX_DESCARTADA = False                                              
     41 if not _ORACLE_SANDBOX_DO_SHELL and "ORACLE_SANDBOX" in os.environ:             
     42 │   del os.environ["ORACLE_SANDBOX"]                                            
                                                                                        
  C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_web\filho.py:17 in _wrapper  
                                                                                        
    14 │   │   "src_tools_antes_da_carga": sorted(m for m in sys.modules if m.startswi  
    15 │   })                                                                           
    16 │   kwargs.setdefault("override", False)                                         
  > 17 │   return _ORIGINAL(ENV_FICTICIO, *args, **kwargs)                              
    18 dotenv.load_dotenv = _wrapper                                                    
    19 CAPTURA = []                                                                     
    20 class _Captura(logging.Handler):                                                 
                                                                                        
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\dotenv\  
  main.py:435 in load_dotenv                                                            
                                                                                        
    432 │   │   override=override,                                                      
    433 │   │   encoding=encoding,                                                      
    434 │   )                                                                           
  > 435 │   return dotenv.set_as_environment_variables()                                
    436                                                                                 
    437                                                                                 
    438 def dotenv_values(                                                              
                                                                                        
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\dotenv\  
  main.py:108 in set_as_environment_variables                                           
                                                                                        
    105 │   │   │   if k in os.environ and not self.override:                           
    106 │   │   │   │   continue                                                        
    107 │   │   │   if v is not None:                                                   
  > 108 │   │   │   │   os.environ[k] = v                                               
    109 │   │                                                                           
    110 │   │   return True                                                             
    111                                                                                 
  in __setitem__:735                                                                    
────────────────────────────────────────────────────────────────────────────────────────
ValueError: embedded null character
C1 web | run2 | excecoes = ['embedded null character']
C1 web | run2 | os.environ ORACLE_SANDBOX = 1
C1 web | run2 | avisos DESCARTADA = []
C1 web | chamadas de load_dotenv = 2
RESULTADO_JSON={"e1": ["embedded null character"], "s1": "1", "d1": [], "e2": ["embedded null character"], "s2": "1", "d2": [], "chamadas": 2}

```

**stderr**

```text
2026-11-18 13:33:08.253 WARNING streamlit.runtime.scriptrunner_utils.script_run_context: Thread 'MainThread': missing ScriptRunContext! This warning can be ignored when running in bare mode.

```

### c1_cli

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_cli\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\c1_cli\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['AGENTDBA_LOG_DIR', 'SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): ['AGENTDBA_LOG_DIR']
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'ORACLE_SANDBOX=1\nSENTINELA_C1=abc\x00def\n'`
- .env fictício depois (repr): `b'ORACLE_SANDBOX=1\nSENTINELA_C1=abc\x00def\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
C1 cli | excecao no import de main = ValueError: embedded null character
C1 cli | os.environ ORACLE_SANDBOX = 1
C1 cli | avisos DESCARTADA = []
C1 cli | chamadas de load_dotenv = 1
RESULTADO_JSON={"excecao": "ValueError: embedded null character", "s1": "1", "d1": [], "chamadas": 1}

```

**stderr**

```text
(vazio)
```

### a3a_cli

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3a_cli\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3a_cli\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): []
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`
- .env fictício depois (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
A3a cli | src.tools.* em sys.modules antes do import main = ['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search']
A3a cli | ausentes em sys.modules = []
A3a cli | src.tools.* / tools.* em sys.modules ao fim = ['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search', 'tools.gemini_router', 'tools.notificador', 'tools.oracle_dba', 'tools.os_tools', 'tools.rag_search']
A3a cli | src.tools.oracle_dba.__file__ = c:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3a cli | tools.oracle_dba.__file__ = C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3a cli | src.tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\AgentDBA\logs
A3a cli | tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\dir_env_a3
A3a cli | DIRETORIO_LOG_APROVACAO iguais = False
A3a cli | src.tools.gemini_router.GEMINI_API_KEY vazia = True
A3a cli | tools.gemini_router.GEMINI_API_KEY vazia = False
A3a cli | GEMINI_API_KEY iguais = False
A3a cli | objetos de modulo distintos = True
A3a cli | chamadas de load_dotenv = 1
RESULTADO_JSON={"out": {"ausentes": [], "dir_iguais": false, "key_iguais": false, "src_key_vazia": true, "tools_key_vazia": false}, "chamadas": 1, "src_antes_carga": ["src.tools", "src.tools.gemini_router", "src.tools.notificador", "src.tools.oracle_dba", "src.tools.os_tools", "src.tools.payloads", "src.tools.rag_search"]}

```

**stderr**

```text
(vazio)
```

### a3a_web

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3a_web\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3a_web\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): []
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`
- .env fictício depois (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
A3a web | src.tools.* em sys.modules antes do AppTest = ['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search']
A3a web | excecoes = []
A3a web | ausentes em sys.modules = []
A3a web | src.tools.* / tools.* em sys.modules ao fim = ['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search', 'tools.gemini_router', 'tools.notificador', 'tools.oracle_dba', 'tools.os_tools', 'tools.rag_search']
A3a web | src.tools.oracle_dba.__file__ = c:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3a web | tools.oracle_dba.__file__ = C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3a web | src.tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\AgentDBA\logs
A3a web | tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\dir_env_a3
A3a web | DIRETORIO_LOG_APROVACAO iguais = False
A3a web | src.tools.gemini_router.GEMINI_API_KEY vazia = True
A3a web | tools.gemini_router.GEMINI_API_KEY vazia = False
A3a web | GEMINI_API_KEY iguais = False
A3a web | objetos de modulo distintos = True
A3a web | chamadas de load_dotenv = 1
RESULTADO_JSON={"out": {"ausentes": [], "dir_iguais": false, "key_iguais": false, "src_key_vazia": true, "tools_key_vazia": false}, "e1": [], "chamadas": 1, "src_antes_carga": ["src.tools", "src.tools.gemini_router", "src.tools.notificador", "src.tools.oracle_dba", "src.tools.os_tools", "src.tools.payloads", "src.tools.rag_search"]}

```

**stderr**

```text
2026-11-18 13:33:16.207 WARNING streamlit.runtime.scriptrunner_utils.script_run_context: Thread 'MainThread': missing ScriptRunContext! This warning can be ignored when running in bare mode.

```

### a3b_cli

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3b_cli\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3b_cli\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): []
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`
- .env fictício depois (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
A3b cli | ausentes em sys.modules = []
A3b cli | src.tools.* / tools.* em sys.modules ao fim = ['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search', 'tools.gemini_router', 'tools.notificador', 'tools.oracle_dba', 'tools.os_tools', 'tools.rag_search']
A3b cli | src.tools.oracle_dba.__file__ = C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3b cli | tools.oracle_dba.__file__ = C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3b cli | src.tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\dir_env_a3
A3b cli | tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\dir_env_a3
A3b cli | DIRETORIO_LOG_APROVACAO iguais = True
A3b cli | src.tools.gemini_router.GEMINI_API_KEY vazia = False
A3b cli | tools.gemini_router.GEMINI_API_KEY vazia = False
A3b cli | GEMINI_API_KEY iguais = True
A3b cli | objetos de modulo distintos = True
A3b cli | chamadas de load_dotenv = 1 | src_tools_antes_da_carga = []
RESULTADO_JSON={"out": {"ausentes": [], "dir_iguais": true, "key_iguais": true, "src_key_vazia": false, "tools_key_vazia": false}, "chamadas": 1, "src_antes_carga": []}

```

**stderr**

```text
(vazio)
```

### a3b_web

- Comando: `C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe -B C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3b_web\filho.py C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\a3b_web\ficticio.env`
- returncode: 0
- Variáveis extras acrescentadas ao env (nomes): ['SCRIPTS_REGISTRY_PATH']
- Chaves com prefixo proibido passadas ao subprocesso (nomes): []
- ORACLE_SANDBOX no env passado: False
- .env fictício antes (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`
- .env fictício depois (repr): `b'AGENTDBA_LOG_DIR=C:\\Users\\FREDER~1\\AppData\\Local\\Temp\\isolamento_fase3\\dir_env_a3\nGEMINI_API_KEY=chave_ficticia_a3\n'`

**stdout**

```text
PRE | ORACLE_SANDBOX no processo antes da carga = AUSENTE
A3b web | excecoes = []
A3b web | ausentes em sys.modules = []
A3b web | src.tools.* / tools.* em sys.modules ao fim = ['src.tools', 'src.tools.gemini_router', 'src.tools.notificador', 'src.tools.oracle_dba', 'src.tools.os_tools', 'src.tools.payloads', 'src.tools.rag_search', 'tools.gemini_router', 'tools.notificador', 'tools.oracle_dba', 'tools.os_tools', 'tools.rag_search']
A3b web | src.tools.oracle_dba.__file__ = C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3b web | tools.oracle_dba.__file__ = C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT\src\tools\oracle_dba.py
A3b web | src.tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\dir_env_a3
A3b web | tools.oracle_dba.DIRETORIO_LOG_APROVACAO = C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3\dir_env_a3
A3b web | DIRETORIO_LOG_APROVACAO iguais = True
A3b web | src.tools.gemini_router.GEMINI_API_KEY vazia = False
A3b web | tools.gemini_router.GEMINI_API_KEY vazia = False
A3b web | GEMINI_API_KEY iguais = True
A3b web | objetos de modulo distintos = True
A3b web | chamadas de load_dotenv = 1 | src_tools_antes_da_carga = []
RESULTADO_JSON={"out": {"ausentes": [], "dir_iguais": true, "key_iguais": true, "src_key_vazia": false, "tools_key_vazia": false}, "e1": [], "chamadas": 1, "src_antes_carga": []}

```

**stderr**

```text
2026-11-18 13:33:22.304 WARNING streamlit.runtime.scriptrunner_utils.script_run_context: Thread 'MainThread': missing ScriptRunContext! This warning can be ignored when running in bare mode.

```

## 5. Limitações e observações

- Não executei pytest neste passo (regra do pedido). Nenhuma alteração no repositório.
- O .env real não foi aberto por nenhum passo. O .env fictício está em TMP e é removido ao fim.
- Como no modelo, os FileHandler de app.py/main.py são construídos antes do basicConfig; o basicConfig vira no-op, mas os arquivos são abertos em append (auditoria_oracle.log na raiz e em data/logs). Nenhuma linha é escrita por eles; ver o git status depois.
- A3 Web: a cópia src.tools.gemini_router entra em sys.modules junto com src.tools.oracle_dba (src/tools/__init__.py importa todos os módulos).

## 6. Apêndice: driver integral (rep.py)

```python
"""Driver da reprodução fase 3 (isolamento-env). Só lê o repositório; grava SÓ o relatório em docs/entregas/isolamento_env/."""
import datetime
import importlib.metadata as md
import json
import os
import pathlib
import subprocess
import sys

RAIZ = r"c:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT"
TMP = pathlib.Path(r"C:\Users\FREDER~1\AppData\Local\Temp\isolamento_fase3")
SAIDA = pathlib.Path(RAIZ) / "docs" / "entregas" / "isolamento_env" / "reproducao_fase3.md"
PREFIXOS = ("ORACLE_", "EMAIL_", "GEMINI_", "AGENTDBA_")
SCRIPTS_REG = str(pathlib.Path(RAIZ) / "registry" / "test_scripts.yaml")
DIR_ENV = TMP / "dir_env_a3"
ENV_LOG = {"AGENTDBA_LOG_DIR": str(TMP / "log"), "SCRIPTS_REGISTRY_PATH": SCRIPTS_REG}
ENV_A3 = {"SCRIPTS_REGISTRY_PATH": SCRIPTS_REG}
BYTES_A3 = ("AGENTDBA_LOG_DIR=" + str(DIR_ENV) + "\nGEMINI_API_KEY=chave_ficticia_a3\n").encode("utf-8")

ESPERADO = """?? db/ops_kill.sqlbkp
?? docs/entregas/1.11/item1/abc/
?? docs/entregas/1.11/item1/diff_producao.diff
?? docs/entregas/1.11/item1/diff_revisao_gemini.diff
?? docs/entregas/1.11/item1/diff_testes.diff
?? docs/entregas/1.11/item1/diff_tests.txt
?? docs/entregas/1.11/item1/greps.txt
?? docs/entregas/1.11/item1/o1o2/
?? docs/entregas/1.11/item1/pytest_run1.txt
?? docs/entregas/1.11/item1/pytest_run2.txt
?? docs/entregas/1.11/item1/revisao_adversarial_gemini.md
?? docs/entregas/1.11/item1/verificacao.md
?? docs/entregas/processo-subagentes/
?? docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md
?? docs/plans/1.11-item1-B-refeito.md"""
PERMITIDO_NOVO = "?? docs/entregas/isolamento_env/"

PREAMBULO = r'''
import json, logging, os, socket, sys
RAIZ = __RAIZ__
ENV_FICTICIO = sys.argv[1]
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "src"))
import dotenv
_ORIGINAL = dotenv.load_dotenv
CHAMADAS = []
def _wrapper(dotenv_path=None, *args, **kwargs):
    CHAMADAS.append({
        "caminho_pedido": None if dotenv_path is None else str(dotenv_path),
        "override_pedido": kwargs.get("override", "AUSENTE"),
        "src_tools_antes_da_carga": sorted(m for m in sys.modules if m.startswith(("src.tools", "tools."))),
    })
    kwargs.setdefault("override", False)
    return _ORIGINAL(ENV_FICTICIO, *args, **kwargs)
dotenv.load_dotenv = _wrapper
CAPTURA = []
class _Captura(logging.Handler):
    def emit(self, record):
        CAPTURA.append((record.levelname, record.getMessage()))
logging.getLogger().addHandler(_Captura())
logging.getLogger().setLevel(logging.INFO)
def _sem_rede(*args, **kwargs):
    raise OSError("rede neutralizada no teste")
socket.create_connection = _sem_rede
def avisos_desde(n):
    return [m for nivel, m in CAPTURA[n:] if nivel == "WARNING" and "DESCARTADA" in m]
def excecoes(at):
    return [str(e.value) for e in at.exception]
print("PRE | ORACLE_SANDBOX no processo antes da carga =", os.environ.get("ORACLE_SANDBOX", "AUSENTE"))
'''

B4_WEB = r'''
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=30)
at.run()
r1 = os.environ.get("ORACLE_USER_KILL")
e1 = excecoes(at)
print("B4 web | apos run1 | os.environ ORACLE_USER_KILL =", r1, "| excecoes =", e1)
with open(ENV_FICTICIO, "a", encoding="utf-8") as f:
    f.write("ORACLE_USER_KILL=kill_tardio_ficticio\n")
at.run()
r2 = os.environ.get("ORACLE_USER_KILL")
e2 = excecoes(at)
print("B4 web | apos run2 | os.environ ORACLE_USER_KILL =", r2, "| excecoes =", e2)
print("B4 web | chamadas de load_dotenv =", len(CHAMADAS))
print("RESULTADO_JSON=" + json.dumps({"run1": r1, "run2": r2, "e1": e1, "e2": e2, "chamadas": len(CHAMADAS)}))
'''

B4_CLI = r'''
import main  # noqa: F401
r1 = os.environ.get("ORACLE_USER_KILL")
print("B4 cli | apos import main | os.environ ORACLE_USER_KILL =", r1)
with open(ENV_FICTICIO, "a", encoding="utf-8") as f:
    f.write("ORACLE_USER_KILL=kill_tardio_ficticio\n")
r2 = os.environ.get("ORACLE_USER_KILL")
print("B4 cli | apos alterar o ficticio (sem rerun) | os.environ ORACLE_USER_KILL =", r2)
print("B4 cli | chamadas de load_dotenv =", len(CHAMADAS))
print("RESULTADO_JSON=" + json.dumps({"run1": r1, "run2": r2, "chamadas": len(CHAMADAS)}))
'''

C1_MIN = r'''
import io, json, os
from dotenv import load_dotenv
s = io.StringIO("FOO_FIRST=1\nFOO_BAD=abc\x00def\n")
exc = None
try:
    load_dotenv(stream=s, override=False)
except Exception as e:
    exc = type(e).__name__ + ": " + str(e)
foo = "FOO_FIRST" in os.environ
print("C1 min | excecao =", exc)
print("C1 min | FOO_FIRST em os.environ =", foo)
print("RESULTADO_JSON=" + json.dumps({"excecao": exc, "foo_first_em_environ": foo}))
'''

C1_WEB = r'''
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=30)
n0 = len(CAPTURA)
at.run()
e1 = excecoes(at); s1 = os.environ.get("ORACLE_SANDBOX"); d1 = avisos_desde(n0)
print("C1 web | run1 | excecoes =", e1)
print("C1 web | run1 | os.environ ORACLE_SANDBOX =", s1)
print("C1 web | run1 | avisos DESCARTADA =", d1)
n1 = len(CAPTURA)
at.run()
e2 = excecoes(at); s2 = os.environ.get("ORACLE_SANDBOX"); d2 = avisos_desde(n1)
print("C1 web | run2 | excecoes =", e2)
print("C1 web | run2 | os.environ ORACLE_SANDBOX =", s2)
print("C1 web | run2 | avisos DESCARTADA =", d2)
print("C1 web | chamadas de load_dotenv =", len(CHAMADAS))
print("RESULTADO_JSON=" + json.dumps({"e1": e1, "s1": s1, "d1": d1, "e2": e2, "s2": s2, "d2": d2, "chamadas": len(CHAMADAS)}))
'''

C1_CLI = r'''
exc = None
try:
    import main  # noqa: F401
except Exception as e:
    exc = type(e).__name__ + ": " + str(e)
s1 = os.environ.get("ORACLE_SANDBOX")
d1 = avisos_desde(0)
print("C1 cli | excecao no import de main =", exc)
print("C1 cli | os.environ ORACLE_SANDBOX =", s1)
print("C1 cli | avisos DESCARTADA =", d1)
print("C1 cli | chamadas de load_dotenv =", len(CHAMADAS))
print("RESULTADO_JSON=" + json.dumps({"excecao": exc, "s1": s1, "d1": d1, "chamadas": len(CHAMADAS)}))
'''

A3_FUNC = r'''
def comparar_a3(rot):
    nomes = ("src.tools.oracle_dba", "tools.oracle_dba", "src.tools.gemini_router", "tools.gemini_router")
    ausentes = [n for n in nomes if n not in sys.modules]
    print(rot, "| ausentes em sys.modules =", ausentes)
    print(rot, "| src.tools.* / tools.* em sys.modules ao fim =", sorted(m for m in sys.modules if m.startswith(("src.tools", "tools."))))
    out = {"ausentes": ausentes}
    if ausentes:
        return out
    so, to = sys.modules[nomes[0]], sys.modules[nomes[1]]
    go, gt = sys.modules[nomes[2]], sys.modules[nomes[3]]
    print(rot, "| src.tools.oracle_dba.__file__ =", so.__file__)
    print(rot, "| tools.oracle_dba.__file__ =", to.__file__)
    print(rot, "| src.tools.oracle_dba.DIRETORIO_LOG_APROVACAO =", str(so.DIRETORIO_LOG_APROVACAO))
    print(rot, "| tools.oracle_dba.DIRETORIO_LOG_APROVACAO =", str(to.DIRETORIO_LOG_APROVACAO))
    out["dir_iguais"] = so.DIRETORIO_LOG_APROVACAO == to.DIRETORIO_LOG_APROVACAO
    out["key_iguais"] = go.GEMINI_API_KEY == gt.GEMINI_API_KEY
    out["src_key_vazia"] = go.GEMINI_API_KEY == ""
    out["tools_key_vazia"] = gt.GEMINI_API_KEY == ""
    print(rot, "| DIRETORIO_LOG_APROVACAO iguais =", out["dir_iguais"])
    print(rot, "| src.tools.gemini_router.GEMINI_API_KEY vazia =", out["src_key_vazia"])
    print(rot, "| tools.gemini_router.GEMINI_API_KEY vazia =", out["tools_key_vazia"])
    print(rot, "| GEMINI_API_KEY iguais =", out["key_iguais"])
    print(rot, "| objetos de modulo distintos =", so is not to)
    return out
'''

A3A_CLI = r'''
import src.tools.oracle_dba  # noqa: F401  (pre-import ANTES de main)
print("A3a cli | src.tools.* em sys.modules antes do import main =", sorted(m for m in sys.modules if m.startswith(("src.tools", "tools."))))
import main  # noqa: F401
out = comparar_a3("A3a cli")
print("A3a cli | chamadas de load_dotenv =", len(CHAMADAS))
print("RESULTADO_JSON=" + json.dumps({"out": out, "chamadas": len(CHAMADAS), "src_antes_carga": CHAMADAS[0]["src_tools_antes_da_carga"] if CHAMADAS else None}))
'''

A3A_WEB = r'''
import src.tools.oracle_dba  # noqa: F401  (pre-import ANTES do app)
print("A3a web | src.tools.* em sys.modules antes do AppTest =", sorted(m for m in sys.modules if m.startswith(("src.tools", "tools."))))
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=30)
at.run()
e1 = excecoes(at)
print("A3a web | excecoes =", e1)
out = comparar_a3("A3a web")
print("A3a web | chamadas de load_dotenv =", len(CHAMADAS))
print("RESULTADO_JSON=" + json.dumps({"out": out, "e1": e1, "chamadas": len(CHAMADAS), "src_antes_carga": CHAMADAS[0]["src_tools_antes_da_carga"] if CHAMADAS else None}))
'''

A3B_CLI = r'''
import main  # noqa: F401
out = comparar_a3("A3b cli")
print("A3b cli | chamadas de load_dotenv =", len(CHAMADAS), "| src_tools_antes_da_carga =", CHAMADAS[0]["src_tools_antes_da_carga"] if CHAMADAS else None)
print("RESULTADO_JSON=" + json.dumps({"out": out, "chamadas": len(CHAMADAS), "src_antes_carga": CHAMADAS[0]["src_tools_antes_da_carga"] if CHAMADAS else None}))
'''

A3B_WEB = r'''
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=30)
at.run()
e1 = excecoes(at)
print("A3b web | excecoes =", e1)
out = comparar_a3("A3b web")
print("A3b web | chamadas de load_dotenv =", len(CHAMADAS), "| src_tools_antes_da_carga =", CHAMADAS[0]["src_tools_antes_da_carga"] if CHAMADAS else None)
print("RESULTADO_JSON=" + json.dumps({"out": out, "e1": e1, "chamadas": len(CHAMADAS), "src_antes_carga": CHAMADAS[0]["src_tools_antes_da_carga"] if CHAMADAS else None}))
'''


def git(*args):
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout


def status():
    linhas = [l for l in git("status", "--short", "--", ".").splitlines() if l.strip()]
    esperado = set(ESPERADO.splitlines())
    fora = [l for l in linhas if l not in esperado and l != PERMITIDO_NOVO]
    faltando = sorted(l for l in esperado if l not in linhas)
    return linhas, fora, faltando


def rodar(nome, corpo, env_extra, env_bytes, preambulo=True):
    assert "ORACLE_SANDBOX" not in env_extra
    d = TMP / nome
    d.mkdir(parents=True, exist_ok=True)
    ef = d / "ficticio.env"
    ef.write_bytes(env_bytes)
    texto = (PREAMBULO.replace("__RAIZ__", repr(RAIZ)) if preambulo else "") + corpo
    sp = d / "filho.py"
    sp.write_text(texto, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(PREFIXOS)}
    env.update(env_extra)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-B", str(sp), str(ef)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=env, cwd=RAIZ, timeout=900)
    resultado = None
    for linha in res.stdout.splitlines():
        if linha.startswith("RESULTADO_JSON="):
            resultado = json.loads(linha[len("RESULTADO_JSON="):])
    return {
        "nome": nome,
        "cmd": " ".join(cmd),
        "rc": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "env_extra": sorted(env_extra),
        "env_prefixados_passados": sorted(k for k in env if k.upper().startswith(PREFIXOS)),
        "sandbox_no_env_passado": "ORACLE_SANDBOX" in env,
        "env_fict_antes": repr(env_bytes),
        "env_fict_depois": repr(ef.read_bytes()),
        "resultado": resultado,
    }


def linha_veredito(achado, cenario, esperado, obtido, rep):
    if rep is None:
        veredito = "NÃO VERIFICADO"
    else:
        veredito = "REPRODUZ" if rep else "NÃO REPRODUZIDO"
    return (achado, cenario, esperado, obtido, veredito)


def v_a3(out, ordem_b):
    if out is None:
        return None, "sem RESULTADO_JSON (erro de execução)"
    aus = out.get("ausentes", [])
    if aus:
        if ordem_b and any(a.startswith("src.") for a in aus):
            return False, "uma só cópia na ordem de produção (ausentes: " + str(aus) + ")"
        return None, "NÃO COMPARÁVEL (ausentes: " + str(aus) + ")"
    rep = (not out["dir_iguais"]) or (not out["key_iguais"])
    return rep, ("dir_iguais=" + str(out["dir_iguais"]) + ", key_iguais=" + str(out["key_iguais"])
                 + ", src_key_vazia=" + str(out["src_key_vazia"]) + ", tools_key_vazia=" + str(out["tools_key_vazia"]))


def veredictos(R):
    L = []
    x = R["b4_web"]["resultado"]
    if x is None:
        L.append(linha_veredito("B4", "Web (AppTest, rerun)", "", "sem RESULTADO_JSON", None))
    else:
        rep = x["run1"] is None and x["run2"] == "kill_tardio_ficticio"
        L.append(linha_veredito("B4", "Web (AppTest, rerun)",
                                "ORACLE_USER_KILL ausente após run1 e presente após run2",
                                "run1=" + repr(x["run1"]) + "; run2=" + repr(x["run2"]), rep))
    x = R["b4_cli"]["resultado"]
    if x is None:
        L.append(linha_veredito("B4", "CLI (import main, sem rerun)", "", "sem RESULTADO_JSON", None))
    else:
        ok = x["run2"] is None and x["chamadas"] == 1
        L.append(("B4", "CLI (import main, sem rerun)", "nada recarrega após alterar o .env",
                  "run1=" + repr(x["run1"]) + "; após alterar=" + repr(x["run2"]) + "; chamadas=" + str(x["chamadas"]),
                  "CONFIRMADO: sem recarga (registro)" if ok else "RECARGA OBSERVADA (revisar)"))
    x = R["c1_min"]["resultado"]
    if x is None:
        L.append(linha_veredito("C1", "load_dotenv mínimo (stream)", "", "sem RESULTADO_JSON", None))
    else:
        rep = x["excecao"] is not None and x["foo_first_em_environ"]
        L.append(linha_veredito("C1", "load_dotenv mínimo (stream)", "exceção e FOO_FIRST já em os.environ",
                                "excecao=" + str(x["excecao"]) + "; FOO_FIRST em environ=" + str(x["foo_first_em_environ"]), rep))
    x = R["c1_web"]["resultado"]
    if x is None:
        L.append(linha_veredito("C1", "Web (AppTest, 2 reruns)", "", "sem RESULTADO_JSON", None))
    else:
        rep = (x["s1"] == "1" and not x["d1"]) or (x["s2"] == "1" and not x["d2"])
        L.append(linha_veredito("C1", "Web (AppTest, 2 reruns)",
                                "ORACLE_SANDBOX=1 permanece após run1 e/ou run2 sem WARNING DESCARTADA",
                                "run1: exc=" + str(x["e1"]) + ", ORACLE_SANDBOX=" + repr(x["s1"]) + ", avisos=" + str(x["d1"])
                                + " | run2: exc=" + str(x["e2"]) + ", ORACLE_SANDBOX=" + repr(x["s2"]) + ", avisos=" + str(x["d2"]), rep))
    x = R["c1_cli"]["resultado"]
    if x is None:
        L.append(linha_veredito("C1", "CLI (import main)", "", "sem RESULTADO_JSON", None))
    else:
        rep = x["s1"] == "1" and x["excecao"] is not None
        L.append(linha_veredito("C1", "CLI (import main)", "exceção e ORACLE_SANDBOX=1 permanece em os.environ",
                                "excecao=" + str(x["excecao"]) + "; ORACLE_SANDBOX=" + repr(x["s1"]) + "; avisos=" + str(x["d1"]), rep))
    for chave, cen, ordem_b, esp in (
        ("a3a_cli", "CLI (src.tools.oracle_dba importado antes de main)", False, "DIRETORIO e GEMINI_API_KEY iguais nas duas cópias"),
        ("a3a_web", "Web (src.tools.oracle_dba importado antes do AppTest)", False, "DIRETORIO e GEMINI_API_KEY iguais nas duas cópias"),
        ("a3b_cli", "CLI (só import main, ordem de produção)", True, "uma só cópia, sem divergência"),
        ("a3b_web", "Web (só AppTest, ordem de produção)", True, "uma só cópia, sem divergência"),
    ):
        x = R[chave]["resultado"]
        if x is None:
            L.append(linha_veredito("A3", cen, esp, "sem RESULTADO_JSON", None))
            continue
        rep, obt = v_a3(x["out"], ordem_b)
        obt = obt + " | src antes da carga=" + str(x.get("src_antes_carga"))
        L.append(linha_veredito("A3", cen, esp, obt, rep))
    return L


def bloco(titulo, texto):
    corpo = texto if texto.strip() else "(vazio)"
    return "**" + titulo + "**\n\n```text\n" + corpo + "\n```\n"


def montar(R, linhas_antes, fora_antes, falt_antes, linhas_depois, fora_depois, falt_depois,
           sb_inicio, sb_fim, versoes, head, inicio, fim):
    o = []
    o.append("# Reprodução fase 3 — isolamento-env (passo 0, só leitura)\n")
    o.append("- Data de execução: " + inicio.strftime("%Y-%m-%d %H:%M:%S") + " até " + fim.strftime("%H:%M:%S"))
    o.append("- Modelo: claude-haiku-5-5")
    o.append("- Branch: isolamento-env; HEAD: " + head)
    o.append("- Fonte dos achados: docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md (B4, C1, A3)")
    o.append("- Versões: Python " + sys.version.split()[0] + "; " + "; ".join(k + " " + v for k, v in versoes.items()))
    o.append("- Baseline da suíte: 199 passed, 16 skipped (não executada neste passo, conforme pedido).")
    o.append("- ORACLE_SANDBOX no processo de execução: antes=" + str(sb_inicio) + ", depois=" + str(sb_fim) + " (presença; deve ser False).\n")

    o.append("## 1. Veredito por achado\n")
    o.append("| Achado | Cenário | Esperado se reproduz | Obtido | Veredito |")
    o.append("|---|---|---|---|---|")
    for achado, cen, esp, obt, vr in veredictos(R):
        o.append("| " + " | ".join([achado, cen, esp.replace("|", "/"), obt.replace("|", "/"), "**" + vr + "**"]) + " |")
    o.append("")

    o.append("## 2. Passo 0 e git status\n")
    o.append("Passo 0 (executado antes do driver, comando do PROCESSO §5, só nomes): `passo0_linhas=0` (nenhum nome com ORACLE_, EMAIL_, GEMINI_, AGENTDBA_ ou SCRIPTS_ no HKCU/HKLM). `ORACLE_SANDBOX` do shell: vazio.\n")
    o.append(bloco("git status --short -- . ANTES (linhas fora do previsto: " + str(len(fora_antes)) + ")",
                   "\n".join(linhas_antes) + "\n\nFora do previsto: " + str(fora_antes) + "\nPrevistos ausentes: " + str(falt_antes)))
    o.append(bloco("git status --short -- . DEPOIS da execução e antes de gravar este relatório (fora do previsto: " + str(len(fora_depois)) + ")",
                   "\n".join(linhas_depois) + "\n\nFora do previsto: " + str(fora_depois) + "\nPrevistos ausentes: " + str(falt_depois)))

    o.append("## 3. Método\n")
    o.append("- Cada cenário é um subprocesso `python -B filho.py ficticio.env`, com cwd na raiz do projeto.")
    o.append("- env do subprocesso = os.environ sem chaves ORACLE_, EMAIL_, GEMINI_, AGENTDBA_; acrescentado só o que o cenário pede (valores fictícios): AGENTDBA_LOG_DIR (temp, fora de A3), SCRIPTS_REGISTRY_PATH (como no modelo tests/test_carga_env_entrada.py) e PYTHONDONTWRITEBYTECODE=1.")
    o.append("- `ORACLE_SANDBOX=1` aparece somente dentro do .env fictício de C1 (Web e CLI).")
    o.append("- dotenv.load_dotenv é substituído por wrapper que chama o original com o .env fictício em TMP; o .env real nunca é aberto. O wrapper registra o caminho pedido pelo app.")
    o.append("- Handler de captura no logger raiz (INFO): basicConfig vira no-op. Nenhum FileHandler de execução.")
    o.append("- socket.create_connection levanta OSError (sem rede).")
    o.append("- A3 (ordem de produção): só `import main` ou só AppTest, sem pré-import; a instrumentação registra src.tools.* em sys.modules no momento de cada chamada de load_dotenv.\n")

    o.append("## 4. Saídas brutas por execução\n")
    for nome in ("c1_min", "b4_web", "b4_cli", "c1_web", "c1_cli", "a3a_cli", "a3a_web", "a3b_cli", "a3b_web"):
        r = R[nome]
        o.append("### " + nome + "\n")
        o.append("- Comando: `" + r["cmd"] + "`")
        o.append("- returncode: " + str(r["rc"]))
        o.append("- Variáveis extras acrescentadas ao env (nomes): " + str(r["env_extra"]))
        o.append("- Chaves com prefixo proibido passadas ao subprocesso (nomes): " + str(r["env_prefixados_passados"]))
        o.append("- ORACLE_SANDBOX no env passado: " + str(r["sandbox_no_env_passado"]))
        o.append("- .env fictício antes (repr): `" + r["env_fict_antes"] + "`")
        o.append("- .env fictício depois (repr): `" + r["env_fict_depois"] + "`\n")
        o.append(bloco("stdout", r["stdout"]))
        o.append(bloco("stderr", r["stderr"]))

    o.append("## 5. Limitações e observações\n")
    o.append("- Não executei pytest neste passo (regra do pedido). Nenhuma alteração no repositório.")
    o.append("- O .env real não foi aberto por nenhum passo. O .env fictício está em TMP e é removido ao fim.")
    o.append("- Como no modelo, os FileHandler de app.py/main.py são construídos antes do basicConfig; o basicConfig vira no-op, mas os arquivos são abertos em append (auditoria_oracle.log na raiz e em data/logs). Nenhuma linha é escrita por eles; ver o git status depois.")
    o.append("- A3 Web: a cópia src.tools.gemini_router entra em sys.modules junto com src.tools.oracle_dba (src/tools/__init__.py importa todos os módulos).\n")

    o.append("## 6. Apêndice: driver integral (rep.py)\n")
    o.append("```python\n" + pathlib.Path(__file__).read_text(encoding="utf-8") + "\n```\n")
    return "\n".join(o)


def main():
    inicio = datetime.datetime.now()
    sb_inicio = "ORACLE_SANDBOX" in os.environ
    versoes = {}
    for pacote in ("streamlit", "python-dotenv", "openai"):
        try:
            versoes[pacote] = md.version(pacote)
        except Exception as e:
            versoes[pacote] = "erro " + type(e).__name__
    head = git("rev-parse", "--short", "HEAD").strip()
    linhas_antes, fora_antes, falt_antes = status()

    R = {}
    R["c1_min"] = rodar("c1_min", C1_MIN, {}, b"", preambulo=False)
    R["b4_web"] = rodar("b4_web", B4_WEB, ENV_LOG, b"SENTINELA_FASE3=1\n")
    R["b4_cli"] = rodar("b4_cli", B4_CLI, ENV_LOG, b"SENTINELA_FASE3=1\n")
    R["c1_web"] = rodar("c1_web", C1_WEB, ENV_LOG, b"ORACLE_SANDBOX=1\nSENTINELA_C1=abc\x00def\n")
    R["c1_cli"] = rodar("c1_cli", C1_CLI, ENV_LOG, b"ORACLE_SANDBOX=1\nSENTINELA_C1=abc\x00def\n")
    R["a3a_cli"] = rodar("a3a_cli", A3_FUNC + A3A_CLI, ENV_A3, BYTES_A3)
    R["a3a_web"] = rodar("a3a_web", A3_FUNC + A3A_WEB, ENV_A3, BYTES_A3)
    R["a3b_cli"] = rodar("a3b_cli", A3_FUNC + A3B_CLI, ENV_A3, BYTES_A3)
    R["a3b_web"] = rodar("a3b_web", A3_FUNC + A3B_WEB, ENV_A3, BYTES_A3)

    linhas_depois, fora_depois, falt_depois = status()
    sb_fim = "ORACLE_SANDBOX" in os.environ
    fim = datetime.datetime.now()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(montar(R, linhas_antes, fora_antes, falt_antes, linhas_depois, fora_depois, falt_depois,
                            sb_inicio, sb_fim, versoes, head, inicio, fim), encoding="utf-8")

    for achado, cen, esp, obt, vr in veredictos(R):
        print(achado, "|", cen, "|", vr, "|", obt)
    print("RC:", {k: v["rc"] for k, v in R.items()})
    print("git fora do previsto ANTES:", fora_antes, "| DEPOIS:", fora_depois)
    print("ORACLE_SANDBOX processo antes/depois:", sb_inicio, sb_fim)
    print("RELATORIO:", SAIDA)


if __name__ == "__main__":
    main()

```
