"""Mede o uso dos subagentes a partir das transcrições agent-*.jsonl (revisao-subagentes-v2).

Uso: python -I medir_subagentes.py [--dir <pasta das transcrições>] [--desde 2026-11-19T03:00]
As horas das transcrições estão em UTC (sufixo Z); o git mostra -03:00. Converta antes de comparar.
Imprime só agregados e caminhos lidos; nunca conteúdo de arquivo.
"""
import argparse, collections, glob, json, os, statistics as st

PADRAO = os.path.join(os.environ.get("USERPROFILE", ""), ".claude", "projects",
                      "c--Users-Frederich-OneDrive---Startup-Dados-e-Sistemas-Ltda---EPP-Workspace-IA-PERSONAL-AGENT")


def medir(arquivo):
    meta = arquivo[:-6] + ".meta.json"
    tipo = json.load(open(meta, encoding="utf-8")).get("agentType", "?") if os.path.exists(meta) else "?"
    r = dict(tipo=tipo, ts="", turnos=0, entrada=0, primeiro=None, pedido=0, retorno=0, ferramentas=collections.Counter(),
             leituras=collections.Counter(), modelos=collections.Counter())
    pedido_lido = False
    for linha in open(arquivo, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(linha)
        except ValueError:
            continue
        r["ts"] = r["ts"] or (o.get("timestamp") or "")
        msg = o.get("message") or {}
        if o.get("type") == "user" and not pedido_lido:
            c = msg.get("content")
            r["pedido"] = len(c) if isinstance(c, str) else sum(len(x.get("text", "")) for x in c or [] if isinstance(x, dict))
            pedido_lido = True
        if o.get("type") != "assistant":
            continue
        r["turnos"] += 1
        if msg.get("model"):
            r["modelos"][msg["model"]] += 1
        u = msg.get("usage") or {}
        n = sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        r["entrada"] += n
        r["primeiro"] = n if r["primeiro"] is None else r["primeiro"]
        for c in msg.get("content", []) or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                r["ferramentas"][c.get("name")] += 1
                inp = c.get("input") or {}
                if c.get("name") == "Read":
                    r["leituras"][inp.get("file_path", "").replace("\\", "/").split("PERSONAL_AGENT/")[-1]] += 1
                if c.get("name") == "SubagentHandback":
                    r["retorno"] += len(json.dumps(inp, ensure_ascii=False))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=PADRAO)
    ap.add_argument("--desde", default="", help="hora UTC mínima do início da chamada, ex.: 2026-11-19T03:00")
    a = ap.parse_args()
    linhas = [medir(f) for f in glob.glob(os.path.join(a.dir, "**", "agent-*.jsonl"), recursive=True)]
    linhas = [r for r in linhas if r["ts"] >= a.desde]
    total = sum(r["entrada"] for r in linhas) or 1
    print(f"{len(linhas)} chamadas desde {a.desde or 'o início'} (UTC); {total / 1e6:.1f} M tokens de entrada")
    por_tipo = collections.defaultdict(list)
    for r in linhas:
        por_tipo[r["tipo"]].append(r)
    for tipo, rs in sorted(por_tipo.items(), key=lambda kv: -len(kv[1])):
        med = lambda k: st.median(r[k] for r in rs)
        longas = [r for r in rs if r["turnos"] > 40]
        relidas = sum(sum(n - 1 for n in r["leituras"].values() if n > 1) for r in rs)
        print(f"\n{tipo}: {len(rs)} chamadas | {sum(r['entrada'] for r in rs) / 1e6:.1f} M | modelos {dict(sum((r['modelos'] for r in rs), collections.Counter()))}")
        print(f"  1º turno: mediana {med('primeiro'):.0f} (mín. {min(r['primeiro'] or 0 for r in rs)}) | turnos: mediana {med('turnos'):.0f}, máx. {max(r['turnos'] for r in rs)}")
        print(f"  pedido: mediana {med('pedido'):.0f} car. | retorno: mediana {med('retorno'):.0f}, máx. {max(r['retorno'] for r in rs)} car.")
        print(f"  chamadas com mais de 40 turnos: {len(longas)} ({sum(r['entrada'] for r in longas) / total:.0%} do total) | releituras: {relidas}")
        print(f"  ferramentas: {sum((r['ferramentas'] for r in rs), collections.Counter()).most_common(8)}")


if __name__ == "__main__":
    main()
