import streamlit as st
from supabase import create_client
import requests


# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================

st.set_page_config(page_title="Riddles Game 🧩", page_icon="🧩")


# =============================================================================
# CONSTANTES DO JOGO (seção 4 da documentação)
# =============================================================================

PONTUACAO_INICIAL = {
    "facil":   5_000,
    "medio":  10_000,
    "dificil": 15_000,
}

PENALIDADE_ERRO   = 1_000
PENALIDADE_DICA   = {1: 1_000, 2: 2_000, 3: 3_000}
LIMITE_DERROTA    = 0


# =============================================================================
# CONEXÃO COM BANCO DE DADOS (Supabase)
# =============================================================================

@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()


# =============================================================================
# CAMADA DE IA — OpenRouter (seção 5 da documentação)
# =============================================================================

def verificar_resposta(pergunta: str, resposta_correta: str, resposta_usuario: str) -> dict:
    """
    Envia a pergunta e as respostas para a IA e retorna:
      - correta (bool)
      - feedback (str)
    """
    api_key = st.secrets["OPENROUTER_API_KEY"]
    url     = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    prompt = f"""
    Pergunta: {pergunta}
    Resposta correta: {resposta_correta}
    Resposta do usuário: {resposta_usuario}

    Avalie se a resposta do usuário está correta considerando sinônimos e contexto.
    Responda APENAS neste formato:
    RESULTADO: SIM ou NÃO
    FEEDBACK: <uma frase curta e divertida explicando o resultado>
    """

    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        texto = response.json()["choices"][0]["message"]["content"]

        linhas   = texto.strip().splitlines()
        correta  = any("SIM" in l.upper() for l in linhas if "RESULTADO" in l.upper())
        feedback = next(
            (l.split(":", 1)[1].strip() for l in linhas if "FEEDBACK" in l.upper()),
            "Sem feedback disponível.",
        )
        return {"correta": correta, "feedback": feedback}

    except Exception:
        return {"correta": False, "feedback": "Não foi possível validar sua resposta. Tente novamente."}


# =============================================================================
# FUNÇÕES DE BANCO DE DADOS
# =============================================================================

def buscar_ou_criar_usuario(nome: str) -> dict:
    """Retorna o registro do usuário, criando-o se não existir."""
    res = supabase.table("usuario").select("*").eq("nome", nome).limit(1).execute()
    if res.data:
        return res.data[0]
    novo = supabase.table("usuario").insert({"nome": nome, "pontuacao": 0}).execute()
    return novo.data[0]


def criar_rodada(user_id: int) -> int:
    """Cria uma nova rodada para o usuário e retorna o ID."""
    rodada = supabase.table("rodada").insert({"user_id": user_id}).execute()
    return rodada.data[0]["id"]


def buscar_enigmas() -> list:
    """Retorna todos os enigmas cadastrados."""
    res = supabase.table("enigma").select("*").execute()
    return res.data


def salvar_tentativa(rodada_id: int, enigma_id: int, resposta_usuario: str,
                     correta: bool) -> None:
    """Registra uma tentativa na tabela correspondente."""
    supabase.table("tentativa").insert({
        "rodada_id":        rodada_id,
        "enigma_id":        enigma_id,
        "resposta_usuario": resposta_usuario,
        "correta":          correta,
    }).execute()


def atualizar_pontuacao_usuario(user_id: int, nova_pontuacao: int) -> None:
    """Persiste a pontuação acumulada do usuário no banco."""
    supabase.table("usuario").update({"pontuacao": nova_pontuacao}).eq("id", user_id).execute()


def buscar_ranking(limite: int = 5) -> list:
    """Retorna os melhores jogadores ordenados por pontuação."""
    res = (
        supabase.table("usuario")
        .select("*")
        .order("pontuacao", desc=True)
        .limit(limite)
        .execute()
    )
    return res.data


# =============================================================================
# MOTOR DE REGRAS DO JOGO (seção 4 da documentação)
# =============================================================================

def pontuacao_inicial_enigma(nivel: str) -> int:
    """Retorna a pontuação inicial do enigma conforme o nível."""
    return PONTUACAO_INICIAL.get(nivel, 5_000)


def aplicar_penalidade_dica(pontuacao: int, numero_dica: int) -> int:
    """Desconta a penalidade da dica e retorna a nova pontuação."""
    desconto = PENALIDADE_DICA.get(numero_dica, 0)
    return max(pontuacao - desconto, 0)


def aplicar_penalidade_erro(pontuacao: int) -> int:
    """Desconta a penalidade por resposta errada."""
    return max(pontuacao - PENALIDADE_ERRO, 0)


def jogador_derrotado(pontuacao: int) -> bool:
    """Retorna True se a pontuação atingiu o limite de derrota."""
    return pontuacao <= LIMITE_DERROTA


# =============================================================================
# INICIALIZAÇÃO DO ESTADO DE SESSÃO
# =============================================================================

def inicializar_sessao(enigmas: list) -> None:
    """Garante que todas as chaves de sessão necessárias existam."""
    defaults = {
        "indice_enigma":    0,
        "pontuacao_rodada": pontuacao_inicial_enigma(enigmas[0]["nivel"]) if enigmas else 0,
        "dicas_usadas":     0,
        "game_over":        False,
        "vitoria":          False,
        "enigmas_resolvidos": [],
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


# =============================================================================
# INTERFACE — TÍTULO E ENTRADA DO USUÁRIO
# =============================================================================

st.title("Riddles Game 🧩")

nome_usuario = st.text_input("Digite seu nome:").strip()

if not nome_usuario:
    st.warning("Digite seu nome para começar a jogar!")
    st.stop()

# Carrega ou cria o usuário
usuario = buscar_ou_criar_usuario(nome_usuario)
user_id = usuario["id"]
pontuacao_acumulada = usuario["pontuacao"]

st.write(f"Olá, **{nome_usuario}**! Pontuação acumulada no ranking: **{pontuacao_acumulada} pts**")

# Cria a rodada uma única vez por sessão
if "rodada_id" not in st.session_state:
    st.session_state["rodada_id"] = criar_rodada(user_id)

rodada_id = st.session_state["rodada_id"]

# Carrega enigmas e inicializa sessão
enigmas = buscar_enigmas()
if not enigmas:
    st.error("Nenhum enigma cadastrado no banco de dados.")
    st.stop()

inicializar_sessao(enigmas)


# =============================================================================
# FLUXO DO JOGO (seção 6 da documentação)
# =============================================================================

indice = st.session_state["indice_enigma"]

# --- Condição de vitória ---
if st.session_state["vitoria"] or indice >= len(enigmas):
    st.balloons()
    st.success("🏆 Parabéns! Você resolveu todos os enigmas!")
    st.info(f"Pontuação adicionada ao ranking: **{st.session_state['pontuacao_rodada']} pts**")
    st.stop()

# --- Condição de derrota ---
if st.session_state["game_over"]:
    st.error("💀 Game Over! Sua pontuação chegou a zero.")
    st.stop()

# --- Enigma atual ---
enigma = enigmas[indice]
pontuacao_enigma = st.session_state["pontuacao_rodada"]

st.divider()
st.subheader(f"Enigma {indice + 1} de {len(enigmas)}  |  Nível: **{enigma['nivel'].capitalize()}**")
st.write(f"**{enigma['pergunta']}**")
st.metric("Pontos disponíveis neste enigma", f"{pontuacao_enigma} pts")

# --- Sistema de dicas ---
dicas = [enigma.get(f"dica{i}") for i in range(1, 4) if enigma.get(f"dica{i}")]

if dicas:
    st.write("---")
    dicas_usadas = st.session_state["dicas_usadas"]
    proxima_dica = dicas_usadas + 1

    if dicas_usadas < len(dicas):
        penalidade = PENALIDADE_DICA.get(proxima_dica, 0)
        if st.button(f"💡 Ver Dica {proxima_dica} (-{penalidade} pts)"):
            st.session_state["pontuacao_rodada"] = aplicar_penalidade_dica(
                st.session_state["pontuacao_rodada"], proxima_dica
            )
            st.session_state["dicas_usadas"] += 1

            if jogador_derrotado(st.session_state["pontuacao_rodada"]):
                st.session_state["game_over"] = True
                st.rerun()

    # Exibe dicas já reveladas
    for i in range(st.session_state["dicas_usadas"]):
        st.info(f"💡 Dica {i + 1}: {dicas[i]}")

# --- Resposta do usuário ---
st.write("---")
resposta_usuario = st.text_input("Sua resposta:", key=f"resposta_{indice}")

if st.button("✅ Responder"):
    if not resposta_usuario.strip():
        st.warning("Digite uma resposta antes de confirmar.")
    else:
        with st.spinner("A IA está avaliando sua resposta..."):
            resultado = verificar_resposta(enigma["pergunta"], enigma["resposta"], resposta_usuario)

        correta  = resultado["correta"]
        feedback = resultado["feedback"]

        if correta:
            pontos_obtidos = st.session_state["pontuacao_rodada"]
            st.success(f"🎉 Correto! {feedback}")
            st.info(f"+{pontos_obtidos} pts adicionados ao seu ranking!")

            salvar_tentativa(rodada_id, enigma["id"], resposta_usuario, True)

            
            usuario_atualizado = supabase.table("usuario") \
            .select("pontuacao") \
            .eq("id", user_id) \
            .execute()

            pontuacao_atual = usuario_atualizado.data[0]["pontuacao"]

            nova_pontuacao_acumulada = pontuacao_atual + pontos_obtidos

            atualizar_pontuacao_usuario(user_id, nova_pontuacao_acumulada)

            # Salva tentativa com pontuação obtida
            salvar_tentativa(rodada_id, enigma["id"], resposta_usuario, True)

            # Atualiza pontuação acumulada no banco
            nova_pontuacao_acumulada = pontuacao_acumulada + pontos_obtidos
            atualizar_pontuacao_usuario(user_id, nova_pontuacao_acumulada)

            # Avança para o próximo enigma
            proximo_indice = indice + 1
            st.session_state["indice_enigma"]    = proximo_indice
            st.session_state["dicas_usadas"]     = 0

            if proximo_indice >= len(enigmas):
                st.session_state["vitoria"] = True
            else:
                proximo_enigma = enigmas[proximo_indice]
                st.session_state["pontuacao_rodada"] = pontuacao_inicial_enigma(proximo_enigma["nivel"])

            st.rerun()

        else:
            # Penalidade por resposta errada
            st.session_state["pontuacao_rodada"] = aplicar_penalidade_erro(
                st.session_state["pontuacao_rodada"]
            )
            st.error(f"❌ Errado! {feedback}")
            st.warning(f"-{PENALIDADE_ERRO} pts de penalidade. Pontuação atual: {st.session_state['pontuacao_rodada']} pts")

            # Salva tentativa sem pontuação
            salvar_tentativa(rodada_id, enigma["id"], resposta_usuario, False)

            if jogador_derrotado(st.session_state["pontuacao_rodada"]):
                st.session_state["game_over"] = True
                st.rerun()


# =============================================================================
# RANKING GERAL (seção 7 da documentação)
# =============================================================================

st.divider()
st.subheader("🏆 Ranking Geral — Top 5")

ranking = buscar_ranking(limite=5)
medalhas = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

for i, jogador in enumerate(ranking):
    st.write(f"{medalhas[i]}  **{jogador['nome']}** — {jogador['pontuacao']} pts")