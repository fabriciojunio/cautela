"""O auditor e a parte do sistema que nao confia no modelo.

Estes testes sao o contrato: se um deles cair, o agente passou a poder dizer
algo que ele nao deveria dizer.
"""

from __future__ import annotations

import pytest

from cautela.dominio.fato import Fato
from cautela.dominio.politica import (
    RECUSA_RECOMENDACAO,
    auditar,
    contem_recomendacao,
    numeros_sem_lastro,
)

FATO = Fato(
    chave="persistencia:acoes",
    pergunta="O desempenho passado de um fundo de acoes prediz o futuro?",
    valor="razao de chances de 0,94",
    leitura="1 significa independencia",
    fonte="cotas da CVM",
    limite="so entram fundos presentes nos dois periodos",
    reproduzir="python experimentos/02_persistencia.py",
    numeros=("0,94", "1"),
)


@pytest.mark.parametrize(
    "texto",
    [
        "Compre esse fundo agora.",
        "Eu recomendo aplicar em renda fixa.",
        "Vale a pena investir nesse quintil.",
        "Voce deveria comprar o fundo que ficou no topo.",
    ],
)
def test_recomendacao_e_barrada(texto: str) -> None:
    assert contem_recomendacao(texto)
    veredicto = auditar(texto, [FATO])
    assert not veredicto.aprovada
    assert veredicto.texto_substituto == RECUSA_RECOMENDACAO


@pytest.mark.parametrize(
    "texto",
    [
        "A razao de chances medida foi 0,94, o que indica independencia.",
        "O estudo de investimento mediu persistencia, e nao recomenda nada.",
        "A compra de cota nao entra nesta analise.",
    ],
)
def test_falar_do_assunto_nao_e_recomendar(texto: str) -> None:
    # A lista de padroes exige intencao explicita. Se bastasse a palavra
    # "investimento" ou "compra", o agente nao conseguiria falar do proprio
    # tema, e um auditor que barra tudo e tao inutil quanto um que nao barra
    # nada.
    assert not contem_recomendacao(texto)


def test_numero_que_nao_veio_do_acervo_e_pego() -> None:
    texto = "A razao foi 0,94 e a rentabilidade media do fundo foi 12,5% ao ano."
    fora = numeros_sem_lastro(texto, [FATO])
    assert "12,5%" in fora


def test_numero_do_acervo_passa() -> None:
    texto = "A razao de chances e 0,94, e 1 significa independencia."
    assert numeros_sem_lastro(texto, [FATO]) == []


def test_ano_e_quantil_nao_contam_como_numero_inventado() -> None:
    # Ano e numero de quantil aparecem na redacao legitima o tempo todo, e
    # exigi-los no acervo faria o auditor barrar resposta correta.
    texto = "Entre 2018 e 2024, o quintil 5 nao se manteve, com razao de 0,94."
    assert numeros_sem_lastro(texto, [FATO]) == []


def test_conversao_de_unidade_e_tratada_como_numero_novo() -> None:
    # 0,94 e 94% sao o mesmo valor, e mesmo assim 94% nao passa. E de proposito:
    # converter unidade e derivar, e a regra deste agente e nao derivar numero
    # nenhum. Derivacao e exatamente onde um modelo erra sem parecer errado.
    texto = "A chance de repetir foi de 94%."
    assert "94%" in numeros_sem_lastro(texto, [FATO])


def test_numero_que_esta_no_proprio_fato_nao_e_invencao() -> None:
    # Este teste existe por causa de um defeito real: o fato traz "IC 95%" no
    # texto, o modo de transcricao repetiu o fato inteiro, e o auditor barrou a
    # propria fonte achando que o modelo tinha inventado o 95%.
    #
    # A definicao certa e a do comentario que ja estava no codigo: vale o numero
    # que FOI ENTREGUE ao modelo, e o intervalo de confianca foi.
    com_intervalo = Fato(
        chave="persistencia:renda fixa",
        pergunta="Renda fixa persiste?",
        valor="razao de chances de 3,82 (IC 95%: 3,40 a 4,29)",
        leitura="acima de 1 ha persistencia",
        fonte="cotas da CVM",
        limite="so sobreviventes",
        reproduzir="python experimentos/02_persistencia.py",
        numeros=("3,82",),
    )
    texto = "A razao foi 3,82, com IC 95% entre 3,40 e 4,29."
    assert numeros_sem_lastro(texto, [com_intervalo]) == []


def test_sem_fato_recupera_a_recusa_padrao() -> None:
    veredicto = auditar("Qualquer coisa sem numero.", [])
    assert not veredicto.aprovada
    assert "nao sei" in veredicto.texto_substituto.lower()


def test_resposta_correta_passa_inteira() -> None:
    texto = (
        "A razao de chances medida foi 0,94, e 1 significa independencia entre um periodo "
        "e o seguinte. Fonte: cotas da CVM. Limitacao: so entram fundos presentes nos dois "
        "periodos."
    )
    assert auditar(texto, [FATO]).aprovada
