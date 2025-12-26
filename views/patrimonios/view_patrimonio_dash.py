from __future__ import annotations

import io
import math
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from controllers.patrimonio_controller import (
    agrupar_por_categoria,
    agrupar_por_estado,
    agrupar_por_situacao,
    cadastrar_patrimonio,
    calcular_indicadores,
    deletar_patrimonios,
    evolucao_por_mes,
    listar_patrimonios,
    salvar_ou_atualizar_patrimonio,
    top_itens_por_valor,
)


def _format_currency(valor: float | int) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data(ttl=120, show_spinner=False)
def _carregar_patrimonios() -> pd.DataFrame:
    return listar_patrimonios()


def _aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    sb = st.sidebar
    sb.markdown("### 🔎 Filtros — Patrimônio")
    busca = sb.text_input("Buscar por item / marca / código", key="patrimonio_busca")
    busca_item = sb.text_input("Nome do item contém", key="patrimonio_item_nome")
    busca_marca = sb.text_input("Marca contém", key="patrimonio_marca_nome")
    busca_modelo = sb.text_input("Modelo contém", key="patrimonio_modelo_nome")
    categorias = sorted(c for c in df["CATEGORIA_NORMALIZADA"].dropna().unique() if c)
    categorias_sel = sb.multiselect("Categorias", categorias, key="patrimonio_categorias")
    estados = sorted(c for c in df["ESTADO_NORMALIZADO"].dropna().unique() if c)
    estados_sel = sb.multiselect("Estado de conservação", estados, key="patrimonio_estados")
    situacoes = sorted(c for c in df["SITUACAO_NORMALIZADA"].dropna().unique() if c)
    situacoes_sel = sb.multiselect("Situação de uso", situacoes, key="patrimonio_situacoes")
    marcas = sorted(c for c in df["MARCA"].dropna().astype(str).str.strip().unique() if c)
    marcas_sel = sb.multiselect("Marcas específicas", marcas, key="patrimonio_marcas")
    modelos = sorted(c for c in df["MODELO"].dropna().astype(str).str.strip().unique() if c)
    modelos_sel = sb.multiselect("Modelos específicos", modelos, key="patrimonio_modelos")

    preco_min = df["PRECO_ESTIMADO"].min()
    preco_max = df["PRECO_ESTIMADO"].max()
    if pd.isna(preco_min):
        preco_min = 0.0
    if pd.isna(preco_max):
        preco_max = 0.0
    if preco_min == preco_max:
        preco_min = max(0.0, float(preco_min) - 1)
        preco_max = float(preco_max) + 1
    else:
        preco_min = float(preco_min)
        preco_max = float(preco_max)
    passo_slider = 10.0 if (preco_max - preco_min) > 200 else 1.0
    valor_min_padrao = float(round(preco_min, 2))
    valor_max_padrao = float(round(preco_max, 2))
    if valor_min_padrao >= valor_max_padrao:
        valor_max_padrao = valor_min_padrao + passo_slider
    faixa_preco = sb.slider(
        "Faixa de preço unitário (R$)",
        min_value=valor_min_padrao,
        max_value=float(round(valor_max_padrao, 2)),
        value=(valor_min_padrao, float(round(valor_max_padrao, 2))),
        step=passo_slider,
    )

    anos = sorted(df["ANO_ATUALIZACAO"].dropna().astype(int).unique().tolist())
    ano_sel = sb.multiselect("Ano de atualização", anos, key="patrimonio_anos")

    if sb.button("Limpar filtros", type="secondary"):
        for chave, valor in {
            "patrimonio_busca": "",
            "patrimonio_item_nome": "",
            "patrimonio_marca_nome": "",
            "patrimonio_modelo_nome": "",
            "patrimonio_categorias": [],
            "patrimonio_estados": [],
            "patrimonio_situacoes": [],
            "patrimonio_anos": [],
            "patrimonio_marcas": [],
            "patrimonio_modelos": [],
        }.items():
            st.session_state[chave] = valor
        st.rerun()

    df_filtrado = df.copy()
    if busca:
        termo = busca.strip().lower()
        if termo:
            colunas_busca = ["ITEM", "MARCA", "MODELO", "CODIGO", "CATEGORIA"]
            mask = pd.Series(False, index=df_filtrado.index)
            for coluna in colunas_busca:
                if coluna in df_filtrado.columns:
                    mask = mask | df_filtrado[coluna].astype(str).str.lower().str.contains(termo, na=False)
            df_filtrado = df_filtrado[mask]
    if categorias_sel:
        df_filtrado = df_filtrado[df_filtrado["CATEGORIA_NORMALIZADA"].isin(categorias_sel)]
    if estados_sel:
        df_filtrado = df_filtrado[df_filtrado["ESTADO_NORMALIZADO"].isin(estados_sel)]
    if situacoes_sel:
        df_filtrado = df_filtrado[df_filtrado["SITUACAO_NORMALIZADA"].isin(situacoes_sel)]
    if marcas_sel:
        df_filtrado = df_filtrado[df_filtrado["MARCA"].isin(marcas_sel)]
    if modelos_sel:
        df_filtrado = df_filtrado[df_filtrado["MODELO"].isin(modelos_sel)]
    if busca_item:
        df_filtrado = df_filtrado[df_filtrado["ITEM"].astype(str).str.contains(busca_item, case=False, na=False)]
    if busca_marca:
        df_filtrado = df_filtrado[df_filtrado["MARCA"].astype(str).str.contains(busca_marca, case=False, na=False)]
    if busca_modelo:
        df_filtrado = df_filtrado[df_filtrado["MODELO"].astype(str).str.contains(busca_modelo, case=False, na=False)]
    if faixa_preco and "PRECO_ESTIMADO" in df_filtrado.columns:
        minimo, maximo = faixa_preco
        df_filtrado = df_filtrado[(df_filtrado["PRECO_ESTIMADO"] >= minimo) & (df_filtrado["PRECO_ESTIMADO"] <= maximo)]
    if ano_sel and "ANO_ATUALIZACAO" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["ANO_ATUALIZACAO"].isin(ano_sel)]
    return df_filtrado


def _download_button(df: pd.DataFrame):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        "⬇️ Baixar inventário (CSV)",
        data=csv_buffer.getvalue(),
        file_name="patrimonio_gp_mecatronica.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _dialog_novo_patrimonio(categorias: list[str], estados: list[str], situacoes: list[str]):
    categorias_opts = sorted(set(categorias + ["Ferramenta", "Componente Eletrônico", "Periférico"]))
    estados_opts = sorted(
        set(estados + ["Em bom estado", "Em ótimo estado", "Regular", "Desgastado, mas funcional", "Danificado"])
    )
    situacoes_opts = sorted(set(situacoes + ["Em uso", "Lacrado", "Em conserto", "Em manutenção"]))

    @st.dialog("➕ Cadastro de patrimônio")
    def modal():
        with st.form("form_novo_patrimonio"):
            col1, col2 = st.columns(2)
            with col1:
                item = st.text_input("Item *")
                categoria = st.selectbox("Categoria", categorias_opts)
                marca = st.text_input("Marca", value="Indefinido")
                quantidade = st.number_input("Quantidade", min_value=1, step=1, value=1)
                estado = st.selectbox("Estado de conservação", estados_opts, index=0)
            with col2:
                modelo = st.text_input("Modelo", value="Indefinido")
                preco = st.number_input("Preço estimado (R$)", min_value=0.0, step=10.0, value=0.0, format="%.2f")
                situacao = st.selectbox("Situação de uso", situacoes_opts, index=0)
                vida_util = st.text_input("Vida útil estimada", value="Indeterminado")
                data_atualizacao = st.date_input("Data da atualização", value=date.today())
                local_objeto = st.text_input("Local do objeto", placeholder="Ex.: Sala 1, armário B")
            observacoes = st.text_area("Observações (opcional)")
            salvar = st.form_submit_button("Salvar patrimônio", use_container_width=True)
            if salvar:
                if not item.strip():
                    st.error("Informe o nome do item.")
                    return
                try:
                    cadastrar_patrimonio(
                        {
                            "ITEM": item.strip(),
                            "CATEGORIA": categoria,
                            "MARCA": marca.strip() or "Indefinido",
                            "MODELO": modelo.strip() or "Indefinido",
                            "QUANTIDADE": quantidade,
                            "PRECO_ESTIMADO": preco,
                            "ESTADO": estado,
                            "SITUACAO_USO": situacao,
                            "VIDA_UTIL": vida_util.strip() or "Indeterminado",
                            "LOCAL_OBJETO": local_objeto.strip(),
                            "DATA_ATUALIZACAO": data_atualizacao.isoformat(),
                            "OBSERVACOES": observacoes.strip(),
                        }
                    )
                    st.session_state["toast_patrimonio"] = {"text": "Patrimônio cadastrado!", "icon": "✅"}
                    st.success("Patrimônio cadastrado com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível salvar o patrimônio: {exc}")

    modal()


def gestao_patrimonios():
    st.markdown("# 📦 Gestão de Patrimônios")
    msg = st.session_state.pop("toast_patrimonio", None)
    if msg:
        st.toast(msg.get("text", ""), icon=msg.get("icon", "✅"))
    st.caption("Inventário atualizado dos ativos do GP Mecatrônica")

    df = _carregar_patrimonios()
    categorias_base = sorted(df["CATEGORIA"].dropna().astype(str).str.strip().unique().tolist()) if not df.empty else []
    estados_base = sorted(df["ESTADO"].dropna().astype(str).str.strip().unique().tolist()) if not df.empty else []
    situacoes_base = sorted(df["SITUACAO_USO"].dropna().astype(str).str.strip().unique().tolist()) if not df.empty else []

    ac1, ac2, _ = st.columns([1, 1, 4])
    if ac1.button("➕ Novo patrimônio"):
        _dialog_novo_patrimonio(categorias_base, estados_base, situacoes_base)
    if ac2.button("🔄 Recarregar inventário"):
        try:
            st.cache_data.clear()
        finally:
            st.rerun()

    if df.empty:
        st.warning("Inventário de patrimônios não encontrado. Verifique o arquivo em `data/patrimonio_gp/`.")
        return

    df_filtrado = _aplicar_filtros(df)
    if df_filtrado.empty:
        st.info("Nenhum patrimônio encontrado com os filtros selecionados.")
        return

    indicadores = calcular_indicadores(df_filtrado)
    st.markdown("### Indicadores gerais")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registros filtrados", f"{indicadores['total_registros']}", border=True)
    c2.metric("Itens em estoque", f"{indicadores['quantidade_total']}", border=True)
    c3.metric("Categorias únicas", f"{indicadores['categorias_unicas']}", border=True)
    c4.metric("Valor estimado", _format_currency(indicadores["valor_total"]), border=True)

    c5, c6 = st.columns(2)
    c5.metric("Valor em uso", _format_currency(indicadores["valor_em_uso"]), border=True)
    c6.metric("Valor com avarias", _format_currency(indicadores["valor_danificado"]), border=True)

    st.markdown("### Inventário detalhado")
    busca_direta = st.text_input(
        "🔍 Busca rápida (item, marca, modelo ou código)",
        key="patrimonio_busca_direta",
        placeholder="Digite para filtrar instantaneamente a tabela...",
    )
    df_resultado = df_filtrado.copy()
    if busca_direta:
        termo = busca_direta.strip().lower()
        if termo:
            campos = ["ITEM", "MARCA", "MODELO", "CODIGO", "CATEGORIA"]
            mask = pd.Series(False, index=df_resultado.index)
            for campo in campos:
                if campo in df_resultado.columns:
                    mask = mask | df_resultado[campo].astype(str).str.lower().str.contains(termo, na=False)
            df_resultado = df_resultado[mask]

    if df_resultado.empty:
        st.info("Nenhum item encontrado com a busca rápida aplicada.")
        return

    colunas_visiveis = [
        "CODIGO",
        "ITEM",
        "CATEGORIA",
        "MARCA",
        "MODELO",
        "QUANTIDADE",
        "PRECO_ESTIMADO",
        "VALOR_TOTAL",
        "ESTADO",
        "SITUACAO_USO",
        "VIDA_UTIL",
        "OBSERVACOES",
        "LOCAL_OBJETO",
        "DATA_ATUALIZACAO_BR",
    ]
    existentes = [c for c in colunas_visiveis if c in df_resultado.columns]
    df_tabela = df_resultado[existentes].copy()
    df_tabela = df_tabela.set_index("CODIGO")
    df_tabela["EXCLUIR"] = False
    # garante coluna de exclusão no final
    cols_ordem = [c for c in df_tabela.columns if c != "EXCLUIR"] + ["EXCLUIR"]
    df_tabela = df_tabela[cols_ordem]

    total_registros = len(df_tabela)
    page_size = st.session_state.get("patrimonio_page_size", 20)
    pagina = st.session_state.get("patrimonio_page_number", 1)
    total_paginas = max(1, math.ceil(total_registros / page_size)) if page_size else 1
    pagina = min(max(1, pagina), total_paginas)
    inicio = (int(pagina) - 1) * page_size
    fim = inicio + page_size
    df_paginado = df_tabela.iloc[inicio:fim]

    st.caption("Edite direto na tabela ou marque linhas para excluir em lote.")
    retorno = st.data_editor(
        df_paginado,
        use_container_width=True,
        num_rows="fixed",
        hide_index=False,
        column_config={
            "EXCLUIR": st.column_config.CheckboxColumn("Excluir", help="Marque para apagar na ação abaixo"),
            "ITEM": st.column_config.TextColumn("Item"),
            "CATEGORIA": st.column_config.TextColumn("Categoria"),
            "MARCA": st.column_config.TextColumn("Marca"),
            "MODELO": st.column_config.TextColumn("Modelo"),
            "QUANTIDADE": st.column_config.NumberColumn("Qtd", min_value=0, step=1),
            "PRECO_ESTIMADO": st.column_config.NumberColumn("Preço", format="R$ %.2f", min_value=0.0, step=1.0),
            "VALOR_TOTAL": st.column_config.NumberColumn("Valor Total", format="R$ %.2f", disabled=True),
            "ESTADO": st.column_config.TextColumn("Estado de conservação"),
            "SITUACAO_USO": st.column_config.TextColumn("Situação de uso"),
            "VIDA_UTIL": st.column_config.TextColumn("Vida útil"),
            "OBSERVACOES": st.column_config.TextColumn("Observações"),
            "LOCAL_OBJETO": st.column_config.TextColumn("Local do objeto"),
            "DATA_ATUALIZACAO_BR": st.column_config.TextColumn("Data atualização", disabled=True),
        },
        key=f"patrimonio_editor_p{pagina}",
    )

    selecionados = [idx for idx, row in retorno.iterrows() if row.get("EXCLUIR")]
    if st.button(
        f"🗑️ Excluir selecionados ({len(selecionados)})",
        disabled=len(selecionados) == 0,
        type="secondary",
    ):
        removidos = deletar_patrimonios(selecionados)
        st.toast(f"{removidos} patrimônio(s) removido(s)", icon="✅")
        st.cache_data.clear()
        st.rerun()

    retorno_clean = retorno.drop(columns=["EXCLUIR"])
    orig_clean = df_paginado.drop(columns=["EXCLUIR"])
    alterados = []
    for codigo, row in retorno_clean.iterrows():
        if codigo not in orig_clean.index:
            continue
        base = orig_clean.loc[codigo]
        if not row.equals(base):
            payload = row.to_dict()
            payload["CODIGO"] = codigo
            try:
                payload["QUANTIDADE"] = int(payload.get("QUANTIDADE") or 0)
            except Exception:
                payload["QUANTIDADE"] = 0
            try:
                payload["PRECO_ESTIMADO"] = float(payload.get("PRECO_ESTIMADO") or 0.0)
            except Exception:
                payload["PRECO_ESTIMADO"] = 0.0
            payload["VALOR_TOTAL"] = payload["QUANTIDADE"] * payload["PRECO_ESTIMADO"]
            alterados.append(payload)

    if alterados:
        if st.button(f"💾 Salvar alterações desta página ({len(alterados)})", type="primary"):
            for payload in alterados:
                try:
                    salvar_ou_atualizar_patrimonio(payload)
                except Exception as exc:
                    st.warning(f"Falha ao salvar código {payload.get('CODIGO')}: {exc}")
            st.toast("Alterações salvas", icon="✅")
            st.cache_data.clear()
            st.rerun()

    st.caption(f"Exibindo {len(df_paginado)} de {total_registros} registros (página {int(pagina)}/{total_paginas}).")
    page_col1, page_col2 = st.columns(2)
    with page_col1:
        novo_page_size = st.selectbox(
            "Itens por página",
            [20, 50, 100],
            index=[20, 50, 100].index(page_size) if page_size in [20, 50, 100] else 0,
            key="patrimonio_page_size_select",
        )
    with page_col2:
        nova_pagina = st.number_input(
            "Página",
            min_value=1,
            max_value=total_paginas,
            value=int(pagina),
            step=1,
            key="patrimonio_page_number_input",
        )
    if novo_page_size != page_size or nova_pagina != pagina:
        st.session_state["patrimonio_page_size"] = novo_page_size
        st.session_state["patrimonio_page_number"] = nova_pagina
        st.rerun()

    df_download = df_resultado[existentes].copy()
    if "DATA_ATUALIZACAO_BR" in df_download.columns:
        df_download["DATA ATUALIZACAO"] = df_download["DATA_ATUALIZACAO_BR"]
        df_download = df_download.drop(columns=["DATA_ATUALIZACAO_BR"])
    _download_button(df_download)

    estado_colors = {
        "Em bom estado": "#22c55e",
        "Em ótimo estado": "#16a34a",
        "Regular": "#eab308",
        "Desgastado, mas funcional": "#f97316",
        "Danificado": "#ef4444",
    }

    with st.expander("📊 Ver gráficos e insights", expanded=False):
        col_a, col_b = st.columns(2)
        df_situacao = agrupar_por_situacao(df_resultado)
        if not df_situacao.empty:
            fig_situacao = px.pie(
                df_situacao,
                names="Situação",
                values="Itens",
                title="Distribuição por situação de uso",
                hole=0.45,
            )
            col_a.plotly_chart(fig_situacao, use_container_width=True)

        df_estado = agrupar_por_estado(df_resultado)
        if not df_estado.empty:
            fig_estado = px.bar(
                df_estado,
                x="Estado",
                y="Itens",
                text_auto=True,
                title="Estado de conservação",
                color="Estado",
                color_discrete_map=estado_colors,
            )
            col_b.plotly_chart(fig_estado, use_container_width=True)

        df_categoria = agrupar_por_categoria(df_resultado)
        if not df_categoria.empty:
            fig_cat = px.treemap(
                df_categoria,
                path=["Categoria"],
                values="Valor_Total",
                hover_data={"Itens": True, "Valor_Total": ":.2f"},
                title="Participação no valor total",
            )
            st.plotly_chart(fig_cat, use_container_width=True)

        df_evolucao = evolucao_por_mes(df_resultado)
        if not df_evolucao.empty:
            fig_evo = px.line(
                df_evolucao,
                x="MES",
                y="Valor_Total",
                markers=True,
                title="Valor movimentado por mês",
            )
            st.plotly_chart(fig_evo, use_container_width=True)

        df_top = top_itens_por_valor(df_resultado)
        if not df_top.empty:
            st.markdown("#### Itens de maior valor")
            df_top_display = df_top.copy()
            for coluna in ["PRECO_ESTIMADO", "VALOR_TOTAL"]:
                if coluna in df_top_display.columns:
                    df_top_display[coluna] = df_top_display[coluna].apply(_format_currency)
            st.dataframe(df_top_display, use_container_width=True, hide_index=True)
