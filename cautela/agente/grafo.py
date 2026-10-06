"""O grafo do agente, em LangGraph.

Quatro nos, e a ordem e a defesa:

    recuperar -> redigir -> auditar -> (aprovada? entrega : substitui)

Por que grafo e nao uma funcao em linha reta: o caminho da recusa e um caminho
de verdade, com saida propria, e nao um `if` escondido no meio da redacao.
Desenhado assim, da para olhar o diagrama e responder "como esse agente pode
recusar?" sem ler o codigo todo. Num sistema que fala de dinheiro, essa pergunta
e feita por quem audita, nao por quem programa.

O no de auditoria roda SEMPRE, inclusive quando o modelo nao foi chamado. Uma
transcricao do acervo tambem pode conter numero demais se alguem mexer no
formato, e a regra nao deve depender de quem escreveu o texto.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from cautela.adaptadores import modelo as adaptador_modelo
from cautela.adaptadores import rastro as adaptador_rastro
from cautela.dominio import politica
from cautela.dominio.acervo import carregar
from cautela.dominio.fato import Fato


class Estado(TypedDict, total=False):
    pergunta: str
    fatos: list[Fato]
    rascunho: str
    origem: str
    resposta: str
    veredicto: str
    rastro: Any
    chamador: Any
    acervo: list[Fato]


def _pontuar(fato: Fato, termos: set[str]) -> int:
    """Casamento por termo entre a pergunta e o texto do fato.

    Busca lexica simples, de proposito. O acervo tem dezenas de fatos, nao
    milhoes de documentos: embedding aqui seria complexidade sem ganho, e teria
    o custo de uma chamada externa antes de qualquer resposta.
    """
    alvo = f"{fato.pergunta} {fato.leitura} {fato.chave}".lower()
    return sum(1 for t in termos if len(t) > 3 and t in alvo)


def recuperar(estado: Estado) -> Estado:
    acervo = estado.get("acervo") or carregar()
    termos = {t.strip(".,?!").lower() for t in estado["pergunta"].split()}
    ranqueados = sorted(acervo, key=lambda f: _pontuar(f, termos), reverse=True)
    escolhidos = [f for f in ranqueados if _pontuar(f, termos) > 0][:2]

    estado["rastro"].evento(
        "recuperar",
        termos=sorted(termos),
        fatos=[f.chave for f in escolhidos],
    )
    return {**estado, "fatos": escolhidos}


def redigir(estado: Estado) -> Estado:
    texto, origem = adaptador_modelo.redigir(
        estado["pergunta"], estado["fatos"], estado.get("chamador")
    )
    estado["rastro"].evento("redigir", origem=origem, caracteres=len(texto))
    return {**estado, "rascunho": texto, "origem": origem}


def auditar(estado: Estado) -> Estado:
    veredicto = politica.auditar(estado["rascunho"], estado["fatos"])
    estado["rastro"].evento(
        "auditar",
        aprovada=veredicto.aprovada,
        motivo=veredicto.motivo,
    )
    if veredicto.aprovada:
        return {**estado, "resposta": estado["rascunho"], "veredicto": "aprovada"}
    return {
        **estado,
        "resposta": veredicto.texto_substituto,
        "veredicto": f"substituida: {veredicto.motivo}",
    }


def construir() -> Any:
    grafo = StateGraph(Estado)
    grafo.add_node("recuperar", recuperar)
    grafo.add_node("redigir", redigir)
    grafo.add_node("auditar", auditar)
    grafo.set_entry_point("recuperar")
    grafo.add_edge("recuperar", "redigir")
    grafo.add_edge("redigir", "auditar")
    grafo.add_edge("auditar", END)
    return grafo.compile()


_COMPILADO: Annotated[Any, "compilado uma vez: montar o grafo a cada pergunta e desperdicio"] = None


def responder(
    pergunta: str,
    acervo: list[Fato] | None = None,
    chamador: Any = None,
) -> dict[str, Any]:
    """Executa o agente e devolve resposta, veredicto e os fatos usados."""
    global _COMPILADO
    if _COMPILADO is None:
        _COMPILADO = construir()

    rastro = adaptador_rastro.abrir(pergunta)
    try:
        final = _COMPILADO.invoke(
            {
                "pergunta": pergunta,
                "rastro": rastro,
                "chamador": chamador,
                "acervo": acervo or [],
            }
        )
    finally:
        rastro.encerrar()

    return {
        "resposta": final["resposta"],
        "veredicto": final["veredicto"],
        "origem": final.get("origem", "local"),
        "fatos": [f.chave for f in final.get("fatos", [])],
    }
