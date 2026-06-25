"""Testes do client STJ (CDP, sem janela). _poll sincrono + parse de resultados."""
from juridico_mcp.clients import stj


class _FakeSession:
    def __init__(self, seq):
        self._seq = list(seq)
        self.calls = 0

    def evaluate(self, expr):
        v = self._seq[min(self.calls, len(self._seq) - 1)]
        self.calls += 1
        return v


def test_poll_retorna_assim_que_truthy():
    s = _FakeSession([0, 0, 7])  # pagina em branco nas 2 primeiras leituras
    assert stj._poll(s, "x", timeout=1.0, intervalo=0.001) == 7
    assert s.calls == 3  # nao esperou o timeout inteiro


def test_poll_timeout_devolve_ultimo_falsy():
    s = _FakeSession([0])
    assert not stj._poll(s, "x", timeout=0.01, intervalo=0.001)


def test_poll_tolera_excecao_no_evaluate():
    class Boom:
        def __init__(self):
            self.calls = 0

        def evaluate(self, expr):
            self.calls += 1
            if self.calls < 2:
                raise RuntimeError("contexto detached")
            return 3

    assert stj._poll(Boom(), "x", timeout=1.0, intervalo=0.001) == 3


def test_submit_js_escapa_valores():
    js = stj._submit_js('DANO "MORAL"', "ACOR", "01/01/2024", "")
    assert "frmConsulta" in js and "f.submit()" in js
    assert '"DANO \\"MORAL\\""' in js  # aspas escapadas via json.dumps


_HTML_RESULT = """
<html><body>
<div class="documento">
  <div class="paragrafoBRS"><div class="docTitulo">Processo</div>
    <div class="docTexto">REsp 1234567 / SP</div></div>
  <div class="paragrafoBRS"><div class="docTitulo">Relator</div>
    <div class="docTexto">Ministro Fulano</div></div>
  <div class="paragrafoBRS"><div class="docTitulo">Ementa</div>
    <div class="docTexto">DANO MORAL. NEGATIVACAO INDEVIDA. IN RE IPSA.</div></div>
</div>
</body></html>
"""


def test_parse_resultados_extrai_campos():
    rs = stj.STJClient()._parse_resultados(_HTML_RESULT, "ACOR", 10)
    assert len(rs) == 1
    r = rs[0]
    assert r.numero == "REsp 1234567"
    assert r.relator == "Ministro Fulano"
    assert "DANO MORAL" in r.ementa
    assert r.tipo == "Acordao"


def test_parse_resultados_vazio():
    assert stj.STJClient()._parse_resultados("<html></html>", "ACOR", 10) == []
