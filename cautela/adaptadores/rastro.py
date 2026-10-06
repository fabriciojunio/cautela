"""Observabilidade do agente: Langfuse e Datadog, pela mesma porta.

Por que rastro e nao so log: a unidade que interessa num agente nao e a linha, e
a execucao inteira. Uma pergunta aciona recuperacao, redacao e auditoria, e o
que explica um resultado ruim e a sequencia. Log de texto corrido obriga quem
investiga a remontar isso na mao.

Por que dois destinos: eles respondem perguntas diferentes, e e assim que as
duas ferramentas aparecem juntas em empresa de verdade.

- **Langfuse** e especifico de LLM. Guarda entrada, saida e veredicto de cada
  etapa, e serve para abrir UMA execucao e entender por que ela saiu assim.
- **Datadog** e observabilidade geral com modulo de LLM. Serve para a visao de
  conjunto e para o alerta disparar quando a taxa de recusa muda de patamar.

Nenhuma credencial passa por este modulo. Os dois SDKs leem as proprias
variaveis de ambiente, e aqui so se verifica a PRESENCA delas. Ler o valor para
repassar adiante seria mais uma copia de segredo em memoria sem necessidade.

**Sem chave, o rastro desliga e o agente roda igual.** Falha de telemetria nunca
derruba a resposta de quem perguntou: cada exportador e isolado.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any, Protocol


class Rastro(Protocol):
    def evento(self, nome: str, **dados: Any) -> None: ...
    def encerrar(self, **dados: Any) -> None: ...


class RastroNulo:
    """Usado quando nenhum destino esta configurado. Nao faz nada, de proposito."""

    def evento(self, nome: str, **dados: Any) -> None:
        return None

    def encerrar(self, **dados: Any) -> None:
        return None


class RastroLangfuse:
    """Uma span por etapa, penduradas numa span de execucao."""

    def __init__(self, pergunta: str) -> None:
        from langfuse import Langfuse

        # Sem argumento: o cliente le LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY e
        # LANGFUSE_HOST do ambiente.
        #
        # `start_observation` e nao `start_span`: na versao 4 do SDK o metodo
        # mudou de nome. O tipo da observacao e declarado em `as_type`, e o
        # agente e um "agent" com etapas dentro, que e como o painel agrupa.
        self._cliente = Langfuse()
        self._span = self._cliente.start_observation(
            name="cautela.responder", as_type="agent", input={"pergunta": pergunta}
        )

    def evento(self, nome: str, **dados: Any) -> None:
        filho = self._span.start_observation(name=nome, as_type="span", input=dados)
        filho.end()

    def encerrar(self, **dados: Any) -> None:
        self._span.update(output=dados or None)
        self._span.end()
        # Em processo curto, como a linha de comando, o envio em segundo plano
        # nao tem tempo de sair. Sem este flush o rastro some sem erro nenhum.
        self._cliente.flush()


class RastroDatadog:
    """Fluxo de trabalho no modulo de LLM Observability do Datadog."""

    def __init__(self, pergunta: str) -> None:
        from ddtrace.llmobs import LLMObs

        self._llmobs = LLMObs
        # `agentless_enabled` porque nao ha agente local: num processo de linha
        # de comando e no CI, o SDK precisa falar direto com a API. As demais
        # configuracoes vem do ambiente, inclusive a credencial.
        LLMObs.enable(
            ml_app=os.environ.get("DD_LLMOBS_ML_APP", "cautela"),
            agentless_enabled=True,
        )
        self._contexto = LLMObs.workflow(name="cautela.responder")
        self._span = self._contexto.__enter__()
        LLMObs.annotate(span=self._span, input_data=pergunta)

    def evento(self, nome: str, **dados: Any) -> None:
        with self._llmobs.task(name=nome) as filho:
            self._llmobs.annotate(span=filho, metadata={k: str(v) for k, v in dados.items()})

    def encerrar(self, **dados: Any) -> None:
        self._llmobs.annotate(span=self._span, output_data=str(dados.get("resposta", "")))
        self._contexto.__exit__(None, None, None)
        self._llmobs.flush()


class RastroComposto:
    """Encaminha para todos os destinos ativos, isolando a falha de cada um."""

    def __init__(self, destinos: list[Any]) -> None:
        self._destinos = destinos

    def evento(self, nome: str, **dados: Any) -> None:
        for d in self._destinos:
            try:
                d.evento(nome, **dados)
            except Exception:  # noqa: BLE001
                continue

    def encerrar(self, **dados: Any) -> None:
        for d in self._destinos:
            try:
                d.encerrar(**dados)
            except Exception:  # noqa: BLE001
                continue


def langfuse_ligado() -> bool:
    """Presenca das variaveis, sem ler o conteudo delas."""
    return "LANGFUSE_PUBLIC_KEY" in os.environ and "LANGFUSE_SECRET_KEY" in os.environ


def datadog_ligado() -> bool:
    return "DD_API_KEY" in os.environ and os.environ.get("DD_LLMOBS_ENABLED") == "1"


def abrir(pergunta: str) -> Rastro:
    destinos: list[Any] = []

    # Falha ao abrir um destino, por rede ou por credencial errada, nao pode
    # impedir o outro nem a resposta. Daqui para a frente o agente roda igual,
    # com menos telemetria.
    if langfuse_ligado():
        with contextlib.suppress(Exception):
            destinos.append(RastroLangfuse(pergunta))

    if datadog_ligado():
        with contextlib.suppress(Exception):
            destinos.append(RastroDatadog(pergunta))

    if not destinos:
        return RastroNulo()
    return RastroComposto(destinos)
