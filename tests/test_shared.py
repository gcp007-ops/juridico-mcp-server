from juridico_mcp.shared import clampar


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
