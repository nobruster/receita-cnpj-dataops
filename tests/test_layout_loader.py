"""Layout e proteções da carga raw (sem PostgreSQL)."""

import zipfile

import duckdb
import pytest

from chaos.sample import write_zip
from pipeline.errors import CorruptZipError, LayoutDriftError, MissingFilesError
from pipeline.receita import loader
from pipeline.receita.layout import ENTITIES, EXPECTED_FILES, entity_for_file, validate_competencia


def test_37_arquivos_esperados():
    assert len(EXPECTED_FILES) == 37


@pytest.mark.parametrize("nome,ent", [("Estabelecimentos3.zip", "estabelecimentos"), ("Cnaes.zip", "cnaes"),
                                       ("Simples.zip", "simples")])
def test_entity_for_file(nome, ent):
    assert entity_for_file(nome).name == ent


def test_arquivo_desconhecido():
    assert entity_for_file("Empresas.zip") is None  # empresas é particionado
    assert entity_for_file("Novidade9.zip") is None


def test_competencia_invalida():
    with pytest.raises(ValueError):
        validate_competencia("2026-13")


def _row(n: int) -> str:
    return ";".join(f'"{i}"' for i in range(n))


def test_layout_drift_detectado(tmp_path):
    p = tmp_path / "Empresas0.csv"
    p.write_text("\n".join(_row(8) for _ in range(10)), encoding="latin-1")
    with pytest.raises(LayoutDriftError):
        loader.check_layout(p, ENTITIES["empresas"], "Empresas0.zip", "2026-08")


def test_zip_corrompido_detectado(tmp_path):
    z = tmp_path / "Cnaes.zip"
    write_zip(z, "CNAE.csv", ['"0111301";"CULTIVO DE ARROZ"'] * 100)
    z.write_bytes(z.read_bytes()[:40])
    with pytest.raises(CorruptZipError):
        loader._extract_member(z, tmp_path, "2026-08")


def test_landing_incompleto(tmp_path):
    write_zip(tmp_path / "Cnaes.zip", "x", ['"1";"a"'])
    with pytest.raises(MissingFilesError):
        loader.check_landing(tmp_path, "2026-08")


def test_carga_latin1_e_log(tmp_path):
    z = tmp_path / "Cnaes.zip"
    write_zip(z, "CNAE.csv", ['"0111301";"CULTIVO DE ARROZ"', '"4711302";"COMÉRCIO VAREJISTA"'])
    con = duckdb.connect()
    loader._ensure_log(con)
    loader._create_raw_table(con, ENTITIES["cnaes"])
    csv = loader._extract_member(z, tmp_path, "2026-08")
    fl = loader.load_csv(con, csv, ENTITIES["cnaes"], "Cnaes.zip", "2026-08")
    assert fl.linhas == 2 and fl.erros_parse == 0
    assert con.execute("SELECT descricao FROM raw.raw_cnaes WHERE codigo='4711302'").fetchone()[0] == \
        "COMÉRCIO VAREJISTA"
    assert zipfile.is_zipfile(z)
