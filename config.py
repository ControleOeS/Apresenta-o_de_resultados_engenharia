from pathlib import Path

# Projeto totalmente independente do DASH_DIRETORIA — lê os arquivos Excel
# direto da pasta local (sem Dropbox, sem cache compartilhado). Mesma pasta
# de origem dos dados, mas nenhum código importado do outro projeto.
PASTA_DADOS = Path(
    r"C:\Users\lol\O&S GESTORA DE RECURSOS E PARTICIPACOES S A"
    r"\DAF - NOVA_ESTRUTURA\DASHBOARD DIRETORIA\RESULTADO 2026"
)

ARQUIVO_REALIZADO = PASTA_DADOS / "Resultado - 2026.xlsx"

# Base refinada da Engenharia (ACPL + Superus Holding + Superus Engenharia) —
# só REV00/REV01 têm a cascata completa até Lucro Líquido hoje. REV02/REV03
# ainda não têm Despesa nessa granularidade (ver conversa de 2026-10-13) —
# quando/se chegar um arquivo de REV02 completo, adicionar aqui.
ARQUIVO_PREVISTO_REV00_MOD = PASTA_DADOS / "REV00.ENG_BASE_PREV_REFINADO_MODERADO.xlsx"
ARQUIVO_PREVISTO_REV00_OTI = PASTA_DADOS / "REV00.ENG_BASE_PREV_REFINADO_OTIMISTA.xlsx"
ARQUIVO_PREVISTO_REV01_OTI = PASTA_DADOS / "ENG_BASE_PREV_REFINADO_OT_REV01.xlsx"

# Superus = ACPL + Superus Holding + Superus Engenharia (mesmo recorte do
# segmento "Superus Engenharia" no DASH_DIRETORIA, confirmado pelo usuário).
COLIGADAS_SUPERUS = [2, 16, 18]
