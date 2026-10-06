"""O grafo inteiro, sem rede e sem chave.

O modelo entra por injecao, entao estes testes verificam o comportamento do
agente e nao o humor de um provedor externo.
"""

from __future__ import annotations

import json
from pathlib import Path

from cautela.agente.grafo import responder
from cautela.dominio.acervo import carregar
from cautela.dominio.fato import Fato

ACERVO = [
    Fato(
        chave="persistencia:acoes",
        pergunta="O desempenho passado de um fundo de acoes prediz o futuro?",
        valor="razao de chances de 0,94",
        leitura="1 significa independencia entre um periodo e o seguinte",
        fonte="cotas diarias da CVM",
        limite="so entram fundos presentes nos dois periodos do par",
        reproduzir="python experimentos/02_persistencia.py",
        numeros=("0,94",),
    ),
    Fato(
        chave="credito:hipotese",
        pergunta="O que move mais a provisao de credito?",
        valor="a hipotese de perda move 1,45x",
        leitura="mais do que trocar o algoritmo",
        fonte="base publica de credito",
        limite="base nao brasileira",
        reproduzir="python experimentos/01_pipeline_completo.py",
        numeros=("1,45x",),
    ),
]


def test_pergunta_sem_fato_recebe_recusa_e_nao_inventa() -> None:
    saida = responder("qual acao vai subir amanha?", acervo=ACERVO)
    assert saida["veredicto"].startswith("substituida")
    assert saida["fatos"] == []


def test_resposta_do_modelo_que_recomenda_e_substituida() -> None:
    # O modelo falso desobedece a instrucao de proposito. E o cenario que o
    # auditor existe para cobrir: instrucao em prompt e pedido, nao garantia.
    def modelo_desobediente(_prompt: str) -> str:
        return "A razao e 0,94, entao eu recomendo comprar esse fundo."

    saida = responder(
        "o desempenho passado de um fundo de acoes prediz o futuro?",
        acervo=ACERVO,
        chamador=modelo_desobediente,
    )
    assert "recomendacao" in saida["veredicto"]
    assert "Nao faco recomendacao" in saida["resposta"]


def test_resposta_do_modelo_que_inventa_numero_e_substituida() -> None:
    def modelo_criativo(_prompt: str) -> str:
        return "A razao e 0,94 e a rentabilidade foi de 14,2% no periodo."

    saida = responder(
        "o desempenho passado de um fundo de acoes prediz o futuro?",
        acervo=ACERVO,
        chamador=modelo_criativo,
    )
    assert "numero fora do acervo" in saida["veredicto"]


def test_resposta_fiel_ao_acervo_passa() -> None:
    def modelo_fiel(_prompt: str) -> str:
        return (
            "A razao de chances medida foi 0,94, e 1 significa independencia. "
            "Fonte: cotas diarias da CVM. Limitacao: so entram fundos presentes "
            "nos dois periodos do par."
        )

    saida = responder(
        "o desempenho passado de um fundo de acoes prediz o futuro?",
        acervo=ACERVO,
        chamador=modelo_fiel,
    )
    assert saida["veredicto"] == "aprovada"
    assert "0,94" in saida["resposta"]


def test_sem_modelo_a_resposta_e_a_transcricao_do_fato() -> None:
    saida = responder("o desempenho passado de um fundo de acoes prediz o futuro?", acervo=ACERVO)
    assert saida["origem"] == "local"
    assert "0,94" in saida["resposta"]
    assert "Limitacao" in saida["resposta"] or "limite" in saida["resposta"].lower()


def test_acervo_vazio_quando_nao_ha_artefato(tmp_path: Path) -> None:
    # Ausencia de dado nao e permissao para opinar: o agente simplesmente fica
    # sem fatos e passa a recusar.
    assert carregar(tmp_path) == []


def test_acervo_le_o_artefato_de_verdade(tmp_path: Path) -> None:
    destino = tmp_path / "prumo" / "resultados"
    destino.mkdir(parents=True)
    (destino / "persistencia.json").write_text(
        json.dumps(
            {
                "vies_declarado": "so entram sobreviventes",
                "resultados": [
                    {
                        "classificacao": "fundos de acoes",
                        "n_fundos": 1000,
                        "n_pares": 4000,
                        "razao_de_chances": {"razao": 0.94, "ic_95_da_razao": [0.9, 0.98]},
                        "carteira_por_quantil": [
                            {"retorno_medio_seguinte": 0.08, "desvio_entre_fundos": 0.2},
                            {"retorno_medio_seguinte": 0.09, "desvio_entre_fundos": 0.3},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    fatos = carregar(tmp_path)
    chaves = {f.chave for f in fatos}
    assert "persistencia:fundos de acoes" in chaves
    assert "carteira:fundos de acoes" in chaves

    persistencia = next(f for f in fatos if f.chave == "persistencia:fundos de acoes")
    assert "0,94" in persistencia.valor
    # O limite vem do proprio artefato, nao de texto escrito a mao aqui.
    assert persistencia.limite == "so entram sobreviventes"
