elif page == "Pedigree":
    st.markdown('<div class="page-title">Pedigree</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">Consulta completa de clientes para análise de Pedigree.</div>',
        unsafe_allow_html=True,
    )

    busca_ped = st.text_input(
        "Buscar cliente no Pedigree",
        placeholder="Cole o telefone copiado da Visão Geral ou busque por nome, código, status, raça...",
    )

    df_ped = df.copy()

    def normalize_full_row(row):
        values = []
        for v in row:
            if pd.isna(v):
                continue
            values.append(normalize_search_text(v))
        return " ".join(values)

    df_ped["_search_all"] = df_ped.apply(normalize_full_row, axis=1)
    df_ped["_tel_digits_ped"] = df_ped[COL_TEL].apply(only_digits) if COL_TEL and COL_TEL in df_ped.columns else ""

    if busca_ped.strip():
        q = normalize_search_text(busca_ped)
        q_digits = re.sub(r"\D", "", busca_ped)

        mask = df_ped["_search_all"].str.contains(q, na=False)

        if q_digits:
            clean_variants = [q_digits]
            if q_digits.startswith("55") and len(q_digits) > 11:
                clean_variants.append(q_digits[2:])

            phone_mask = pd.Series(False, index=df_ped.index)
            for variant in clean_variants:
                phone_mask = phone_mask | df_ped["_tel_digits_ped"].str.contains(variant, na=False)

            mask = mask | phone_mask

        df_ped = df_ped[mask].copy()

    st.markdown(
        f"""
        <div class="live-card">
            <div class="live-title">Resultados encontrados</div>
            <div class="live-sub">
                {len(df_ped)} registro(s) encontrado(s) na base de Pedigree.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if busca_ped.strip() and not df_ped.empty:
        cliente = df_ped.iloc[0]

        nome = normalize_text(cliente.get(COL_NOME, ""))
        telefone = format_phone_br(cliente.get(COL_TEL, ""))
        status_venda = normalize_text(cliente.get("Status Venda Pedigree", ""))
        status_pedigree = normalize_text(cliente.get("Status Pedigree", ""))
        codigo = normalize_text(cliente.get("Código Royal", ""))
        raca = normalize_text(cliente.get(COL_RACA, ""))
        whatsapp = normalize_text(cliente.get(COL_WHATSAPP, "")) if COL_WHATSAPP else ""

        st.markdown(
            f"""
            <div class="live-card">
                <div class="live-title">{nome}</div>
                <div class="live-sub">Ficha do cliente encontrada na base</div>

                <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:16px;">

                    <div class="empty-page-card">
                        <div class="empty-page-title">Telefone</div>
                        <div class="empty-page-sub">{telefone}</div>
                    </div>

                    <div class="empty-page-card">
                        <div class="empty-page-title">WhatsApp</div>
                        <div class="empty-page-sub">{whatsapp}</div>
                    </div>

                    <div class="empty-page-card">
                        <div class="empty-page-title">Raça</div>
                        <div class="empty-page-sub">{raca}</div>
                    </div>

                    <div class="empty-page-card">
                        <div class="empty-page-title">Status Venda Pedigree</div>
                        <div class="empty-page-sub">{status_venda}</div>
                    </div>

                    <div class="empty-page-card">
                        <div class="empty-page-title">Status Pedigree</div>
                        <div class="empty-page-sub">{status_pedigree}</div>
                    </div>

                    <div class="empty-page-card">
                        <div class="empty-page-title">Código Royal</div>
                        <div class="empty-page-sub">{codigo}</div>
                    </div>

                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif busca_ped.strip() and df_ped.empty:
        st.warning("Nenhum cliente encontrado com essa busca.")
