import streamlit as st
from supabase import create_client
import requests

# =========================
# FUNÇÃO IA (OpenRouter)
# =========================
def verificar_resposta(pergunta, resposta_correta, resposta_usuario):
    api_key = st.secrets["OPENROUTER_API_KEY"]
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = f"""
    Pergunta: {pergunta}
    Resposta correta: {resposta_correta}
    Resposta do usuário: {resposta_usuario}

    A resposta do usuário está correta? Responda apenas com SIM ou NÃO.
    """

    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        resultado = response.json()
        if "choices" not in resultado:
            return "NÃO"
        return resultado["choices"][0]["message"]["content"]
    except:
        return "NÃO"


# =========================
# CONEXÃO BANCO (Supabase)
# =========================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("Riddles Game 🧩")

# =========================
# USUÁRIO DINÂMICO
# =========================
nome_usuario = st.text_input("Digite seu nome:").strip()

if not nome_usuario:
    st.warning("Digite seu nome para jogar!")
    st.stop()

# Busca o usuário no banco para pegar o ID e a pontuação real
response_user = supabase.table("usuario").select("*").eq("nome", nome_usuario).limit(1).execute()

if not response_user.data:
    # Se não existe, cria um novo
    novo_user = supabase.table("usuario").insert({"nome": nome_usuario, "pontuacao": 0}).execute()
    user_id = novo_user.data[0]["id"]
    pontuacao_atual = 0
else:
    # Se existe, guarda o ID e a pontuação que já estava lá
    user_id = response_user.data[0]["id"]
    pontuacao_atual = response_user.data[0]["pontuacao"]

st.write(f"Olá, **{nome_usuario}**! Sua pontuação atual: **{pontuacao_atual}**")
# criar rodada (uma vez por sessão)
if "rodada_id" not in st.session_state:
    usuario_data = supabase.table("usuario") \
        .select("*") \
        .eq("nome", nome_usuario) \
        .execute()

    user_id = usuario_data.data[0]["id"]

    rodada = supabase.table("rodada").insert({
        "user_id": user_id
    }).execute()

    st.session_state["rodada_id"] = rodada.data[0]["id"]

# =========================
# ENIGMA
# =========================
response_enigma = supabase.table("enigma").select("*").limit(1).execute()
enigma = response_enigma.data[0]

st.subheader("Pergunta:")
st.write(enigma["pergunta"])

resposta_usuario = st.text_input("Digite sua resposta:")

# =========================
# LÓGICA DE RESPOSTA
# =========================
if st.button("Responder"):
    resultado_ia = verificar_resposta(
        enigma["pergunta"],
        enigma["resposta"],
        resposta_usuario
    )
    rodada_id = st.session_state["rodada_id"]

    correta = "SIM" in resultado_ia.upper()

    # salvar tentativa
    supabase.table("tentativa").insert({
        "rodada_id": rodada_id,
        "enigma_id": enigma["id"],
        "resposta_usuario": resposta_usuario,
        "correta": correta
    }).execute()

    if "SIM" in resultado_ia.upper():
        st.success("Acertou! 🎉")
        
        # SOMA 1000 pontos à pontuação que buscamos no banco
        nova_pontuacao = pontuacao_atual + 1000

        # Atualiza o banco usando o ID (é muito mais seguro que o nome)
        supabase.table("usuario").update({"pontuacao": nova_pontuacao}).eq("id", user_id).execute()
        
        st.info(f"Nova pontuação salva: {nova_pontuacao} pts")
        st.rerun() # Atualiza a tela para mostrar a pontuação nova no topo
    else:
        st.error("Errou! 😢 A IA disse que sua resposta não bate.")

# =========================
# RANKING (TOP 5)
# =========================
st.divider()
st.subheader("🏆 Ranking Geral")

ranking = supabase.table("usuario") \
    .select("*") \
    .order("pontuacao", desc=True) \
    .limit(5) \
    .execute()

for i, user in enumerate(ranking.data, start=1):
    st.write(f"{i}º {user['nome']} - {user['pontuacao']} pts")