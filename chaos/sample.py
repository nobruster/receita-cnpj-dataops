"""Gera uma competência sintética, fiel ao formato físico da Receita.

37 zips, cada um com um CSV sem cabeçalho, ``;``, aspas em todos os campos,
ISO-8859-1 — exatamente o que o loader espera. Determinístico por ``seed``.
Inclui CNPJs alfanuméricos (a partir de 2026-07) e os "defeitos da fonte" que a
Receita publica de verdade (motivo 32 sem domínio, UF EX, capital sentinela,
CEP com 7 dígitos) — eles NÃO podem virar rejeição.

Uso: ``python -m chaos.sample --competencia 2026-08 --empresas 2000 --out /data/landing``
"""

from __future__ import annotations

import argparse
import random
import string
import zipfile
from datetime import date, timedelta
from pathlib import Path

from pipeline.receita import cnpj as cnpjlib
from pipeline.receita.layout import ENTITIES

CNAES = [
    ("4711302", "COMERCIO VAREJISTA DE MERCADORIAS EM GERAL - SUPERMERCADOS"),
    ("5611201", "RESTAURANTES E SIMILARES"),
    ("6201501", "DESENVOLVIMENTO DE PROGRAMAS DE COMPUTADOR SOB ENCOMENDA"),
    ("4781400", "COMERCIO VAREJISTA DE ARTIGOS DO VESTUARIO E ACESSORIOS"),
    ("8630503", "ATIVIDADE MEDICA AMBULATORIAL RESTRITA A CONSULTAS"),
    ("4930202", "TRANSPORTE RODOVIARIO DE CARGA, EXCETO PRODUTOS PERIGOSOS"),
    ("9602501", "CABELEIREIROS, MANICURE E PEDICURE"),
    ("4120400", "CONSTRUCAO DE EDIFICIOS"),
    ("6911701", "SERVICOS ADVOCATICIOS"),
    ("7319002", "PROMOCAO DE VENDAS"),
    ("8211300", "SERVICOS COMBINADOS DE ESCRITORIO E APOIO ADMINISTRATIVO"),
    ("4520001", "SERVICOS DE MANUTENCAO E REPARACAO MECANICA DE VEICULOS"),
]
MOTIVOS = [("00", "SEM MOTIVO"), ("01", "EXTINCAO POR ENCERRAMENTO LIQUIDACAO VOLUNTARIA"),
           ("21", "PEDIDO DE BAIXA INDEFERIDO"), ("63", "OMISSAO DE DECLARACOES")]
MUNICIPIOS = [("9701", "BRASILIA", "DF"), ("7107", "SAO PAULO", "SP"), ("6001", "RIO DE JANEIRO", "RJ"),
              ("4123", "BELO HORIZONTE", "MG"), ("1389", "FORTALEZA", "CE"), ("2531", "RECIFE", "PE"),
              ("3849", "SALVADOR", "BA"), ("7535", "PORTO ALEGRE", "RS")]
NATUREZAS = [("2062", "SOCIEDADE EMPRESARIA LIMITADA"), ("2135", "EMPRESARIO (INDIVIDUAL)"),
             ("2305", "EMPRESA INDIVIDUAL DE RESPONSABILIDADE LIMITADA"), ("2046", "SOCIEDADE ANONIMA ABERTA"),
             ("3999", "ASSOCIACAO PRIVADA")]
PAISES = [("105", "BRASIL"), ("249", "ESTADOS UNIDOS"), ("607", "PORTUGAL")]
QUALIFICACOES = [("00", "NAO INFORMADA"), ("05", "ADMINISTRADOR"), ("22", "SOCIO"),
                 ("49", "SOCIO-ADMINISTRADOR"), ("16", "PRESIDENTE")]
NOMES = ["SILVA", "SOUZA", "OLIVEIRA", "SANTOS", "LIMA", "PEREIRA", "COSTA", "RIBEIRO", "ALVES", "CARVALHO"]
PREFIXOS = ["COMERCIAL", "DISTRIBUIDORA", "TECH", "SERVICOS", "INDUSTRIA", "CONSULTORIA", "ATELIE", "PADARIA"]


def _q(v: object) -> str:
    return '"' + ("" if v is None else str(v)).replace('"', "") + '"'


def _line(values: list[object]) -> str:
    return ";".join(_q(v) for v in values)


def _d(x: date | None) -> str:
    return x.strftime("%Y%m%d") if x else "0"


def _money(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _raiz(rng: random.Random, alfanumerica: bool) -> str:
    if alfanumerica:
        return "".join(rng.choice(string.digits + string.ascii_uppercase) for _ in range(8))
    return f"{rng.randrange(10**7, 10**8):08d}"


def write_zip(path: Path, member: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = ("\n".join(lines) + ("\n" if lines else "")).encode("latin-1")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(member, data)


def generate(competencia: str, out: Path, empresas: int = 2000, seed: int = 42) -> Path:
    """Gera ``out/<competencia>/*.zip`` e devolve a pasta."""
    rng = random.Random(seed)
    ano, mes = map(int, competencia.split("-"))
    ref = date(ano, mes, 1)
    alfa_ok = ref >= date(2026, 7, 1)
    dest = out / competencia
    rows: dict[str, list[str]] = {k: [] for k in ENTITIES}

    for codigo, desc in CNAES:
        rows["cnaes"].append(_line([codigo, desc]))
    for codigo, desc in MOTIVOS:  # sem o "32": a Receita publica o código mas não o domínio
        rows["motivos"].append(_line([codigo, desc]))
    for codigo, nome, _ in MUNICIPIOS:
        rows["municipios"].append(_line([codigo, nome]))
    for codigo, desc in NATUREZAS:
        rows["naturezas"].append(_line([codigo, desc]))
    for codigo, desc in PAISES:
        rows["paises"].append(_line([codigo, desc]))
    for codigo, desc in QUALIFICACOES:
        rows["qualificacoes"].append(_line([codigo, desc]))

    raizes: list[str] = []
    seen: set[str] = set()
    while len(raizes) < empresas:
        r = _raiz(rng, alfanumerica=alfa_ok and rng.random() < 0.02)
        if r not in seen:
            seen.add(r)
            raizes.append(r)

    for i, raiz in enumerate(raizes):
        nat = rng.choice(NATUREZAS)[0]
        porte = rng.choices(["01", "03", "05", "00"], weights=[70, 8, 20, 2])[0]
        capital = 999999999999.0 if i == 7 else round(rng.uniform(0, 500000), 2)
        razao = f"{rng.choice(PREFIXOS)} {rng.choice(NOMES)} {rng.choice(['LTDA', 'ME', 'EIRELI', 'S.A.'])}"
        rows["empresas"].append(_line([raiz, razao, nat, "49", _money(capital), porte, ""]))

        inicio = ref - timedelta(days=rng.randrange(30, 365 * 30))
        for ordem in range(1, rng.choice([1, 1, 1, 2, 3]) + 1):
            ordem_s = f"{ordem:04d}"
            cod_mun, _, uf = rng.choice(MUNICIPIOS)
            situacao = rng.choices(["02", "08", "04", "03"], weights=[80, 14, 5, 1])[0]
            motivo = "00" if situacao == "02" else rng.choice(["01", "21", "63", "32"])
            cep = f"{rng.randrange(10**7, 10**8):08d}"
            if i % 500 == 3:
                cep = cep.lstrip("0")[:7].rjust(7, "1")  # CEP com 7 dígitos (defeito real da fonte)
            exterior = i % 997 == 11
            cnae = rng.choice(CNAES)[0]
            sec = ",".join(rng.sample([c for c, _ in CNAES if c != cnae], rng.choice([0, 1, 2])))
            rows["estabelecimentos"].append(_line([
                raiz, ordem_s, cnpjlib.dv(raiz + ordem_s), "1" if ordem == 1 else "2",
                f"{rng.choice(PREFIXOS)} {rng.choice(NOMES)}" if rng.random() < 0.6 else "",
                situacao, _d(min(inicio + timedelta(days=rng.randrange(0, 300)), ref - timedelta(days=1))), motivo,
                "MIAMI" if exterior else "", "249" if exterior else "", _d(inicio), cnae, sec,
                "RUA", f"DAS FLORES {rng.randrange(1, 200)}", str(rng.randrange(1, 3000)), "",
                "CENTRO", cep, "EX" if exterior else uf, cod_mun,
                "61", f"3{rng.randrange(10**6, 10**7)}", "", "", "", "",
                f"CONTATO{i}@EXEMPLO.COM.BR", "", "",
            ]))

        for _ in range(rng.choice([1, 1, 2, 3])):
            if rng.random() < 0.08 and i > 10:  # sócio pessoa jurídica: CNPJ completo
                socio_raiz = raizes[rng.randrange(0, i)]
                doc = socio_raiz + "0001" + cnpjlib.dv(socio_raiz + "0001")
                ident, nome, faixa = "1", "HOLDING " + rng.choice(NOMES), "0"
            else:
                doc = f"***{rng.randrange(10**5, 10**6)}**"
                ident, nome, faixa = "2", f"{rng.choice(NOMES)} {rng.choice(NOMES)}", str(rng.randrange(2, 9))
            rows["socios"].append(_line([
                raiz, ident, nome, doc, rng.choice(["49", "22", "05"]), _d(inicio), "",
                "***000000**", "", "00", faixa,
            ]))

        if rng.random() < 0.6:
            mei = "S" if porte == "01" and rng.random() < 0.4 else "N"
            data_mei = _d(inicio) if mei == "S" else "0"
            rows["simples"].append(_line([raiz, "S", _d(inicio), "0", mei, data_mei, "0"]))

    for name, ent in ENTITIES.items():
        data = rows[name]
        if ent.partitioned:
            for part, fname in enumerate(ent.expected_files):
                write_zip(dest / fname, f"K3241.K{part:02d}.D{ano % 100:02d}{mes:02d}.{name.upper()[:8]}",
                          data[part::10])
        else:
            write_zip(dest / ent.expected_files[0], f"F.K03200$Z.D{ano % 100:02d}{mes:02d}.{name.upper()[:6]}", data)
    return dest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--competencia", required=True)
    p.add_argument("--empresas", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path("/data/landing"))
    a = p.parse_args()
    print(generate(a.competencia, a.out, a.empresas, a.seed))


if __name__ == "__main__":
    main()
