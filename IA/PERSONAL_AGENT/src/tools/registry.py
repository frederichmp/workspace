"""
Módulo de Carregamento e Validação do Registro de Scripts Homologados (registry/scripts.yaml).
Garante conformidade de schema Pydantic, unicidade de script_id e cache em memória (carregado uma única vez).
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union
import yaml
from pydantic import BaseModel, Field, field_validator


# Modelos Pydantic para validação estrita do schema
class BindDef(BaseModel):
    nome: str
    tipo: str = "string"


class ScriptRegistryEntry(BaseModel):
    script_id: str
    arquivo: str
    sha256: str
    tipo: Literal["SELECT", "DML", "DDL", "PLSQL"]
    risco: Literal["baixo", "medio", "alto"]
    status: Literal["homologado", "bloqueado"]
    binds: List[BindDef] = Field(default_factory=list)

    @field_validator("script_id")
    @classmethod
    def validar_script_id(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError(
                f"script_id '{v}' inválido. Deve conter apenas letras minúsculas, dígitos e underscore: [a-z0-9_]+"
            )
        return v

    @field_validator("sha256")
    @classmethod
    def validar_sha256(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", v_clean):
            raise ValueError(f"sha256 '{v}' inválido. Deve conter exatamente 64 caracteres hexadecimais minúsculos.")
        return v_clean


# Cache em memória (Singleton / carregado uma vez)
_REGISTRY_CACHE: Optional[Dict[str, ScriptRegistryEntry]] = None
_DEFAULT_REGISTRY_PATH: Optional[Path] = None


def obter_diretorio_raiz() -> Path:
    """
    Localiza o diretório raiz do projeto PERSONAL_AGENT de forma robusta.
    """
    # Se definido via variável de ambiente:
    env_root = os.getenv("PERSONAL_AGENT_ROOT")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()

    # Baseado na estrutura: este arquivo está em src/tools/registry.py -> sobe 2 níveis para raiz
    arquivo_atual = Path(__file__).resolve()
    # src/tools/registry.py -> parent = tools, parent.parent = src, parent.parent.parent = PERSONAL_AGENT
    raiz_candidata = arquivo_atual.parent.parent.parent
    if (raiz_candidata / "registry").exists() or (raiz_candidata / "scripts").exists():
        return raiz_candidata

    # Fallback para diretório de trabalho atual se contiver pasta registry ou scripts
    cwd = Path.cwd().resolve()
    if (cwd / "registry").exists() or (cwd / "scripts").exists():
        return cwd
    if (cwd / "IA" / "PERSONAL_AGENT").exists():
        return cwd / "IA" / "PERSONAL_AGENT"

    return raiz_candidata


def obter_caminho_registro() -> Path:
    """Retorna o caminho absoluto do arquivo scripts.yaml."""
    caminho_env = os.getenv("SCRIPTS_REGISTRY_PATH")
    if caminho_env:
        return Path(caminho_env).resolve()
    return obter_diretorio_raiz() / "registry" / "scripts.yaml"


def obter_caminho_scripts_dir() -> Path:
    """Retorna o diretório base onde residem os arquivos físicos dos scripts (scripts/)."""
    caminho_env = os.getenv("SCRIPTS_DIR_PATH")
    if caminho_env:
        return Path(caminho_env).resolve()
    return obter_diretorio_raiz() / "scripts"


def carregar_registro(
    caminho_yaml: Optional[Union[str, Path]] = None,
    forcar_recarga: bool = False,
) -> Dict[str, ScriptRegistryEntry]:
    """
    Carrega o catálogo de scripts homologados a partir do arquivo YAML.
    Valida os dados com Pydantic e armazena em cache em memória.
    Executa a validação apenas uma vez, exceto se forcar_recarga=True.
    """
    global _REGISTRY_CACHE

    if _REGISTRY_CACHE is not None and not forcar_recarga and caminho_yaml is None:
        return _REGISTRY_CACHE

    alvo = Path(caminho_yaml).resolve() if caminho_yaml else obter_caminho_registro()

    if not alvo.is_file():
        raise FileNotFoundError(f"Arquivo de registro de scripts não encontrado em: {alvo}")

    with open(alvo, "r", encoding="utf-8") as f:
        dados_yaml = yaml.safe_load(f)

    if dados_yaml is None:
        _REGISTRY_CACHE = {}
        return _REGISTRY_CACHE

    # Suporta formato de lista raiz ou dicionário com chave 'scripts'
    lista_entradas: List[dict] = []
    if isinstance(dados_yaml, dict) and "scripts" in dados_yaml:
        lista_entradas = dados_yaml["scripts"] or []
    elif isinstance(dados_yaml, list):
        lista_entradas = dados_yaml
    else:
        raise ValueError("Estrutura do YAML inválida. Esperada lista de scripts ou chave 'scripts'.")

    novo_registro: Dict[str, ScriptRegistryEntry] = {}
    for item in lista_entradas:
        entrada = ScriptRegistryEntry.model_validate(item)
        if entrada.script_id in novo_registro:
            raise ValueError(f"script_id duplicado detectado no registro: '{entrada.script_id}'")
        novo_registro[entrada.script_id] = entrada

    if caminho_yaml is None or forcar_recarga:
        _REGISTRY_CACHE = novo_registro

    return novo_registro


def obter_script(script_id: str) -> Optional[ScriptRegistryEntry]:
    """Recupera a entrada de um script homologado do registro em cache."""
    registro = carregar_registro()
    return registro.get(script_id)
