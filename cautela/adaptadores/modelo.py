"""Quem redige a resposta.

Duas implementacoes atras da mesma funcao, pelo mesmo motivo do PermaneIA: o
sistema precisa funcionar sem chave e sem rede, porque demonstracao em sala cai
e cota de tier gratuito acaba. O modo sem modelo nao e remendo, e degradacao
projetada: ele transcreve o fato em vez de redigi-lo.

O que NAO muda entre os dois modos: o numero. Ele vem do acervo nos dois casos.
A diferenca e so a prosa em volta.
"""

from __future__ import annotations

import os

from cautela.dominio.fato import Fato

INSTRUCAO = """Voce responde perguntas sobre investimento usando SOMENTE os fatos medidos abaixo.

Regras que nao se negociam:
- nunca recomende comprar, vender ou aplicar. Voce nao e analista certificado.
- nunca escreva um numero que nao esteja nos fatos. Nao calcule, nao converta, nao arredonde.
- cite a fonte e termine declarando a limitacao do fato que usou.
- se os fatos nao respondem a pergunta, diga que nao sabe.

Responda em portugues, em no maximo cinco frases, sem lista e sem titulo."""


def _chave() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def disponivel() -> bool:
    return len(_chave()) > 0 and os.environ.get("IA_EXTERNA") != "off"


def redigir_sem_modelo(pergunta: str, fatos: list[Fato]) -> str:
    """Transcricao determinista. Serve de piso e serve de teste.

    Note que ela nao tenta parecer conversa: repete o fato na forma em que ele
    foi medido. Uma transcricao honesta e melhor do que uma redacao bonita cujo
    numero ninguem conferiu.
    """
    if not fatos:
        return "Nao tenho numero medido para essa pergunta no acervo."
    f = fatos[0]
    return (
        f"{f.pergunta} {f.valor}. {f.leitura} "
        f"Fonte: {f.fonte}. Limitacao: {f.limite}."
    )


def redigir(pergunta: str, fatos: list[Fato], chamador=None) -> tuple[str, str]:
    """Devolve o texto e a origem ("gemini" ou "local").

    `chamador` existe para o teste injetar um modelo falso sem rede. Em
    producao ele vem nulo e o adaptador monta o cliente de verdade.
    """
    if not fatos:
        return redigir_sem_modelo(pergunta, fatos), "local"

    contexto = "\n\n".join(f.como_contexto() for f in fatos)
    prompt = f"{INSTRUCAO}\n\nFATOS:\n{contexto}\n\nPERGUNTA: {pergunta}"

    if chamador is not None:
        return chamador(prompt), "falso"

    if not disponivel():
        return redigir_sem_modelo(pergunta, fatos), "local"

    # Import tardio: sem chave configurada o projeto roda inteiro sem precisar
    # do pacote carregado, e o teste nao paga o custo de importar o cliente.
    from langchain_google_genai import ChatGoogleGenerativeAI

    modelo = ChatGoogleGenerativeAI(
        model=os.environ.get("GEMINI_MODELO", "gemini-flash-lite-latest"),
        google_api_key=_chave(),
        # Temperatura baixa porque a tarefa e transcrever um fato com fidelidade,
        # nao variar a redacao. E o parametro que mais afeta invencao de numero.
        temperature=0.1,
        max_output_tokens=600,
    )
    resposta = modelo.invoke(prompt)
    texto = resposta.content if isinstance(resposta.content, str) else str(resposta.content)
    return texto.strip(), "gemini"
