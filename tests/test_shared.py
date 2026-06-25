from juridico_mcp.shared import (
    clampar,
    dedup_resultados,
    formatar_resultados_texto,
    ResultadoJuridico,
    PREVIEW_CHARS,
)


def _r(numero="", ementa="", tipo="acordao"):
    return ResultadoJuridico(fonte="x", tipo=tipo, numero=numero, ementa=ementa)


def test_formatar_preview_trunca_ementa_e_marca():
    longa = "A" * 1200
    out = formatar_resultados_texto([_r(numero="1", ementa=longa)])
    assert "Ementa (preview):" in out
    assert "[...]" in out                       # truncou
    assert len(out) < 1000                      # nao despejou os 1200
    assert "completo=True" in out               # nota de rodape


def test_formatar_completo_nao_trunca_curto():
    media = "B" * 1200  # < 2000 (cap completo)
    out = formatar_resultados_texto([_r(numero="1", ementa=media)], completo=True)
    assert "Ementa:" in out and "(preview)" not in out
    assert "[...]" not in out                    # 1200 < 2000, sem corte
    assert "completo=True" not in out            # sem nota quando completo


def test_formatar_dedup_por_numero():
    rs = [_r(numero="REsp 1", ementa="a"), _r(numero="REsp 1", ementa="b"), _r(numero="REsp 2", ementa="c")]
    out = formatar_resultados_texto(rs)
    assert "2 exibidos" in out                   # 3 -> 2 apos dedup


def test_dedup_preserva_sem_numero():
    rs = [_r(numero="", ementa="a"), _r(numero="", ementa="b")]
    assert len(dedup_resultados(rs)) == 2        # sem numero = sem chave confiavel


def test_preview_chars_e_o_cap_default():
    assert PREVIEW_CHARS == 500



def test_clampar_dentro_do_intervalo():
    assert clampar(10, lo=1, hi=50) == 10


def test_clampar_acima_do_teto():
    assert clampar(999, lo=1, hi=50) == 50
    assert clampar(999, lo=1, hi=100) == 100


def test_clampar_abaixo_do_piso():
    # 0 e negativos virariam slices patologicos (lista[:0], lista[:-3]) nos clients
    assert clampar(0, lo=1, hi=50) == 1
    assert clampar(-5, lo=1, hi=50) == 1


def test_clampar_tolera_nao_inteiro():
    assert clampar("abc", lo=1, hi=50) == 1
    assert clampar(None, lo=1, hi=50) == 1
    assert clampar("12", lo=1, hi=50) == 12
