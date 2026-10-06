"""O rastro nao pode derrubar a resposta, e nao pode ligar sozinho.

Estes testes nao tocam a rede: o que esta sendo verificado e a politica, que e
quando ligar, o que fazer quando o destino falha e o que nao registrar.
"""

from __future__ import annotations

import pytest

from cautela.adaptadores import rastro as mod
from cautela.adaptadores.rastro import (
    RastroComposto,
    RastroNulo,
    abrir,
    datadog_ligado,
    langfuse_ligado,
)


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    for chave in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "DD_API_KEY",
        "DD_LLMOBS_ENABLED",
    ):
        monkeypatch.delenv(chave, raising=False)


def test_sem_chave_o_rastro_e_nulo() -> None:
    assert isinstance(abrir("qualquer pergunta"), RastroNulo)
    assert not langfuse_ligado()
    assert not datadog_ligado()


def test_uma_chave_so_do_langfuse_nao_liga(monkeypatch: pytest.MonkeyPatch) -> None:
    # Meia configuracao e pior que nenhuma: o cliente subiria e falharia em toda
    # execucao, gastando tempo de rede para nada.
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-exemplo")
    assert not langfuse_ligado()


def test_datadog_exige_o_interruptor_explicito(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ter a chave no ambiente nao basta. Variavel de Datadog costuma estar
    # presente em maquina corporativa inteira, e ligar telemetria por acidente
    # manda dado para um painel que ninguem esta olhando.
    monkeypatch.setenv("DD_API_KEY", "valor-qualquer")
    assert not datadog_ligado()
    monkeypatch.setenv("DD_LLMOBS_ENABLED", "1")
    assert datadog_ligado()


def test_destino_que_estoura_nao_derruba_a_execucao() -> None:
    class Quebrado:
        def evento(self, nome: str, **dados: object) -> None:
            raise RuntimeError("rede caiu")

        def encerrar(self, **dados: object) -> None:
            raise RuntimeError("rede caiu de novo")

    registrados: list[str] = []

    class Bom:
        def evento(self, nome: str, **dados: object) -> None:
            registrados.append(nome)

        def encerrar(self, **dados: object) -> None:
            registrados.append("fim")

    composto = RastroComposto([Quebrado(), Bom()])
    composto.evento("recuperar", fatos=["x"])
    composto.encerrar(resposta="ok")

    # O destino bom continuou recebendo mesmo com o outro estourando.
    assert registrados == ["recuperar", "fim"]


def test_falha_ao_abrir_um_destino_nao_impede_o_outro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-exemplo")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-exemplo")

    class LangfuseQuebrado:
        def __init__(self, pergunta: str) -> None:
            raise RuntimeError("sem rede")

    monkeypatch.setattr(mod, "RastroLangfuse", LangfuseQuebrado)

    # Com o unico destino configurado falhando ao abrir, sobra o rastro nulo e o
    # agente segue respondendo.
    assert isinstance(abrir("pergunta"), RastroNulo)
