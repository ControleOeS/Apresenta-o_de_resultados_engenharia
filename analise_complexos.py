"""Análise de Complexos (páginas 10/11 da apresentação de referência).

Unidade usada aqui = Centro de Custo direto (não agrupado em "Complexo"
comercial) — o agrupamento pela coluna "Complexo" do Realizado cobria só
~32 dos Centro de Custo de Receita, com boa parte das linhas caindo em
"SEM AGRUPAMENTO"; por pedido do usuário, trocamos pra Centro de Custo
puro, que não depende de nenhum agrupamento adivinhado e cobre todo CC
que já apareceu em Receita Bruta (Realizado ou Orçado).

O Orçado por Centro de Custo vem do Refinado Engenharias (cobre as 4
Revisões — REV00 a REV03), não do df_previsto "antigo" (só tem CC-level
pra REV00/REV01: ex. só 29 Centro de Custo de Receita na REV01, contra
57 no Realizado — REV03 no Refinado já bate as 57). O nome de exibição
vem da tabela dimensão (dados.tabela_dimensao_centro_de_custo), com
fallback pro nome visto no Realizado/Refinado pra CC que ela não cobrir.

Critério de status confirmado com o usuário:
- Ativo: tem Receita Bruta faturada no mês de referência.
- Inativo: já faturou Receita Bruta antes, mas não no mês de referência.
- Novo Mobilizado: 1º faturamento caiu dentro dos últimos 3 meses
  (contando o mês de referência).
- Em Mobilização: nunca faturou Receita, mas aparece no Orçado/Previsto
  da Revisão/Cenário selecionada."""

import pandas as pd

from dados import NIVEL_CUSTO, NIVEL_RECEITA_BRUTA, custo_por_cc_refinado, receita_por_cc_refinado

MESES_NOVO_MOBILIZADO = 3

STATUS_ATIVO = "Backlog Ativo"
STATUS_INATIVO = "Backlog Inativo"
STATUS_NOVO = "Backlog Novo Mobilizado"
STATUS_MOBILIZACAO = "Backlog Novo Em Mobilização"


def _serie_por_cc(df: pd.DataFrame, niveis: list[int], mes_ini=None, mes_fim=None) -> pd.Series:
    sub = df[df["Nível 1"].isin(niveis)]
    if mes_ini is not None:
        sub = sub[(sub["Mes"] >= mes_ini) & (sub["Mes"] <= mes_fim)]
    return sub.groupby("Cod. Centro de Custo")["Valor"].sum()


class AnaliseComplexos:
    def __init__(
        self,
        df_real: pd.DataFrame,
        df_refinado_detalhado: pd.DataFrame,
        tabela_dimensao: pd.DataFrame,
        mes_ref,
        mes_ini_ano,
        revisao: str,
        cenario: str,
    ):
        sub_receita = df_real[df_real["Nível 1"].isin(NIVEL_RECEITA_BRUTA) & (df_real["Valor"] != 0)].copy()
        sub_receita["Cod. Centro de Custo"] = sub_receita["Cod. Centro de Custo"].astype(str)
        self._primeiro_mes_cc = sub_receita.groupby("Cod. Centro de Custo")["Mes"].min().to_dict()
        self._meses_com_receita_cc = sub_receita.groupby("Cod. Centro de Custo")["Mes"].agg(set).to_dict()

        # Nome: tabela dimensão primeiro (fonte canônica), senão o nome
        # visto no Realizado, senão o do Refinado (CC sem nenhum dos dois
        # mostra o próprio código).
        self._nomes_cc = tabela_dimensao.set_index("Codigo")["Centro de Custo"].to_dict()
        for cc, nome in sub_receita.drop_duplicates("Cod. Centro de Custo").set_index("Cod. Centro de Custo")["Centro de Custo"].items():
            self._nomes_cc.setdefault(cc, nome)

        self.receita_orc_mes = receita_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ref, mes_ref)
        self.receita_orc_acum = receita_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini_ano, mes_ref)
        self._ccs_com_orcado = set(self.receita_orc_acum.index)

        self.complexos = sorted(set(self._primeiro_mes_cc) | self._ccs_com_orcado)
        self.mes_ref = mes_ref

        self.receita_real_mes = _serie_por_cc(df_real, NIVEL_RECEITA_BRUTA, mes_ref, mes_ref)
        self.receita_real_acum = _serie_por_cc(df_real, NIVEL_RECEITA_BRUTA, mes_ini_ano, mes_ref)

        custo_real_mes = _serie_por_cc(df_real, NIVEL_CUSTO, mes_ref, mes_ref)
        custo_real_acum = _serie_por_cc(df_real, NIVEL_CUSTO, mes_ini_ano, mes_ref)
        custo_orc_mes = custo_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ref, mes_ref)
        custo_orc_acum = custo_por_cc_refinado(df_refinado_detalhado, revisao, cenario, mes_ini_ano, mes_ref)

        self.lucro_real_mes = self.receita_real_mes.add(custo_real_mes, fill_value=0)
        self.lucro_real_acum = self.receita_real_acum.add(custo_real_acum, fill_value=0)
        self.lucro_orc_mes = self.receita_orc_mes.add(custo_orc_mes, fill_value=0)
        self.lucro_orc_acum = self.receita_orc_acum.add(custo_orc_acum, fill_value=0)

    def nome(self, cc: str) -> str:
        return self._nomes_cc.get(cc, cc)

    def status(self, cc: str) -> str:
        meses_com_receita = self._meses_com_receita_cc.get(cc, set())
        primeiro_mes = self._primeiro_mes_cc.get(cc)
        if self.mes_ref in meses_com_receita:
            if primeiro_mes is not None:
                meses_desde_inicio = (self.mes_ref.year - primeiro_mes.year) * 12 + (self.mes_ref.month - primeiro_mes.month)
                if meses_desde_inicio < MESES_NOVO_MOBILIZADO:
                    return STATUS_NOVO
            return STATUS_ATIVO
        if primeiro_mes is not None:
            return STATUS_INATIVO
        if cc in self._ccs_com_orcado:
            return STATUS_MOBILIZACAO
        return STATUS_INATIVO

    def status_todos(self) -> dict[str, str]:
        return {c: self.status(c) for c in self.complexos}

    def complexos_operando(self) -> list[str]:
        """Backlog Ativo + Novo Mobilizado — só esses têm Real x Orçado
        comparável (Inativo não fatura mais, Em Mobilização nunca faturou)."""
        status = self.status_todos()
        return [c for c, s in status.items() if s in (STATUS_ATIVO, STATUS_NOVO)]
