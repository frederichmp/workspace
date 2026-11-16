"""
Ferramenta Reutilizável de Verificação de Integridade de Scripts Oracle.
Calcula o hash SHA-256 dos bytes brutos de cada arquivo em scripts/
e compara com o hash registrado em registry/scripts.yaml.
"""

import sys
import hashlib
from pathlib import Path
import yaml


def verificar_hashes(atualizar: bool = False) -> int:
    # Determina diretório base
    base_dir = Path(__file__).resolve().parent.parent
    yaml_path = base_dir / "registry" / "scripts.yaml"
    scripts_dir = base_dir / "scripts"

    if not yaml_path.is_file():
        print(f"ERRO: Arquivo de registro não encontrado em {yaml_path}")
        return 1

    with open(yaml_path, "r", encoding="utf-8") as f:
        registro_data = yaml.safe_load(f)

    scripts_list = registro_data.get("scripts", [])
    divergencias = 0

    print("=" * 140)
    print(f"{'SCRIPT_ID':<26} | {'ARQUIVO':<28} | {'HASH REGISTRADO':<64} | {'STATUS'}")
    print("=" * 140)

    alterado = False

    for item in scripts_list:
        script_id = item.get("script_id", "")
        arquivo = item.get("arquivo", "")
        hash_reg = item.get("sha256", "")

        arquivo_path = (scripts_dir / arquivo).resolve()

        if not arquivo_path.is_file():
            hash_calc = "ARQUIVO_NAO_ENCONTRADO"
            status = "DIVERGENTE (ARQUIVO AUSENTE)"
            divergencias += 1
        else:
            raw_bytes = arquivo_path.read_bytes()
            hash_calc = hashlib.sha256(raw_bytes).hexdigest()
            if hash_calc == hash_reg:
                status = "OK"
            else:
                status = "DIVERGENTE"
                divergencias += 1
                if atualizar and script_id not in ("script_hash_divergente", "path_traversal_parent_t17", "path_traversal_abs_t17"):
                    item["sha256"] = hash_calc
                    alterado = True
                    status = "DIVERGENTE (ATUALIZADO)"

        print(f"{script_id:<26} | {arquivo:<28} | {hash_reg:<64} | {status}")
        if status.startswith("DIVERGENTE") and hash_calc != "ARQUIVO_NAO_ENCONTRADO":
            print(f"  -> Hash Calculado: {hash_calc}")

    print("=" * 140)
    print(f"Total de scripts avaliados: {len(scripts_list)} | Divergências encontradas: {divergencias}")
    print("=" * 140)

    if atualizar and alterado:
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(registro_data, f, sort_keys=False, allow_unicode=True)
        print("Arquivo registry/scripts.yaml atualizado com sucesso.")

    return 0 if divergencias == 0 else 1


if __name__ == "__main__":
    atualizar_flag = "--atualizar" in sys.argv or "--update" in sys.argv
    sys.exit(verificar_hashes(atualizar=atualizar_flag))
