import pathlib

import pytest

from juridico_mcp import vault_common as vc


def test_slug_ascii_lower_default():
    # RT usa o default (lower=True)
    assert vc.slug_ascii("REsp Açúcar SP") == "resp-acucar-sp"


def test_slug_ascii_preserva_case_quando_lower_false():
    # Jusbrasil preserva o case
    assert vc.slug_ascii("TJ-MG Apelação", lower=False) == "TJ-MG-Apelacao"


def test_slug_ascii_max_len_e_fallback():
    assert vc.slug_ascii("a" * 100, max_len=10) == "a" * 10
    assert vc.slug_ascii("!!!") == "julgado"


def test_esc_yaml_escapa_barra_e_aspas():
    assert vc.esc_yaml('a"b\\c') == 'a\\"b\\\\c'


def test_exigir_required():
    vc.exigir_required({"a": "x", "b": "y"}, ("a", "b"))  # nao levanta
    with pytest.raises(ValueError, match="required ausentes"):
        vc.exigir_required({"a": "x", "b": ""}, ("a", "b"))


def test_resolver_base_sem_nada_levanta(monkeypatch):
    monkeypatch.delenv("THINKBOX_VAULT_PATH", raising=False)
    with pytest.raises(ValueError, match="THINKBOX_VAULT_PATH"):
        vc.resolver_base()


def test_escrever_nota_grava_na_subpasta(tmp_path):
    p = vc.escrever_nota(("sub", "dir"), "nome", "conteudo", base_path=str(tmp_path))
    assert pathlib.Path(p).read_text(encoding="utf-8") == "conteudo"
    assert p.endswith("nome.md") and "sub" in p and "dir" in p
