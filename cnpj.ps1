<#
  Atalhos da plataforma DataOps do CNPJ (Windows / PowerShell).

  Uso:  .\cnpj.ps1 <comando> [argumentos]

    up                      Constrói as imagens e sobe tudo (Postgres, Airflow, Sentinel, MCP)
    down                    Para os containers (mantém os dados)
    status                  Containers + competências processadas + últimos incidentes
    logs [servico]          Acompanha os logs (padrão: airflow-scheduler)
    rodar [AAAA-MM]         Ativa e dispara a DAG (sem mês = última competência publicada)
    amostra AAAA-MM         Gera uma competência sintética no landing (teste sem internet)
    injetar CHAVE AAAA-MM   Injeta uma falha do chaos (ex.: invalid_cnpj, multi_failure_cascade)
    falhas                  Lista as falhas injetáveis
    sentinel                Roda o Sentinel agora sobre os incidentes pendentes
    evals                   Mede os critérios de aceite (AC-1..AC-6)
    consulta "SQL"          SELECT somente leitura no DuckDB (gold/silver)
    psql                    Abre o psql no banco da plataforma
    limpar-teste            Apaga amostras, warehouse e ledger (antes da primeira carga real)
#>
param(
    [Parameter(Position = 0)][string]$Comando = "ajuda",
    [Parameter(Position = 1)][string]$Arg1,
    [Parameter(Position = 2)][string]$Arg2
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-EnvValue([string]$name, [string]$default) {
    $line = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match "^$name=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1].Trim() } else { return $default }
}

switch ($Comando) {
    "up" {
        if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Criei o .env a partir do .env.example. Edite as senhas e rode de novo." -ForegroundColor Yellow; exit 1 }
        docker compose up -d --build
        Write-Host "`nAirflow: http://localhost:8080  |  MCP: http://localhost:8000/mcp" -ForegroundColor Green
    }
    "down"   { docker compose down }
    "status" {
        docker compose ps
        $u = Get-EnvValue "PG_USER" "cnpj"; $d = Get-EnvValue "PG_DB" "cnpj"
        docker compose exec -T postgres psql -U $u -d $d -c "SELECT competencia, status, detalhe, iniciado_em, finalizado_em FROM ops.competencias ORDER BY 1 DESC LIMIT 5;"
        docker compose exec -T postgres psql -U $u -d $d -c "SELECT incident_id, failure_key, origin, competencia, status, left(detail, 60) AS detalhe FROM ops.incidents ORDER BY 1 DESC LIMIT 10;"
        docker compose exec -T postgres psql -U $u -d $d -c "SELECT diagnosis_id, route, failure_key, sub_failures, score_tier, match_score FROM ops.diagnoses ORDER BY 1 DESC LIMIT 5;"
    }
    "logs" { $s = if ($Arg1) { $Arg1 } else { "airflow-scheduler" }; docker compose logs -f --tail 200 $s }
    "rodar" {
        docker compose exec airflow-apiserver airflow dags unpause receita_cnpj_mensal
        if ($Arg1) {
            $conf = '{"competencia": "' + $Arg1 + '"}'
            docker compose exec airflow-apiserver airflow dags trigger receita_cnpj_mensal --conf $conf
        } else {
            docker compose exec airflow-apiserver airflow dags trigger receita_cnpj_mensal
        }
        Write-Host "Acompanhe em http://localhost:8080" -ForegroundColor Green
    }
    "amostra" {
        if (-not $Arg1) { throw "informe a competência: .\cnpj.ps1 amostra 2026-08" }
        docker compose run --rm sentinel python -m chaos.cli sample --competencia $Arg1
    }
    "injetar" {
        if (-not $Arg1 -or -not $Arg2) { throw "uso: .\cnpj.ps1 injetar invalid_cnpj 2026-08" }
        docker compose run --rm sentinel python -m chaos.cli inject $Arg1 --competencia $Arg2
    }
    "falhas"   { docker compose run --rm sentinel python -m chaos.cli list }
    "sentinel" { docker compose exec sentinel python -m sentinel.trigger --once }
    "evals"    { docker compose exec mcp python -m pipeline.evals }
    "consulta" {
        if (-not $Arg1) { throw 'uso: .\cnpj.ps1 consulta "SELECT * FROM gold.gold_resumo_competencia"' }
        docker compose exec -T mcp python -c "import sys; from sentinel.tools.readers import run_guarded_select as q; print(q(sys.argv[1]))" $Arg1
    }
    "psql" {
        $u = Get-EnvValue "PG_USER" "cnpj"; $d = Get-EnvValue "PG_DB" "cnpj"
        docker compose exec postgres psql -U $u -d $d
    }
    "limpar-teste" {
        $ok = Read-Host "Isto apaga landing, warehouse e o ledger ops. Digite SIM para continuar"
        if ($ok -ne "SIM") { exit 0 }
        docker compose run --rm --user 0 sentinel sh -c "rm -rf /data/landing/* /data/warehouse/* /data/work/* /data/sentinel/* /data/logs/*"
        $u = Get-EnvValue "PG_USER" "cnpj"; $d = Get-EnvValue "PG_DB" "cnpj"
        docker compose exec -T postgres psql -U $u -d $d -c "TRUNCATE ops.incidents, ops.dq_metrics, ops.competencias, ops.diagnoses RESTART IDENTITY;"
        Write-Host "Ambiente de teste limpo." -ForegroundColor Green
    }
    default { Get-Help $PSCommandPath -Detailed | Out-String | Write-Host }
}
