elif page == "Comissão":
    st.markdown('<div class="page-title">Comissão</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Painel de acompanhamento da aba Pedigree Comissão Ju.</div>',
        unsafe_allow_html=True,
    )

    df_com = load_commission_data().copy()

    if not df_com.empty:
        col_data_venda = "Data da Venda" if "Data da Venda" in df_com.columns else detect_col(df_com, [["data", "venda"]])
        col_mes_venda = "Mês da Venda" if "Mês da Venda" in df_com.columns else detect_col(df_com, [["mês", "venda"], ["mes", "venda"]])
        col_cliente = "Cliente" if "Cliente" in df_com.columns else detect_col(df_com, [["cliente"]])
        col_produtos = "Produtos" if "Produtos" in df_com.columns else detect_col(df_com, [["produto"]])
        col_mes_compra_cliente = "Mês da Compra do Cliente" if "Mês da Compra do Cliente" in df_com.columns else detect_col(df_com, [["compra", "cliente"]])
        col_valor = "Valor" if "Valor" in df_com.columns else detect_col(df_com, [["valor"]])
        col_vendedor = "Vendedor" if "Vendedor" in df_com.columns else detect_col(df_com, [["vendedor"]])
        col_silimario = "Silimario" if "Silimario" in df_com.columns else detect_col(df_com, [["silimario"]])

        df_com["_data_venda"] = df_com[col_data_venda].apply(parse_date_any) if col_data_venda else None
        df_com["_mes_key"] = df_com.apply(lambda row: build_month_key(row, col_mes_venda, col_data_venda), axis=1)
        df_com["_valor_num"] = df_com[col_valor].apply(parse_money) if col_valor else 0.0
        df_com["_silimario_num"] = df_com[col_silimario].apply(parse_money) if col_silimario else 0.0
        df_com["_produto_norm"] = df_com[col_produtos].apply(normalize_search_text) if col_produtos else ""

        comm_months = sorted(
            [m for m in df_com["_mes_key"].dropna().unique().tolist()],
            key=lambda x: (x[0], x[1]),
        )

        if not comm_months:
            comm_months = [(today.year, today.month)]

        default_comm_month = comm_months[-1]

        left_col, right_col = st.columns([1.05, 2.7])

        with left_col:
            st.markdown(
                """
                <div class="live-card">
                    <div class="live-title">Filtros da Comissão</div>
                    <div class="live-sub">Use os filtros abaixo para acompanhar os valores.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            data_referencia = st.selectbox(
                "Data de referência",
                options=comm_months,
                index=comm_months.index(default_comm_month),
                format_func=month_key_to_label,
                key="data_referencia_comissao",
            )

            venc_col1, venc_col2 = st.columns(2)

            with venc_col1:
                data_venc_de = st.date_input("Vencimento de", value=None, key="vencimento_de_comissao")

            with venc_col2:
                data_venc_ate = st.date_input("Vencimento até", value=None, key="vencimento_ate_comissao")

            pag_col1, pag_col2 = st.columns(2)

            with pag_col1:
                data_pag_de = st.date_input("Pagamento de", value=None, key="pagamento_de_comissao")

            with pag_col2:
                data_pag_ate = st.date_input("Pagamento até", value=None, key="pagamento_ate_comissao")

            mes_valor_cliente = st.selectbox(
                "Valor clientes no mês",
                options=comm_months,
                index=comm_months.index(default_comm_month),
                format_func=month_key_to_label,
                key="valor_clientes_mes_comissao",
            )

            df_mes_valor = df_com[df_com["_mes_key"] == mes_valor_cliente].copy()
            valor_clientes_mes = float(df_mes_valor["_valor_num"].sum()) if not df_mes_valor.empty else 0.0

            card_metric(
                "Valor clientes no mês",
                format_money(valor_clientes_mes),
                month_key_to_label(mes_valor_cliente),
                "💰",
                "#8E0E3F",
            )

            st.markdown(
                """
                <div class="live-card">
                    <div class="live-title">Total de vendas por produto</div>
                    <div class="live-sub">Contagem pelo produto selecionado na planilha.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            produto = df_com["_produto_norm"]

            qtd_pedigree_trans = int(
                (
                    produto.str.contains("pedigree", na=False)
                    & ~produto.str.contains("s/ troca", na=False)
                    & ~produto.str.contains("sem transferencia", na=False)
                    & ~produto.str.contains("s/ trans", na=False)
                ).sum()
            )

            qtd_airtag = int(produto.str.contains("airtag", na=False).sum())

            qtd_cert_rg = int(
                (
                    produto.str.contains("certidao", na=False)
                    & produto.str.contains("rg", na=False)
                ).sum()
            )

            qtd_somente_rg = int(
                (
                    produto.str.contains("rg", na=False)
                    & ~produto.str.contains("certidao", na=False)
                    & ~produto.str.contains("airtag", na=False)
                ).sum()
            )

            qtd_ped_sem_trans = int(
                (
                    produto.str.contains("pedigree", na=False)
                    & (
                        produto.str.contains("s/ troca", na=False)
                        | produto.str.contains("sem transferencia", na=False)
                        | produto.str.contains("s/ trans", na=False)
                    )
                ).sum()
            )

            qtd_somente_certidao = int(
                (
                    produto.str.contains("certidao", na=False)
                    & ~produto.str.contains("rg", na=False)
                    & ~produto.str.contains("airtag", na=False)
                ).sum()
            )

            st.markdown(
                f"""
                <div class="live-card">
                    <div class="live-sub"><b>Pedigree com Transferência:</b> {qtd_pedigree_trans}</div>
                    <div class="live-sub"><b>Airtag:</b> {qtd_airtag}</div>
                    <div class="live-sub"><b>Certidão e RG:</b> {qtd_cert_rg}</div>
                    <div class="live-sub"><b>Somente RG:</b> {qtd_somente_rg}</div>
                    <div class="live-sub"><b>Pedigree sem Transferência:</b> {qtd_ped_sem_trans}</div>
                    <div class="live-sub"><b>Somente Certidão:</b> {qtd_somente_certidao}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with right_col:
            selected_comm_month = data_referencia

            vendedores = ["Todos"]

            if col_vendedor and col_vendedor in df_com.columns:
                vendedores += sorted(
                    [
                        v
                        for v in df_com[col_vendedor].dropna().astype(str).str.strip().unique().tolist()
                        if v
                    ]
                )

            filtro1, filtro2 = st.columns([1.2, 2.4])

            with filtro1:
                selected_vendedor = st.selectbox("Vendedor", vendedores, key="vendedor_comissao")

            with filtro2:
                busca_comissao = st.text_input(
                    "Busca rápida",
                    placeholder="Buscar por cliente, produto, vendedor...",
                )

            df_com_filtrado = df_com[df_com["_mes_key"] == selected_comm_month].copy()

            if selected_vendedor != "Todos" and col_vendedor and col_vendedor in df_com_filtrado.columns:
                df_com_filtrado = df_com_filtrado[
                    df_com_filtrado[col_vendedor].astype(str).str.strip() == selected_vendedor
                ].copy()

            if busca_comissao.strip():
                q = normalize_search_text(busca_comissao)

                busca_cols = [
                    c
                    for c in [col_cliente, col_produtos, col_vendedor, col_mes_compra_cliente]
                    if c and c in df_com_filtrado.columns
                ]

                if busca_cols:
                    mask_busca = pd.Series(False, index=df_com_filtrado.index)

                    for c in busca_cols:
                        mask_busca = mask_busca | df_com_filtrado[c].apply(normalize_search_text).str.contains(q, na=False)

                    df_com_filtrado = df_com_filtrado[mask_busca].copy()

            total_vendas = len(df_com_filtrado)
            valor_total = float(df_com_filtrado["_valor_num"].sum()) if not df_com_filtrado.empty else 0.0
            silimario_total = float(df_com_filtrado["_silimario_num"].sum()) if not df_com_filtrado.empty else 0.0
            ticket_medio = valor_total / total_vendas if total_vendas else 0.0

            if not df_com_filtrado.empty and col_produtos and col_produtos in df_com_filtrado.columns:
                produtos_unicos = df_com_filtrado[col_produtos].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
            else:
                produtos_unicos = 0

            k1, k2, k3, k4, k5 = st.columns(5)

            with k1:
                card_metric("Total de vendas", str(total_vendas), month_key_to_label(selected_comm_month), "📋", "#071B49")

            with k2:
                card_metric("Valor total", format_money(valor_total), "somatório vendido", "💰", "#8E0E3F")

            with k3:
                card_metric("Silimario", format_money(silimario_total), "total calculado", "⚖️", "#D39A33")

            with k4:
                card_metric("Ticket médio", format_money(ticket_medio), "valor médio", "📊", "#071B49")

            with k5:
                card_metric("Produtos", str(produtos_unicos), "tipos vendidos", "🧾", "#8E0E3F")

            graf1, graf2 = st.columns([1.25, 1])

            with graf1:
                st.markdown(
                    """
                    <div class="live-card">
                        <div class="live-title">📊 Vendas por dia</div>
                        <div class="live-sub">Quantidade de registros por data da venda no mês selecionado.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if not df_com_filtrado.empty and col_data_venda:
                    df_dia = df_com_filtrado.copy()
                    df_dia["_dia_label"] = df_dia["_data_venda"].apply(
                        lambda x: x.strftime("%d/%m") if isinstance(x, dt.date) else "Sem data"
                    )

                    resumo_dia = df_dia.groupby("_dia_label").size().reset_index(name="Vendas")

                    fig_dia = px.bar(
                        resumo_dia,
                        x="_dia_label",
                        y="Vendas",
                        text="Vendas",
                        color="_dia_label",
                        color_discrete_sequence=[
                            "#071B49",
                            "#8E0E3F",
                            "#2E3192",
                            "#C00040",
                            "#45546B",
                            "#95A3B8",
                            "#1B1D6D",
                            "#9B0033",
                        ],
                    )

                    fig_dia.update_traces(textposition="outside", marker_line_width=0)

                    fig_dia.update_layout(
                        height=360,
                        showlegend=False,
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        margin=dict(l=20, r=20, t=30, b=60),
                        xaxis=dict(title="", tickangle=-35, showgrid=False),
                        yaxis=dict(title="", rangemode="tozero", gridcolor="#E7EAF3"),
                    )

                    st.plotly_chart(fig_dia, use_container_width=True)
                else:
                    st.info("Sem dados para montar o gráfico por dia.")

            with graf2:
                st.markdown(
                    """
                    <div class="live-card">
                        <div class="live-title">🧾 Produtos vendidos</div>
                        <div class="live-sub">Distribuição por tipo de produto.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if not df_com_filtrado.empty and col_produtos and col_produtos in df_com_filtrado.columns:
                    resumo_prod = (
                        df_com_filtrado[col_produtos]
                        .astype(str)
                        .str.strip()
                        .replace("", "Não informado")
                        .value_counts()
                        .reset_index()
                    )

                    resumo_prod.columns = ["Produto", "Quantidade"]

                    fig_prod = px.pie(
                        resumo_prod,
                        names="Produto",
                        values="Quantidade",
                        hole=0.55,
                        color_discrete_sequence=[
                            "#071B49",
                            "#8E0E3F",
                            "#D39A33",
                            "#2E3192",
                            "#C00040",
                            "#64748B",
                            "#95A3B8",
                        ],
                    )

                    fig_prod.update_traces(
                        textinfo="percent+label",
                        hovertemplate="<b>%{label}</b><br>Quantidade: %{value}<extra></extra>",
                    )

                    fig_prod.update_layout(
                        height=360,
                        showlegend=True,
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        margin=dict(l=10, r=10, t=30, b=20),
                    )

                    st.plotly_chart(fig_prod, use_container_width=True)
                else:
                    st.info("Sem dados para montar o gráfico por produto.")

            st.markdown(
                """
                <div class="live-card">
                    <div class="live-title">📄 Lista de vendas da comissão</div>
                    <div class="live-sub">Base filtrada da aba Pedigree Comissão Ju.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            cols_show = [
                c
                for c in [
                    col_data_venda,
                    col_mes_venda,
                    col_cliente,
                    col_produtos,
                    col_mes_compra_cliente,
                    col_valor,
                    col_vendedor,
                    col_silimario,
                ]
                if c and c in df_com_filtrado.columns
            ]

            if not df_com_filtrado.empty and cols_show:
                render_realtime_table(df_com_filtrado, cols_show, height=430)
            else:
                st.info("Nenhuma venda encontrada com os filtros selecionados.")

    else:
        st.warning("A aba Pedigree Comissão Ju está vazia ou não foi encontrada.")
