if st.session_state.acao_ped == "Novo":
    st.markdown("### Formulário Pedigree")

    with st.form("formulario_pedigree_novo"):
        st.markdown("#### Informações Tutor")

        col1, col2 = st.columns(2)

        with col1:
            tutor_nome = st.text_input("Nome do tutor")
            tutor_cpf = st.text_input("CPF")
            tutor_email = st.text_input("E-mail")
            tutor_endereco = st.text_input("Endereço completo")

        with col2:
            status_cliente = st.checkbox("Status cliente")
            fazendo = st.checkbox("Fazendo")
            rg_certidao = st.checkbox("RG e certidão fazer")
            pagamento = st.checkbox("Pagamento")
            aprovacao = st.checkbox("Aprovação")
            imprimir = st.checkbox("Imprimir")
            enviar = st.checkbox("Enviar")
            enviado = st.checkbox("Enviado")

        st.markdown("#### Informações Cão")

        col3, col4 = st.columns(2)

        with col3:
            cao_nome = st.text_input("Nome do cão")
            nascimento = st.date_input("Data de nascimento")
            pelagem = st.text_input("Pelagem")
            raca = st.text_input("Raça do pet")

        with col4:
            foto_pet = st.file_uploader("Foto do pet", type=["png", "jpg", "jpeg"])
            if foto_pet:
                st.image(foto_pet, caption="Foto do pet", width=220)

        transferencia = st.radio(
            "Houve pedido de transferência?",
            ["Sim", "Não"],
            horizontal=True
        )

        observacoes = st.text_area("Observações")

        salvar = st.form_submit_button("Executar tudo")

        if salvar:
            st.success("Formulário preenchido com sucesso.")

            dados_formulario = {
                "Nome tutor": tutor_nome,
                "CPF": tutor_cpf,
                "E-mail": tutor_email,
                "Endereço": tutor_endereco,
                "Status cliente": status_cliente,
                "Fazendo": fazendo,
                "RG e certidão fazer": rg_certidao,
                "Pagamento": pagamento,
                "Aprovação": aprovacao,
                "Imprimir": imprimir,
                "Enviar": enviar,
                "Enviado": enviado,
                "Nome cão": cao_nome,
                "Data nascimento": nascimento,
                "Pelagem": pelagem,
                "Raça": raca,
                "Transferência": transferencia,
                "Observações": observacoes,
            }

            st.session_state["novo_pedigree_form"] = dados_formulario
