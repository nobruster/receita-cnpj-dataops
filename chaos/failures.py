"""Registro de falhas injetáveis — o equivalente Receita das 14 falhas do ws-3.

Cada falha altera os zips de uma competência no landing e grava a VERDADE DE
REFERÊNCIA em ``ops.incidents`` (``origin='chaos'``). O Sentinel nunca vê essas
linhas (as ferramentas filtram ``origin <> 'chaos'``); o oráculo de pontuação sim.

O mapa falha -> quem detecta -> superfície de evidência -> capacidade CrewAI é
vinculante (regra R6 herdada): o crew precisa dar conta de todas.
"""

from __future__ import annotations

import random
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pipeline.receita.layout import ENTITIES


@dataclass(frozen=True, slots=True)
class Failure:
    key: str
    descricao: str
    detected_by: str  # log_analyst | data_profiler | monitor | flow
    evidence_surface: str
    unlocks: str  # capacidade CrewAI que a falha exercita
    inject: Callable[[Path, random.Random], str]


# --- utilitários de zip -------------------------------------------------------

def _read(path: Path) -> tuple[str, list[str]]:
    with zipfile.ZipFile(path) as z:
        info = z.infolist()[0]
        text = z.read(info).decode("latin-1")
    return info.filename, [ln for ln in text.split("\n") if ln]


def _write(path: Path, member: str, lines: list[str], raw: bytes | None = None) -> None:
    data = raw if raw is not None else ("\n".join(lines) + "\n").encode("latin-1")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(member, data)


def _fields(line: str) -> list[str]:
    return [f.strip('"') for f in line.split('";"')]


def _join(fields: list[str]) -> str:
    return '"' + '";"'.join(fields) + '"'


def _mutate(landing: Path, fname: str, n: int, fn: Callable[[list[str]], list[str]], rng: random.Random) -> int:
    path = landing / fname
    member, lines = _read(path)
    idx = rng.sample(range(len(lines)), min(n, len(lines)))
    for i in idx:
        lines[i] = _join(fn(_fields(lines[i])))
    _write(path, member, lines)
    return len(idx)


# --- injetores ----------------------------------------------------------------

def _invalid_cnpj(landing: Path, rng: random.Random) -> str:
    def bad_dv(f: list[str]) -> list[str]:
        f[2] = f"{(int(f[2]) + 11) % 100:02d}"
        return f
    n = _mutate(landing, "Estabelecimentos1.zip", 25, bad_dv, rng)
    return f"{n} estabelecimentos com DV errado em Estabelecimentos1.zip"


def _duplicate_key(landing: Path, rng: random.Random) -> str:
    member, lines = _read(landing / "Estabelecimentos2.zip")
    dup = rng.sample(lines, 30)
    _write(landing / "Estabelecimentos2.zip", member, lines + dup)
    return "30 estabelecimentos duplicados em Estabelecimentos2.zip"


def _invalid_date(landing: Path, rng: random.Random) -> str:
    def bad(f: list[str]) -> list[str]:
        f[10] = rng.choice(["20261399", "20990101", "18000101"])
        return f
    n = _mutate(landing, "Estabelecimentos3.zip", 25, bad, rng)
    return f"{n} datas de início impossíveis em Estabelecimentos3.zip"


def _invalid_domain(landing: Path, rng: random.Random) -> str:
    def bad(f: list[str]) -> list[str]:
        f[5] = "07"  # situação cadastral inexistente
        return f
    n = _mutate(landing, "Estabelecimentos4.zip", 25, bad, rng)
    return f"{n} situações cadastrais '07' em Estabelecimentos4.zip"


def _invalid_capital(landing: Path, rng: random.Random) -> str:
    def bad(f: list[str]) -> list[str]:
        f[4] = "-" + f[4]
        return f
    n = _mutate(landing, "Empresas5.zip", 25, bad, rng)
    return f"{n} capitais sociais negativos em Empresas5.zip"


def _encoding_mojibake(landing: Path, rng: random.Random) -> str:
    path = landing / "Empresas6.zip"
    member, lines = _read(path)
    idx = set(rng.sample(range(len(lines)), 20))
    # simula trecho reexportado em UTF-8: "AÇÃO" vira bytes C3 87 C3 83, que lidos
    # como latin-1 aparecem como "AÃ\x87Ã\x83O" (mojibake) na razão social.
    raw = b"\n".join(
        (ln.encode("latin-1") if i not in idx
         else ln.encode("latin-1").replace(b'";"', ('";"' + "AÇÃO ").encode("utf-8"), 1))
        for i, ln in enumerate(lines)
    ) + b"\n"
    _write(path, member, [], raw=raw)
    return "20 razões sociais gravadas em UTF-8 dentro de arquivo latin-1 (Empresas6.zip)"


def _orphan_socio(landing: Path, rng: random.Random) -> str:
    member, lines = _read(landing / "Socios7.zip")
    novos = []
    for i in range(30):
        f = _fields(rng.choice(lines))
        f[0] = f"{99000000 + i:08d}"  # raiz que não existe em Empresas
        novos.append(_join(f))
    _write(landing / "Socios7.zip", member, lines + novos)
    return "30 sócios apontando para CNPJ básico inexistente (Socios7.zip)"


def _volume_drop(landing: Path, rng: random.Random) -> str:
    total = removidas = 0
    for fname in ENTITIES["estabelecimentos"].expected_files:
        member, lines = _read(landing / fname)
        keep = [ln for ln in lines if rng.random() > 0.25]
        total += len(lines)
        removidas += len(lines) - len(keep)
        _write(landing / fname, member, keep)
    return f"{removidas} de {total} estabelecimentos removidos (~25%): entrega parcial da Receita"


def _orphan_domain(landing: Path, rng: random.Random) -> str:
    def bad(f: list[str]) -> list[str]:
        f[11] = "9999999"  # CNAE que não existe em Cnaes.zip
        return f
    n = _mutate(landing, "Estabelecimentos5.zip", 60, bad, rng)
    return f"{n} estabelecimentos com CNAE principal ausente do domínio (Estabelecimentos5.zip)"


def _layout_drift(landing: Path, rng: random.Random) -> str:
    member, lines = _read(landing / "Empresas3.zip")
    _write(landing / "Empresas3.zip", member, [ln + ';"NOVA_COLUNA"' for ln in lines])
    return "Empresas3.zip passou a ter 8 colunas (layout oficial: 7)"


def _missing_file(landing: Path, rng: random.Random) -> str:
    (landing / "Socios8.zip").unlink()
    return "Socios8.zip ausente da competência"


def _corrupt_zip(landing: Path, rng: random.Random) -> str:
    path = landing / "Estabelecimentos6.zip"
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    return "Estabelecimentos6.zip truncado pela metade (download interrompido)"


def _source_unavailable(landing: Path, rng: random.Random) -> str:
    # Não mexe no landing: a falha é da FONTE. Quem roda o ciclo aponta RFB_WEBDAV_URL
    # para um endereço inalcançável (o e2e faz isso; no Docker, edite o .env).
    return "servidor WebDAV da Receita inalcançável (RFB_WEBDAV_URL inválida)"


FAILURES: dict[str, Failure] = {
    f.key: f
    for f in (
        Failure("invalid_cnpj", "DV do CNPJ não confere", "data_profiler",
                "silver_estabelecimentos_rejects", "base crew", _invalid_cnpj),
        Failure("duplicate_key", "Estabelecimento repetido", "data_profiler",
                "silver_estabelecimentos_rejects", "HITL (correção destrutiva)", _duplicate_key),
        Failure("invalid_date", "Data impossível", "data_profiler",
                "silver_estabelecimentos_rejects", "base crew", _invalid_date),
        Failure("invalid_domain", "Código fora do domínio", "data_profiler",
                "silver_estabelecimentos_rejects", "base crew", _invalid_domain),
        Failure("invalid_capital", "Capital social negativo", "data_profiler",
                "silver_empresas_rejects", "base crew", _invalid_capital),
        Failure("encoding_mojibake", "UTF-8 dentro de arquivo latin-1", "data_profiler",
                "silver_empresas_rejects", "Guardrails + output_pydantic", _encoding_mojibake),
        Failure("orphan_socio", "Sócio sem empresa", "data_profiler",
                "silver_socios_rejects", "base crew", _orphan_socio),
        Failure("volume_drop", "Queda de volume vs mês anterior", "monitor",
                "ops.dq_metrics", "HITL (reprocessar competência)", _volume_drop),
        Failure("orphan_domain", "Código válido na forma, ausente do domínio", "monitor",
                "silver_estabelecimentos._orphan_cnae", "Knowledge/RAG (runbook desambigua)", _orphan_domain),
        Failure("layout_drift", "Mudança de layout", "log_analyst",
                "pipeline_logs", "Tool reliability", _layout_drift),
        Failure("missing_file", "Arquivo ausente", "log_analyst",
                "pipeline_logs", "Tool reliability", _missing_file),
        Failure("corrupt_zip", "Zip corrompido", "log_analyst",
                "pipeline_logs", "Tool reliability", _corrupt_zip),
        Failure("source_unavailable", "Fonte da Receita fora do ar", "log_analyst",
                "pipeline_logs", "Tool reliability", _source_unavailable),
    )
}

CASCADE_KEY = "multi_failure_cascade"
CASCADE_MEMBERS: tuple[str, ...] = ("invalid_cnpj", "orphan_socio", "volume_drop")
# Falhas da FONTE não pertencem a uma competência: a verdade vai para a pseudo-competência ``fonte``.
SOURCE_KEYS: frozenset[str] = frozenset({"source_unavailable"})
PIPELINE_KEYS: frozenset[str] = frozenset(k for k, f in FAILURES.items() if f.detected_by == "log_analyst")
