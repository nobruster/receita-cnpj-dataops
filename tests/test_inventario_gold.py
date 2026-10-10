from scripts import inventario_gold


class _Con:
    def __init__(self, rows):
        self.rows = rows
        self.fechada = False

    def execute(self, sql, params=None):
        assert "information_schema.columns" in sql
        return self

    def fetchall(self):
        return self.rows

    def close(self):
        self.fechada = True


def test_connect_ro(tmp_path, monkeypatch):
    chamadas = []
    con = _Con([("gold_x", "cnpj", "VARCHAR")])

    def fake_ro():
        chamadas.append("ro")
        return con

    monkeypatch.setattr(inventario_gold, "connect_ro", fake_ro)
    assert inventario_gold.main([str(tmp_path / "a.json")]) == 0
    assert chamadas == ["ro"]
    assert con.fechada
    assert "connect_rw" not in inventario_gold.__dict__
