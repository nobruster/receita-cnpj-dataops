"""Configuração central — tudo vem de variáveis de ambiente (arquivo .env).

Nenhum segredo fica no código (regra R8 herdada do ws-3). Os valores padrão
funcionam dentro do docker-compose; para rodar fora do Docker basta exportar as
variáveis ou criar um .env na raiz.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Fonte: Nextcloud da Receita Federal (WebDAV público) -----------------
    rfb_webdav_url: str = "https://arquivos.receitafederal.gov.br/public.php/webdav"
    rfb_share_token: str = ""  # obrigatório no .env (token do link público da Receita); nunca no código
    rfb_verify_ssl: bool = True
    rfb_ca_bundle: str | None = None  # CA corporativa (proxy com inspeção TLS)
    rfb_connect_timeout: float = 30.0
    rfb_stall_timeout: float = 120.0  # segundos sem receber bytes => retoma
    download_workers: int = 3
    download_retries: int = 8
    # Modo offline: não acessa a Receita; processa os zips já colocados em
    # /data/landing/AAAA-MM (rede bloqueada, cópia manual ou testes com o chaos).
    offline_mode: bool = False

    # --- Diretórios (volume /data no container) -------------------------------
    data_dir: Path = Path("/data")

    # --- DuckDB (motor de processamento) ---------------------------------------
    duckdb_memory_limit: str = "8GB"
    duckdb_threads: int = 4
    duckdb_lock_wait_s: int = 600  # escritor espera leitores/escritores soltarem o arquivo

    # --- PostgreSQL (camada de consumo + ledger de incidentes) ----------------
    pg_host: str = "postgres"
    pg_port: int = 5432
    pg_db: str = "cnpj"
    pg_user: str = "cnpj"
    pg_password: str = ""  # obrigatório no .env; nunca no código
    # Papel publisher (publicação BI): conexão separada do usuário cnpj.
    publisher_user: str = "publisher"
    publisher_password: str = ""  # obrigatório no .env; nunca no código
    publish_schema: str = "gold"
    publish_enabled: bool = True
    # Tabelas gold copiadas para o Postgres. gold_empresa_detalhe (dezenas de
    # milhões de linhas, larga) fica de fora por padrão: adicione se o Power BI precisar.
    publish_tables: str = "gold_resumo_competencia,gold_painel_prospeccao,gold_rede_societaria"

    # --- Qualidade (limiares dos monitores determinísticos) -------------------
    dq_volume_drop_pct: float = 5.0  # queda de linhas vs competência anterior
    dq_reject_rate_pct: float = 0.5  # % de linhas em *_rejects por entidade
    dq_stale_days: int = 45  # dias sem nova competência => stale_release
    landing_retention: int = 2  # competências de zips mantidas no landing (~6 GB cada; mínimo 1)

    # --- Sentinel (LLM configurável; padrão OpenAI via OPENAI_API_KEY) ---------
    # Tiering herdado do ws-3: gerente num modelo mais forte, especialistas no
    # modelo barato. provider=none => só o caminho determinístico (sem LLM).
    sentinel_llm_provider: str = "openai"  # openai | ollama | none
    sentinel_llm_model: str = "openai/gpt-5.6-luna"
    sentinel_manager_model: str = "openai/gpt-5.6-terra"
    openai_api_key: str | None = None
    ollama_base_url: str = "http://ollama:11434"

    # --- Derivados ------------------------------------------------------------
    @property
    def landing_dir(self) -> Path:
        return self.data_dir / "landing"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "work"

    @property
    def warehouse_path(self) -> Path:
        return self.data_dir / "warehouse" / "cnpj.duckdb"

    @property
    def duckdb_temp_dir(self) -> Path:
        return self.data_dir / "work" / "duckdb_tmp"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} "
            f"user={self.pg_user} password={self.pg_password}"
        )

    @property
    def publisher_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} "
            f"user={self.publisher_user} password={self.publisher_password}"
        )

    def ensure_dirs(self) -> None:
        for d in (self.landing_dir, self.work_dir, self.warehouse_path.parent, self.duckdb_temp_dir,
                  self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
