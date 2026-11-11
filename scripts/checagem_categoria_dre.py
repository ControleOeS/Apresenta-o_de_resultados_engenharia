"""Checagem automática pedida na auditoria de 2026-11-11 (item 2) — importa
as mesmas funções de cálculo usadas pelo app (nunca copia a lógica) e
confere, para toda combinação de mês x Revisão x Cenário, que a soma das
categorias/Centro de Custo fecha com a linha do DRE (tolerância R$1) para
Receita Bruta e Lucro Bruto — a divergência original do item 2 (585.167 /
522.325 / 91.811 de diferença, conforme as Revisões/meses) foi causada por
duas fontes distintas: REV02/REV03 não espelhavam o Realizado antes da
janela real de previsão da Revisão (Causa 1) e REV00/REV01 liam de um
arquivo diferente do usado pelo DRE (Causa 2) — ambas corrigidas em
analise_categoria.py (_por_cc_efetivo).

Roda com: python scripts/checagem_categoria_dre.py
Precisa de acesso ao Dropbox (mesma fonte de dados do app publicado) — sem
arquivo de exemplo local disponível neste projeto; se a carga falhar por
credencial, o script avisa e para (não inventa dados).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

TOLERANCIA = 1.0


def main() -> int:
    try:
        from dados import (
            calcular_previsto_com_fallback_despesa,
            carregar_previsto,
            carregar_previsto_refinado,
            carregar_realizado_superus,
            carregar_refinado_detalhado,
        )
        from analise_categoria import (
            custo_por_categoria_previsto,
            imposto_por_categoria_previsto,
            receita_por_categoria_previsto,
        )
    except Exception as exc:
        print(f"ERRO ao importar módulos: {exc}")
        return 1

    try:
        df_real = carregar_realizado_superus()
        df_previsto = carregar_previsto()
        df_refinado = carregar_previsto_refinado()
        df_refinado_detalhado = carregar_refinado_detalhado()
    except Exception as exc:
        print(f"ERRO ao carregar bases (credencial/Dropbox indisponível?): {exc}")
        print("Sem arquivo de exemplo local disponível neste projeto — não é possível seguir sem inventar dados.")
        return 1

    ano = 2026
    ultimo_mes_fechado = df_real.loc[df_real["Mes"].dt.year == ano, "Mes"].max()
    meses = pd.date_range(f"{ano}-01-01", ultimo_mes_fechado, freq="MS")
    mes_ini_ano = pd.Timestamp(year=ano, month=1, day=1)

    falhas: list[str] = []
    total = 0

    for revisao in ["REV00", "REV01", "REV02", "REV03"]:
        for cenario in ["Otimista", "Moderado"]:
            for mes_fim in meses:
                for mes_ini, label in [(mes_fim, "mês"), (mes_ini_ano, "acumulado")]:
                    dre_orc, _ = calcular_previsto_com_fallback_despesa(
                        df_previsto, df_refinado, revisao, cenario, mes_ini, mes_fim, df_real
                    )
                    if dre_orc is None:
                        continue

                    rec_cat = receita_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao, cenario, mes_ini, mes_fim)
                    custo_cat = custo_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao, cenario, mes_ini, mes_fim)
                    imp_cat = imposto_por_categoria_previsto(df_previsto, df_refinado_detalhado, df_real, revisao, cenario, mes_ini, mes_fim)
                    soma_receita = rec_cat.sum() if rec_cat is not None else None
                    soma_custo = custo_cat.sum() if custo_cat is not None else None
                    soma_imposto = imp_cat.sum() if imp_cat is not None else None

                    contexto = f"{revisao}/{cenario}/{label}/{mes_fim.strftime('%Y-%m')}"

                    total += 1
                    rb_dre = dre_orc.get("receita_bruta")
                    if rb_dre is not None and soma_receita is not None:
                        diff = rb_dre - soma_receita
                        if abs(diff) > TOLERANCIA:
                            falhas.append(f"Receita Bruta {contexto}: DRE={rb_dre:,.2f} categoria={soma_receita:,.2f} diff={diff:,.2f}")

                    total += 1
                    mb_dre = dre_orc.get("margem_bruta")
                    if mb_dre is not None and None not in (soma_receita, soma_imposto, soma_custo):
                        lucro_cat = soma_receita + soma_imposto + soma_custo
                        diff = mb_dre - lucro_cat
                        if abs(diff) > TOLERANCIA:
                            falhas.append(f"Lucro Bruto {contexto}: DRE={mb_dre:,.2f} categoria={lucro_cat:,.2f} diff={diff:,.2f}")

    print(f"TOTAL: {total} checagens · {total - len(falhas)} OK · {len(falhas)} FALHARAM")
    if falhas:
        print("\nFALHAS:")
        for f in falhas:
            print(f"  - {f}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
