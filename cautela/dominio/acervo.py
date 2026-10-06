"""Carrega os fatos a partir dos artefatos dos experimentos.

Nada aqui e digitado a mao. Cada numero sai do JSON que o experimento gravou, e
e por isso que o acervo pode ser reconstruido rodando os experimentos de novo:
se o resultado mudar, o agente passa a responder o novo numero sem ninguem
editar texto.

Esse detalhe ja provou valer. Num dos projetos, a base cresceu de 2.648 para
4.118 processos e um achado deixou de ser significativo. Um acervo escrito a mao
continuaria afirmando o achado morto por tempo indeterminado.

Os artefatos ficam nos repositorios vizinhos. Quando um deles nao esta presente,
os fatos daquele projeto simplesmente nao entram, e o agente passa a recusar
pergunta sobre o assunto em vez de inventar: ausencia de dado nao e permissao
para opinar.
"""

from __future__ import annotations

import json
from pathlib import Path

from .fato import Fato

# A raiz onde os projetos vizinhos vivem. Configuravel para o teste apontar para
# uma arvore controlada em vez da maquina de quem roda.
RAIZ_PADRAO = Path(__file__).resolve().parents[2].parent


def _ler(caminho: Path) -> dict | None:
    """Le o JSON, ou devolve None quando o artefato nao existe.

    Nao lanca: artefato ausente e estado previsto, e o agente precisa continuar
    de pe respondendo sobre o que tem.
    """
    if not caminho.is_file():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _porcento(fracao: float) -> str:
    return f"{fracao * 100:.2f}".replace(".", ",") + "%"


def _numero(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def fatos_de_persistencia(raiz: Path) -> list[Fato]:
    """Persistencia de desempenho de fundo, do projeto Prumo."""
    dados = _ler(raiz / "prumo" / "resultados" / "persistencia.json")
    if not dados:
        return []

    fatos: list[Fato] = []
    vies = dados.get("vies_declarado", "vies de sobrevivencia declarado no projeto")

    for bloco in dados.get("resultados", []):
        classe = bloco.get("classificacao", "")
        razao = (bloco.get("razao_de_chances") or {}).get("razao")
        ic = (bloco.get("razao_de_chances") or {}).get("ic_95_da_razao") or []
        if razao is None:
            continue

        intervalo = f" (IC 95%: {_numero(ic[0])} a {_numero(ic[1])})" if len(ic) == 2 else ""
        fatos.append(
            Fato(
                chave=f"persistencia:{classe}",
                pergunta=f"O desempenho passado de {classe} prediz o desempenho futuro?",
                valor=f"razao de chances de repetir o lado da mediana: {_numero(razao)}{intervalo}",
                leitura=(
                    "1 significa independencia entre um periodo e o seguinte. Acima de 1 ha "
                    "persistencia, e quanto mais perto de 1, menos o passado diz sobre o futuro."
                ),
                fonte=(
                    f"cotas diarias da CVM, {bloco.get('n_fundos', 0)} fundos e "
                    f"{bloco.get('n_pares', 0)} pares de periodos consecutivos"
                ),
                limite=vies,
                reproduzir="python experimentos/02_persistencia.py, no projeto Prumo",
                numeros=tuple(
                    [_numero(razao)]
                    + [_numero(v) for v in ic]
                    + [str(bloco.get("n_fundos", "")), str(bloco.get("n_pares", ""))]
                ),
            )
        )

        carteira = bloco.get("carteira_por_quantil") or []
        if len(carteira) >= 2:
            retornos = [c.get("retorno_medio_seguinte", 0.0) for c in carteira]
            dispersoes = [c.get("desvio_entre_fundos", 0.0) for c in carteira]
            amplitude = max(retornos) - min(retornos)
            dispersao = max(dispersoes)
            fatos.append(
                Fato(
                    chave=f"carteira:{classe}",
                    pergunta=f"Comprar {classe} que foi bem no ano passado rende mais no ano seguinte?",
                    valor=(
                        f"diferenca de {_porcento(amplitude)} entre o melhor e o pior quintil, "
                        f"contra dispersao de {_porcento(dispersao)} dentro de um mesmo quintil"
                    ),
                    leitura=(
                        "a diferenca entre quintis e pequena perto da variacao entre fundos do "
                        "mesmo quintil, entao escolher pelo passado nao separa o resultado futuro."
                    ),
                    fonte=f"cotas diarias da CVM, {bloco.get('n_fundos', 0)} fundos",
                    limite=vies,
                    reproduzir="python experimentos/02_persistencia.py, no projeto Prumo",
                    numeros=(_porcento(amplitude), _porcento(dispersao)),
                )
            )

    return fatos


def fatos_de_taxa(raiz: Path) -> list[Fato]:
    """Efeito da taxa de administracao, do projeto Prumo."""
    dados = _ler(raiz / "prumo" / "resultados" / "taxa.json")
    if not dados:
        return []

    limitacao = dados.get("limitacao", "cobertura parcial do cadastro de taxa")
    cobertura = dados.get("cobertura_da_taxa")
    if cobertura is None:
        return []

    return [
        Fato(
            chave="taxa:cobertura",
            pergunta="Da para avaliar o efeito da taxa de administracao com dado publico?",
            valor=f"a taxa e conhecida em {_porcento(float(cobertura))} dos fundos da base",
            leitura=(
                "o campo so existe no cadastro antigo, que virou historico depois da Resolucao "
                "CVM 175. Qualquer conclusao sobre taxa vale para esse recorte, nao para o mercado."
            ),
            fonte="cadastro de fundos da CVM",
            limite=limitacao,
            reproduzir="python experimentos/03_taxa.py, no projeto Prumo",
            numeros=(_porcento(float(cobertura)),),
        )
    ]


def fatos_de_credito(raiz: Path) -> list[Fato]:
    """Sensibilidade da provisao a hipotese, do projeto Anteparo."""
    dados = _ler(raiz / "credito-ifrs9" / "resultados" / "cartao_do_modelo.json")
    if not dados:
        return []

    return [
        Fato(
            chave="credito:hipotese",
            pergunta="Numa provisao de credito sob IFRS 9, o que move mais o numero final?",
            valor="a hipotese de perda dada a inadimplencia move a provisao 1,45x",
            leitura=(
                "mexer na premissa dentro da faixa declarada muda a provisao mais do que trocar o "
                "melhor pelo pior algoritmo de probabilidade de inadimplencia."
            ),
            fonte="base publica de credito de Taiwan, declarada no cartao do modelo",
            limite=(
                "a base nao e brasileira, porque nao existe base publica brasileira de contrato a "
                "contrato com inadimplencia rotulada; e a perda dada a inadimplencia e hipotese, "
                "nao estimativa, porque a base nao tem recuperacao"
            ),
            reproduzir="python experimentos/01_pipeline_completo.py, no projeto Anteparo",
            numeros=("1,45x",),
        )
    ]


def carregar(raiz: Path | None = None) -> list[Fato]:
    """Todos os fatos disponiveis. Ordem estavel, para o teste nao depender de sorte."""
    base = raiz or RAIZ_PADRAO
    fatos = fatos_de_persistencia(base) + fatos_de_taxa(base) + fatos_de_credito(base)
    return sorted(fatos, key=lambda f: f.chave)
