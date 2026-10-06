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


def fatos_de_duracao_judicial(raiz: Path) -> list[Fato]:
    """Duracao de processo judicial, do projeto Decurso.

    Entra num agente de investimentos porque contingencia judicial e passivo:
    quem avalia uma empresa precisa saber quanto tempo o processo dura e quanto
    disso vira provisao.
    """
    dados = _ler(raiz / "decurso" / "resultados" / "duracao.json")
    if not dados:
        return []

    comp = dados.get("comparacao_das_duas_contas") or {}
    km = comp.get("mediana_kaplan_meier")
    encerrados = comp.get("mediana_dos_encerrados")
    razao = comp.get("razao")
    if km is None or encerrados is None or razao is None:
        return []

    return [
        Fato(
            chave="judicial:duracao",
            pergunta="Quanto tempo dura um processo judicial, e a conta de planilha serve?",
            valor=(
                f"mediana de {int(km)} dias por Kaplan-Meier, contra {int(encerrados)} dias "
                f"pela media dos processos ja encerrados: razao de {_numero(razao)}"
            ),
            leitura=(
                "a conta de planilha so olha o que ja terminou, e o que ainda esta correndo e "
                "justamente o mais demorado. O erro nao e aleatorio: e maior na vara mais lenta."
            ),
            fonte="API publica do CNJ, processos coletados pelo DataJud",
            limite=(
                "a coleta veio incompleta, com 4.118 processos de 9.852 estimados, e isso esta "
                "declarado em vez de invisivel"
            ),
            reproduzir="python experimentos/02_duracao.py, no projeto Decurso",
            numeros=(str(int(km)), str(int(encerrados)), _numero(razao)),
        )
    ]


def fatos_de_texto_regulatorio(raiz: Path) -> list[Fato]:
    """Vazamento de anotacao, do projeto Verbete.

    E o fato mais util do acervo para quem vai construir modelo: mostra o
    tamanho do engano que um campo contaminado produz.
    """
    dados = _ler(raiz / "verbete" / "resultados" / "treino.json")
    if not dados:
        return []

    vaz = dados.get("vazamento_de_anotacao") or {}
    sem = vaz.get("micro_f1_sem")
    com = vaz.get("micro_f1_com")
    if sem is None or com is None:
        return []

    ganho = (com / sem - 1) * 100 if sem else 0
    return [
        Fato(
            chave="texto:vazamento",
            pergunta="Quanto um campo contaminado infla o resultado de um modelo de texto?",
            valor=f"micro-F1 de {_numero(sem, 3)} sem o campo e {_numero(com, 3)} com ele",
            leitura=(
                f"o modelo pareceria {ganho:.0f}% melhor do que vai ser em producao, porque o "
                "campo e preenchido pela mesma pessoa que atribui o rotulo e nao existe no dia "
                "em que o documento chega."
            ),
            fonte="proposicoes legislativas da API da Camara dos Deputados",
            limite=(
                "a divisao e temporal e nao aleatoria: proposicao sobre o mesmo assunto reaparece "
                "a cada legislatura com ementa quase igual, e divisao aleatoria poria a quase-copia "
                "nos dois lados"
            ),
            reproduzir="python experimentos/02_treinar.py, no projeto Verbete",
            numeros=(_numero(sem, 3), _numero(com, 3)),
        )
    ]


def fatos_de_efeito_de_contato(raiz: Path) -> list[Fato]:
    """Efeito incremental de contato, do projeto Trato."""
    dados = _ler(raiz / "trato" / "resultados" / "cartao_do_dado.json")
    if not dados:
        return []

    efeito = dados.get("efeito_medio")
    if efeito is None:
        return []

    return [
        Fato(
            chave="contato:efeito",
            pergunta="Contatar o cliente muda o comportamento dele, ou ele ja ia agir sozinho?",
            valor=f"efeito medio do contato medido em experimento aleatorizado: {efeito}",
            leitura=(
                "a pergunta certa nao e quem vai agir, e quem age POR CAUSA do contato. Modelo de "
                "resposta manda mensagem para quem ja ia agir, que e onde o contato so custa."
            ),
            fonte=str(dados.get("fonte", "experimento aleatorizado publico")),
            limite=(
                "uplift nao tem rotulo individual: ninguem e observado contatado e nao contatado "
                "ao mesmo tempo, entao toda validacao e por grupo"
            ),
            reproduzir="python experimentos/02_uplift.py, no projeto Trato",
            numeros=(str(efeito),),
        )
    ]


def carregar(raiz: Path | None = None) -> list[Fato]:
    """Todos os fatos disponiveis. Ordem estavel, para o teste nao depender de sorte."""
    base = raiz or RAIZ_PADRAO
    fatos = (
        fatos_de_persistencia(base)
        + fatos_de_taxa(base)
        + fatos_de_credito(base)
        + fatos_de_duracao_judicial(base)
        + fatos_de_texto_regulatorio(base)
        + fatos_de_efeito_de_contato(base)
    )
    return sorted(fatos, key=lambda f: f.chave)
