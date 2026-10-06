"""O que o agente pode afirmar.

Um fato aqui nao e um texto solto: e um numero que saiu de um experimento, com a
base de onde veio, a limitacao declarada e o jeito de reproduzir. O modelo de
linguagem nunca cria um fato, so redige o que o acervo entrega.

A razao disso e o unico risco que importa num agente que fala de investimento:
numero inventado com tom de autoridade. Um assistente que erra a data de uma
prova atrapalha um aluno; um que erra a rentabilidade de um fundo, ou pior, que
inventa uma, induz decisao de dinheiro.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fato:
    """Um numero medido, com tudo que precisa acompanhar o numero."""

    chave: str
    """Identificador estavel, usado pelo auditor e pelos testes."""

    pergunta: str
    """A pergunta que este fato responde, escrita como alguem perguntaria."""

    valor: str
    """O numero ja formatado. Texto, e nao float, porque a unidade faz parte dele."""

    leitura: str
    """O que o numero quer dizer, em uma frase."""

    fonte: str
    """De onde o dado veio. Nome da base e recorte, nunca "estudos mostram"."""

    limite: str
    """A limitacao declarada. Fato sem limite nao entra no acervo."""

    reproduzir: str
    """Comando ou caminho que refaz o numero."""

    numeros: tuple[str, ...] = field(default_factory=tuple)
    """
    Todo numero que pode aparecer legitimamente numa resposta sobre este fato.

    E com esta lista que o auditor confere a saida do modelo: numero que esta na
    resposta e nao esta aqui nao veio do acervo, veio do modelo. Ver
    dominio/politica.py.
    """

    def como_contexto(self) -> str:
        """O bloco que vai para o prompt. Formato fixo, para o modelo nao ter que adivinhar."""
        return (
            f"PERGUNTA: {self.pergunta}\n"
            f"RESPOSTA MEDIDA: {self.valor}\n"
            f"LEITURA: {self.leitura}\n"
            f"FONTE: {self.fonte}\n"
            f"LIMITACAO: {self.limite}\n"
        )
