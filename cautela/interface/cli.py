"""Linha de comando do agente.

    python -m cautela.interface.cli "o desempenho passado de um fundo prediz o futuro?"

Sem argumento, lista o acervo. Listar o que o agente PODE responder antes de
perguntar e o que evita a conversa mais comum com um sistema desses, que e
perguntar algo fora do escopo e concluir que ele nao funciona.
"""

from __future__ import annotations

import sys

from cautela.agente.grafo import responder
from cautela.dominio.acervo import carregar


def carregar_env() -> None:
    """Le o .env local, se existir.

    Fica aqui e nao no modulo de rastro de proposito: a biblioteca nao deve
    decidir de onde vem a configuracao do processo. Quem roda e quem decide, e
    no teste nenhuma variavel de ambiente e carregada por acidente.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def listar() -> int:
    fatos = carregar()
    if not fatos:
        print("Acervo vazio: os artefatos dos experimentos nao foram encontrados.")
        print("Este agente nao inventa numero, entao sem artefato ele so sabe recusar.")
        return 1
    print(f"{len(fatos)} fatos no acervo:\n")
    for f in fatos:
        print(f"  [{f.chave}]")
        print(f"    {f.pergunta}")
        print(f"    {f.valor}")
        print(f"    limite: {f.limite}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    carregar_env()
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        return listar()

    saida = responder(" ".join(args))
    print(saida["resposta"])
    print()
    print(f"[origem: {saida['origem']} | auditoria: {saida['veredicto']}]")
    if saida["fatos"]:
        print(f"[fatos usados: {', '.join(saida['fatos'])}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
