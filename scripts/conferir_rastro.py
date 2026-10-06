"""Confere se o rastro chegou ao Langfuse, lendo de volta pela API.

Existe porque telemetria e o tipo de coisa que falha em silencio: o SDK aceita a
chamada, o processo termina, e ninguem descobre que nada foi enviado ate
precisar do dado. A unica prova de que funciona e ler de volta.

    python scripts/conferir_rastro.py

O cliente le as credenciais do ambiente sozinho; este script nunca toca no valor
das chaves.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    from langfuse import Langfuse

    cliente = Langfuse()
    if not cliente.auth_check():
        print("Autenticacao recusada pelo Langfuse. Confira as chaves no .env.")
        return 1

    # A API antiga de traces (`/api/public/traces`) responde 410 para
    # organizacao criada a partir de setembro de 2026. O caminho atual e a de
    # observacoes, com janela de tempo obrigatoria.
    # Janela de um dia porque a ingestao tem atraso de alguns minutos, e
    # conferir logo depois de rodar o agente devolvia vazio com tudo correto.
    # Vazio aqui nao prova que nada foi enviado; prova que nada chegou AINDA.
    #
    # `fields` nao e opcional por comodidade. A v2 devolve grupos de campos, e o
    # padrao e `core,basic`: nome, tipo e horario. Entrada, saida, modelo, token
    # e custo ficam FORA, e vem ausentes, nao nulos. Sem pedir, este script
    # mostrava a estrutura do rastro e nenhum conteudo, o que e pior do que nao
    # mostrar nada: parece que o agente registrou uma geracao sem token.
    agora = datetime.now(UTC)
    pagina = cliente.api.observations.get_many(
        fields="core,basic,io,model,usage",
        from_start_time=agora - timedelta(days=1),
        to_start_time=agora + timedelta(hours=1),
        limit=50,
    )
    observacoes = getattr(pagina, "data", [])
    if not observacoes:
        print("Autenticou, mas nenhuma observacao chegou nas ultimas 24 horas.")
        print("Se o agente acabou de rodar, espere alguns minutos: a ingestao atrasa.")
        return 1

    print(f"{len(observacoes)} observacoes nas ultimas 24 horas:\n")
    for o in observacoes:
        linha = f"  {o.start_time}  {o.name}  ({o.type})"
        modelo = getattr(o, "model", None)
        if modelo:
            linha += f"  modelo={modelo}"
        uso = getattr(o, "usage_details", None)
        if uso:
            linha += f"  tokens={uso.get('input')}/{uso.get('output')}"
        custo = getattr(o, "total_cost", None)
        if custo is not None:
            linha += f"  US$ {custo}"
        print(linha)

    # Uma geracao sem modelo e sem token e o sinal de que o atributo nao subiu,
    # e nao de que a chamada foi barata. Vale dizer em voz alta.
    mudas = [
        o
        for o in observacoes
        if o.type == "GENERATION" and not getattr(o, "model", None) and not getattr(o, "usage_details", None)
    ]
    if mudas:
        print(f"\nAtencao: {len(mudas)} geracao(oes) sem modelo e sem token.")
        print("Confira se os atributos estao sendo passados na criacao da span.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
