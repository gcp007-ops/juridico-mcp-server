"""Testes do client STJ. Foco: _poll (substitui sleeps fixos que davam 0 resultados)."""
import asyncio

from juridico_mcp.clients import stj


class _FakePage:
    def __init__(self, seq):
        self._seq = list(seq)
        self.calls = 0

    async def evaluate(self, expr):
        v = self._seq[min(self.calls, len(self._seq) - 1)]
        self.calls += 1
        return v


def test_poll_retorna_assim_que_truthy():
    # pagina em branco nas 2 primeiras leituras, resultados na 3a
    page = _FakePage([0, 0, 7])
    out = asyncio.run(stj._poll(page, "x", timeout=1.0, intervalo=0.01))
    assert out == 7
    assert page.calls == 3  # nao esperou o timeout inteiro


def test_poll_timeout_devolve_ultimo_falsy():
    page = _FakePage([0])
    out = asyncio.run(stj._poll(page, "x", timeout=0.05, intervalo=0.01))
    assert not out


def test_poll_tolera_excecao_no_evaluate():
    class Boom(_FakePage):
        async def evaluate(self, expr):
            self.calls += 1
            if self.calls < 2:
                raise RuntimeError("contexto detached")
            return 3

    page = Boom([])
    out = asyncio.run(stj._poll(page, "x", timeout=1.0, intervalo=0.01))
    assert out == 3  # nao propaga a excecao; segue pollando
