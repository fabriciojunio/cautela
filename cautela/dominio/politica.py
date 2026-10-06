"""As regras que valem independentemente do que o modelo responder.

Instrucao em prompt nao e garantia: ela e um pedido. O que garante e codigo que
le a saida e a recusa. Sao tres regras, e cada uma existe por um motivo
diferente.

**Nao recomendar.** Este agente fala de investimento. Dizer "compre", "venda" ou
"vale a pena" e recomendacao, e recomendacao de investimento no Brasil e
atividade regulada pela CVM, reservada a analista certificado. A regra aqui nao
e de estilo, e de nao exercer profissao alheia.

**Nao citar numero que nao veio do acervo.** O risco real de um agente que fala
de dinheiro nao e errar o tom, e inventar um numero com cara de medido. Por isso
cada fato carrega a lista dos numeros que podem aparecer, e a resposta e
conferida contra ela.

**Sempre declarar o limite.** Numero sem limitacao vira regra geral na cabeca de
quem le. O limite vai no texto, nao numa nota de rodape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .fato import Fato

# Verbos e expressoes que caracterizam recomendacao. A lista e de intencao
# explicita, nao de palavra solta: "investimento" sozinho nao bloqueia nada,
# senao o agente nao conseguiria falar do proprio assunto.
PADROES_DE_RECOMENDACAO = (
    r"\b(compre|venda|invista|aplique|resgate)\b",
    r"\b(recomendo|recomendamos|sugiro|aconselho)\b",
    r"\bvale a pena (comprar|investir|aplicar)\b",
    r"\b(melhor|pior) (fundo|acao|investimento) (para|e)\b",
    r"\bvoce deveria (comprar|investir|aplicar|vender)\b",
)

# Numeros que nao precisam estar no acervo: ano, quantil, numero de item de
# lista e percentual de referencia escrito por extenso no proprio texto do fato.
ISENTOS = re.compile(r"^(19|20)\d{2}$|^[1-5]$")

RECUSA_RECOMENDACAO = (
    "Nao faco recomendacao de investimento. Recomendacao e atividade regulada "
    "pela CVM e exige analista certificado. Posso dizer o que foi medido, com a "
    "fonte e a limitacao."
)

RECUSA_SEM_FATO = (
    "Nao tenho numero medido para essa pergunta no acervo. Prefiro dizer que nao "
    "sei a responder por impressao."
)


@dataclass(frozen=True)
class Veredicto:
    aprovada: bool
    motivo: str = ""
    texto_substituto: str = ""


def _numeros_do_texto(texto: str) -> list[str]:
    """Extrai numeros como aparecem escritos, inclusive com virgula decimal e sufixo."""
    return re.findall(r"\d+(?:[.,]\d+)*\s*%?x?", texto)


def _normalizar(valor: str) -> str:
    return valor.replace(" ", "").replace(".", "").lower()


def contem_recomendacao(texto: str) -> bool:
    alvo = texto.lower()
    return any(re.search(p, alvo) for p in PADROES_DE_RECOMENDACAO)


# Pergunta que PEDE recomendacao. E uma lista diferente da de cima: aqui a
# forma e interrogativa, e barrar "comprar" sozinho impediria perguntar sobre
# comportamento de quem compra, que e assunto legitimo do acervo.
PADROES_DE_PEDIDO = (
    r"\b(qual|quais|que)\b.{0,40}\b(comprar|vender|investir|aplicar)\b",
    r"\b(devo|posso|vale a pena)\b.{0,30}\b(comprar|vender|investir|aplicar)\b",
    r"\bo que (voce )?(recomenda|sugere|acha que eu)\b",
    r"\bmelhor (fundo|acao|a[cç][aã]o|investimento)\b",
    r"\bonde (investir|aplicar)\b",
)


def pergunta_pede_recomendacao(pergunta: str) -> bool:
    """Reconhece o pedido antes de o modelo ser chamado.

    O auditor cuida da saida, mas havia um buraco: perguntado "qual acao
    comprar agora", o agente devolvia um fato correto sobre escolher pelo
    passado e NAO dizia que nao recomenda. A resposta era honesta e incompleta,
    porque a pessoa foi embora sem saber que aquilo nao era conselho.

    A resposta certa nao e recusar a pergunta inteira: e dizer que nao recomenda
    e entregar o que foi medido logo em seguida.
    """
    alvo = pergunta.lower()
    return any(re.search(p, alvo) for p in PADROES_DE_PEDIDO)


def numeros_sem_lastro(texto: str, fatos: list[Fato]) -> list[str]:
    """Numeros presentes na resposta que nao aparecem em nenhum fato recuperado.

    Compara por forma normalizada e nao por valor numerico, de proposito: o que
    interessa e se aquele numero FOI ENTREGUE ao modelo, e nao se por acaso ele
    equivale a algum outro. Modelo que reescreve 1,45x como 145% esta derivando
    um numero, e derivacao e exatamente o que nao queremos aqui.
    """
    # O conjunto permitido sai do TEXTO que foi entregue ao modelo, e nao apenas
    # da lista curada. Foi um caso real que ensinou isso: o intervalo de
    # confianca aparece no proprio fato como "IC 95%", o modo de transcricao
    # repetiu o fato inteiro, e o auditor barrou a propria fonte por causa do
    # "95%". Numero que estava no contexto nao e invencao do modelo, por
    # definicao.
    permitidos = {_normalizar(n) for f in fatos for n in f.numeros}
    for f in fatos:
        for n in _numeros_do_texto(f.como_contexto()):
            permitidos.add(_normalizar(n))
    fora: list[str] = []
    for bruto in _numeros_do_texto(texto):
        achatado = bruto.strip()
        if ISENTOS.match(achatado):
            continue
        if _normalizar(achatado) not in permitidos:
            fora.append(achatado)
    return fora


def auditar(texto: str, fatos: list[Fato]) -> Veredicto:
    """Decide se a resposta pode sair como esta.

    A ordem importa. Recomendacao e barrada antes de qualquer conferencia de
    numero, porque uma resposta que recomenda com numero correto continua sendo
    uma recomendacao.
    """
    if contem_recomendacao(texto):
        return Veredicto(False, "recomendacao de investimento", RECUSA_RECOMENDACAO)

    if not fatos:
        return Veredicto(False, "sem fato no acervo", RECUSA_SEM_FATO)

    inventados = numeros_sem_lastro(texto, fatos)
    if inventados:
        return Veredicto(
            False,
            f"numero fora do acervo: {', '.join(inventados)}",
            RECUSA_SEM_FATO,
        )

    return Veredicto(True)
