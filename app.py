import streamlit as st
from supabase import create_client

# pegar dados do secrets
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

# conectar ao supabase
supabase = create_client(url, key)

st.title("Riddles Game 🧩")

# buscar um enigma
response = supabase.table("enigma").select("*").limit(1).execute()

# pegar o primeiro resultado
enigma = response.data[0]

# mostrar na tela
st.subheader("Pergunta:")
st.write(enigma["pergunta"])

# campo de resposta
resposta_usuario = st.text_input("Digite sua resposta:")

# botão para enviar
if st.button("Responder"):
    if resposta_usuario.lower() == enigma["resposta"]:
        st.success("Acertou! 🎉")

        # buscar pontuação atual
        usuario = supabase.table("usuario").select("*").eq("nome", "Jessy").execute()

        pontuacao_atual = usuario.data[0]["pontuacao"]

        # somar pontos
        nova_pontuacao = pontuacao_atual + 1000

        # atualizar no banco
        supabase.table("usuario").update({
        "pontuacao": nova_pontuacao
        }).eq("nome", "Jessy").execute()
    else:
        st.error("Errou! 😢")
st.subheader("🏆 Ranking")

# buscar usuários ordenados por pontuação
ranking = supabase.table("usuario") \
    .select("*") \
    .order("pontuacao", desc=True) \
    .limit(5) \
    .execute()

# mostrar ranking
for i, user in enumerate(ranking.data, start=1):
    st.write(f"{i}º {user['nome']} - {user['pontuacao']} pts")