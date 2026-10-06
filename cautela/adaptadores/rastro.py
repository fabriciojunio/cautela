"""Observabilidade do agente, com Langfuse.

Por que Langfuse e nao so log: a unidade que interessa num agente nao e a linha,
e a execucao inteira. Uma pergunta aciona recuperacao, redacao e auditoria, e o
que explica um resultado ruim e a sequencia, nao cada etapa isolada. Rastro de
texto corrido obriga quem investiga a remontar isso na mao.

O que fica registrado por execucao: a pergunta, quais fatos foram recuperados, o
texto que o modelo produziu, o veredicto do auditor e, quando houve substituicao,
o motivo. O veredicto e o campo mais util: ele transforma "o agente respondeu
estranho" em uma contagem de quantas respostas foram barradas e por que.

**Sem chave configurada, o rastro e desligado e o agente roda igual.** Dependencia
de servico externo para a aplicacao funcionar seria o oposto do que esta escrito
no resto deste projeto.
"""

from __future__ import annotations

import os
from typing import Any


def ligado() -> bool:
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))


class RastroNulo:
    """Implementacao vazia, usada quando o Langfuse nao esta configurado."""

    def evento(self, nome: str, **dados: Any) -> None:  # noqa: D102
        return None

    def encerrar(self) -> None:  # noqa: D102
        return None


class RastroLangfuse:
    """Encaminha a execucao para o Langfuse, uma span por etapa do grafo."""

    def __init__(self, pergunta: str) -> None:
        from langfuse import Langfuse

        self._cliente = Langfuse()
        self._span = self._cliente.start_span(name="cautela.responder", input={"pergunta": pergunta})

    def evento(self, nome: str, **dados: Any) -> None:
        filho = self._span.start_span(name=nome, input=dados)
        filho.end()

    def encerrar(self) -> None:
        self._span.end()
        # Em processo curto, como a linha de comando, o envio em segundo plano
        # nao tem tempo de sair. Sem este flush o rastro some sem erro nenhum.
        self._cliente.flush()


def abrir(pergunta: str) -> RastroNulo | RastroLangfuse:
    if not ligado():
        return RastroNulo()
    try:
        return RastroLangfuse(pergunta)
    except Exception:
        # Falha em telemetria nunca derruba a resposta de quem perguntou.
        return RastroNulo()
