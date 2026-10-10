from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_default_privileges():
    sql = (RAIZ / "sql" / "001_schemas_roles.sql").read_text(encoding="utf-8")
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE publisher IN SCHEMA gold "
        "GRANT SELECT ON TABLES TO bi_reader"
    ) in sql


def test_make_bi_ddl():
    linhas = (RAIZ / "Makefile").read_text(encoding="utf-8").splitlines()
    assert any(linha.startswith("bi-ddl:") for linha in linhas)


def test_env_example_bi_reader():
    linhas = (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "BI_READER_PASSWORD=" in linhas
    assert "PUBLISHER_PASSWORD=" in linhas
