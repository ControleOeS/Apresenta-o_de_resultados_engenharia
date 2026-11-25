from pathlib import Path

# Até 2026-10-21 este projeto lia os arquivos Excel direto da pasta local.
# Pra publicar na web (Streamlit Community Cloud, sem acesso ao disco local),
# passou a ler tudo do Dropbox — mesma conta/app do DASH_DIRETORIA (reuso
# pedido pelo usuário, já que vários desses arquivos já são sincronizados
# por ele). Os caminhos locais abaixo continuam existindo só pra uso pelos
# scripts `sync_*.py` (que leem o arquivo local e sobem pro Dropbox); o app
# em si (dados.py) não lê mais nada em disco.
PASTA_DADOS = Path(
    r"C:\Users\lol\O&S GESTORA DE RECURSOS E PARTICIPACOES S A"
    r"\DAF - NOVA_ESTRUTURA\DASHBOARD DIRETORIA\RESULTADO 2026"
)

ARQUIVO_REALIZADO = PASTA_DADOS / "Resultado - 2026.xlsx"
# "/dados.xlsx" (não "/Resultado - 2026.xlsx") porque é o mesmo arquivo que o
# DASH_DIRETORIA já sincroniza com esse nome (sync_to_dropbox.py de lá,
# agendado no Task Scheduler) — reaproveitando, sem sincronização duplicada.
DROPBOX_REALIZADO = "/dados.xlsx"

# Realizado 2025 (adicionado pelo usuário em 2026-10-20) — DRE mensal
# pronta (Jan-Dez/25), usada só pra comparação Real. 2026 x Real. 2025 na
# DRE Mês/Acumulado. Ver dados.py (carregar_realizado_2025_mensal) pro
# mapeamento exato de linhas/colunas da aba.
ARQUIVO_RESULTADO_2025 = PASTA_DADOS / "RESULTADOS 2025.xlsx"
# Novo no Dropbox — sem sincronização agendada (dado histórico, não muda
# mais), sobe uma vez via sync_to_dropbox.py deste projeto.
DROPBOX_RESULTADO_2025 = "/RESULTADOS 2025.xlsx"

# Base refinada da Engenharia (ACPL + Superus Holding + Superus Engenharia) —
# só REV00/REV01 têm a cascata completa até Lucro Líquido hoje. REV02/REV03
# ainda não têm Despesa nessa granularidade (ver conversa de 2026-10-13) —
# quando/se chegar um arquivo de REV02 completo, adicionar aqui.
ARQUIVO_PREVISTO_REV00_MOD = PASTA_DADOS / "REV00.ENG_BASE_PREV_REFINADO_MODERADO.xlsx"
ARQUIVO_PREVISTO_REV00_OTI = PASTA_DADOS / "REV00.ENG_BASE_PREV_REFINADO_OTIMISTA.xlsx"
ARQUIVO_PREVISTO_REV01_OTI = PASTA_DADOS / "ENG_BASE_PREV_REFINADO_OT_REV01.xlsx"
# Já sincronizados pelo DASH_DIRETORIA (upload manual de lá, valores não
# mudam mais) — reaproveitando os mesmos caminhos no Dropbox.
DROPBOX_PREVISTO_REV00_MOD = "/REV00.ENG_BASE_PREV_REFINADO_MODERADO.xlsx"
DROPBOX_PREVISTO_REV00_OTI = "/REV00.ENG_BASE_PREV_REFINADO_OTIMISTA.xlsx"
DROPBOX_PREVISTO_REV01_OTI = "/ENG_BASE_PREV_REFINADO_OT_REV01.xlsx"

# Dados Refinado (REV00-REV03) — só vai até Margem Bruta (nenhuma Revisão
# tem Despesa Administrativa/Financeira aqui, confirmado inspecionando o
# arquivo em 2026-10-14). Usado pra trazer REV02/REV03 de Receita/Custo;
# a Despesa dessas revisões usa a da REV01 como provisório (ver dados.py),
# por instrução explícita do usuário, até a Despesa real de REV02/REV03
# ser lançada.
ARQUIVO_REFINADO_ENGENHARIAS = PASTA_DADOS / "REFINADO ENGENHARIAS 2026 - BI BRANCO OFICIAL.xlsx"
# Já sincronizado semanalmente pelo DASH_DIRETORIA (sync_refinado.py de lá) —
# reaproveitando o mesmo caminho no Dropbox.
DROPBOX_REFINADO_ENGENHARIAS = "/REFINADO ENGENHARIAS 2026 - BI BRANCO OFICIAL.xlsx"

# Despesa própria da REV02 (adicionada pelo usuário em 2026-10-20) — cobre
# Jul-Dez-26, por departamento, já com subtotais prontos (Administrativa/
# Comercial/Operação). Ver dados.py pra como isso se combina com o
# Realizado (meses fechados).
ARQUIVO_DESPESA_REV02 = PASTA_DADOS / "DESPESA REV02.xlsx"
# Novo no Dropbox — sem sincronização agendada (mesma política da REV00/REV01
# Engenharia: upload manual quando o usuário atualizar o arquivo).
DROPBOX_DESPESA_REV02 = "/DESPESA REV02.xlsx"

# Despesa própria da REV03 — NÃO é o DESPESA REV03.xlsx (abandonado em
# 2026-10-20: o usuário confirmou que a Despesa Administrativa/Financeira
# de verdade da REV03 está inteira na aba "Dados Refinado" do
# ONEPAGE_REV03.xlsx, igual ao que o DASH_DIRETORIA já usa — mesmo arquivo,
# "Análise de emissão" = "DESPESA ADMINISTRATIVA" (por Centro de Custo,
# Out-Dez/26) e "DESPESA FINANCEIRA" (agregado, Out-Dez/26); Moderado e
# Otimista são idênticos pra Despesa, confirmado pelo usuário). Cobre só
# REV03 — REV00/REV01/REV02 não têm essas duas análises nessa aba.
ARQUIVO_ONEPAGE_REV03 = PASTA_DADOS / "ONEPAGE_REV03.xlsx"
# Já sincronizado pelo DASH_DIRETORIA (upload manual de lá, sync_previsto.py)
# — reaproveitando o mesmo caminho no Dropbox.
DROPBOX_ONEPAGE_REV03 = "/ONEPAGE_REV03.xlsx"

# Superus = ACPL + Superus Holding + Superus Engenharia (mesmo recorte do
# segmento "Superus Engenharia" no DASH_DIRETORIA, confirmado pelo usuário).
COLIGADAS_SUPERUS = [2, 16, 18]
COLIGADAS_ASAP = [14]
COLIGADAS_OES = [11]
# Grupo = Superus + ASAP, SEM a O&S — pedido explícito do usuário,
# 2026-11-24: a Receita da O&S é o rateio de despesa cobrado de ASAP/
# Superus pelos próprios serviços administrativos da O&S, então somá-la
# direto contaria a mesma coisa duas vezes (uma como Receita da O&S, outra
# já embutida na Despesa de quem paga). Mesma regra já usada no
# DASH_DIRETORIA (coligadas_dos_grupos/coligada_os_excluida em dre.py).
COLIGADAS_GRUPO = COLIGADAS_SUPERUS + COLIGADAS_ASAP

# Previsto ASAP (REV00-REV02, upload manual — mesma política de todo
# Previsto deste app, nunca Task Scheduler). Já sincronizados pelo
# DASH_DIRETORIA — reaproveitando os mesmos caminhos no Dropbox (pedido do
# usuário, 2026-11-24, igual ao reuso já feito pro Previsto da Engenharia).
DROPBOX_ASAP_REV00_MOD = "/REV00_ASAP_BASE_PREV_REFINADO_MOD.xlsx"
DROPBOX_ASAP_REV00_OTI = "/REV00_ASAP_BASE_PREV_REFINADO_OT.xlsx"
DROPBOX_ASAP_REV01_MOD = "/REV01_ASAP_BASE_PREV_REFINADO_MD.xlsx"
DROPBOX_ASAP_REV01_OTI = "/REV01_ASAP_BASE_PREV_REFINADO_OT.xlsx"
DROPBOX_ASAP_REV02_MOD = "/ASAP_REV02_2026 Moderado.xlsx"
DROPBOX_ASAP_REV02_OTI = "/ASAP_REV02_2026 Otimista.xlsx"
# REV03: um único arquivo (aba "DePara_CC", linha a linha por Centro de
# Custo com a classificação "Grupo DRE") usado como Moderado E Otimista —
# pedido explícito do usuário, 2026-11-25 ("utilize esse valor como
# moderado e otimista da ASAP"), não tem uma base Moderado separada ainda.
DROPBOX_ASAP_REV03 = "/ASAP_REV03_2026 Otimista.xlsx"

# Forecast manual da ASAP (grade de Receita Bruta/Lucro Bruto por Cliente,
# mesma ideia do Forecast da Superus) — arquivo PRÓPRIO, não compartilhado
# com o DROPBOX_FORECAST da Superus (linhas/Clientes diferentes).
DROPBOX_FORECAST_ASAP = "/app_forecast_receita_margem_asap.json"

# Previsto O&S (só REV00/REV02 — não existe REV01/REV03 pra O&S, upload
# manual). Já sincronizados pelo DASH_DIRETORIA — mesmos caminhos no Dropbox.
DROPBOX_OES_REV00_MOD = "/OES_BASE_PREV_REFINADO_MOD.xlsx"
DROPBOX_OES_REV00_OTI = "/OES_BASE_PREV_REFINADO_OT1.xlsx"
DROPBOX_OES_REV02_MOD = "/REV2-DRE OES MODERADO.xlsx"
DROPBOX_OES_REV02_OTI = "/REV2-DRE OES OTIMISTA.xlsx"

# Classificação manual de Centro de Custo -> categoria (Receita: BackLog
# Ativo/Novo/Inativo, Funil de Vendas, etc.; Despesa/SGA: Operação,
# Comercial, Administração...). Até 2026-10-21 persistia em disco local
# (dados_locais/, fora do git); passou a persistir no Dropbox pra sobreviver
# a reinício/redeploy na nuvem e ficar igual pra qualquer um que abrir o
# link (não é mais "por computador", é um dado só, compartilhado).
DROPBOX_CLASSIFICACOES = "/app_classificacao_centros_custo.json"
DROPBOX_CATEGORIAS = "/app_categorias.json"

# Simulador de Forecast (páginas 6/7 da apresentação de referência) —
# preenchimento manual de Receita Bruta por Centro de Custo e Margem Bruta %
# por mês, pros meses que ainda não têm Realizado. Único arquivo (não por
# Revisão/Cenário — por pedido do usuário, 2026-10-20): é pré-preenchido com
# os valores da Revisão mais recente já em vigor, mas o preenchimento salvo
# é um só, que o usuário vai editando conforme o ano avança.
DROPBOX_FORECAST = "/app_forecast_receita_margem.json"

# Meta Ano Superus (adicionado pelo usuário em 2026-10-21) — DRE anual
# alvo/meta, 3 cenários (abas Otimista/Moderado/Pessimista), valores em R$
# mil. Usado só como comparativo na DRE do Forecast (ver forecast.py:
# carregar_meta_otimista_mensal) — não entra em nenhum cálculo.
ARQUIVO_META_SUPERUS = PASTA_DADOS / "META ANO SUPERUS.xlsx"
# Novo no Dropbox — sem sincronização agendada, upload manual quando mudar.
DROPBOX_META_SUPERUS = "/META ANO SUPERUS.xlsx"
