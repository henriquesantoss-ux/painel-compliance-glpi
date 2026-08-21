import streamlit as st
import pandas as pd
import plotly.express as px
from urllib.parse import quote

# Configuração da Página
st.set_page_config(page_title="Painel de Compliance - GLPI", layout="wide")

# -------------------------------------------------------------
# ESTILIZAÇÃO CSS DARK E REMOÇÃO DE INSTRUÇÕES DE INPUT
# -------------------------------------------------------------
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1726;
        color: #ffffff;
    }
    div[data-testid="stMetricValue"] {
        font-size: 30px;
        font-weight: bold;
        color: #ffffff;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 13px;
        color: #888ea8;
        font-weight: 600;
    }
    /* Oculta o texto "Press Enter to apply" dos campos de texto */
    div[data-testid="stInputInstructions"] {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# SISTEMA DE AUTENTICAÇÃO (BUSCA EXCLUSIVAMENTE NO SECRETS)
# -------------------------------------------------------------
# Não existe NENHUMA senha salva no código. O Streamlit busca direto na nuvem.
SENHA_CORRETA = st.secrets["SENHA_CORRETA"]

def verificar_senha():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.markdown("<h2 style='text-align: center;'>🔒 Acesso Restrito - GLPI</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form(key="form_login", clear_on_submit=False):
                senha_digitada = st.text_input("Digite a senha de acesso:", type="password")
                botao_entrar = st.form_submit_button("Entrar", use_container_width=True)
                
                if botao_entrar:
                    if senha_digitada == SENHA_CORRETA:
                        st.session_state["autenticado"] = True
                        st.rerun()
                    else:
                        st.error("🔑 Senha incorreta! Tente novamente.")
        return False
    return True

if not verificar_senha():
    st.stop()

if st.sidebar.button("🚪 Sair / Logoff"):
    st.session_state["autenticado"] = False
    st.rerun()

# -------------------------------------------------------------
# CONEXÃO COM O GOOGLE SHEETS (BUSCA EXCLUSIVAMENTE NO SECRETS)
# -------------------------------------------------------------
SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
SHEET_NAME = "Base GLPI"

url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote(SHEET_NAME)}"

@st.cache_data(ttl=60, show_spinner=False)
def carregar_dados():
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip()
    
    if 'Dias Numéricos' in df.columns:
        s_dias = df['Dias Numéricos'].astype(str).str.replace(',', '.').str.strip()
        df['Dias Numéricos'] = pd.to_numeric(s_dias, errors='coerce')
    return df

try:
    df = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar os dados: {e}")
    st.stop()

# -------------------------------------------------------------
# ORDENAÇÃO CRONOLÓGICA DOS MESES
# -------------------------------------------------------------
ORDEM_MESES = [
    'jan', 'fev', 'mar', 'abr', 'mai', 'jun', 
    'jul', 'ago', 'set', 'out', 'nov', 'dez'
]

def obter_chave_ordenacao(mes_str):
    if not isinstance(mes_str, str):
        return (9999, 99)
    partes = mes_str.lower().replace('.', '').split('/')
    nome_mes = partes[0].strip()
    
    idx_mes = ORDEM_MESES.index(nome_mes) if nome_mes in ORDEM_MESES else 99
    ano = int("20" + partes[1].strip()) if len(partes) > 1 and partes[1].strip().isdigit() else 0
    
    return (ano, idx_mes)

meses_brutos = df['Mês'].dropna().unique().tolist() if 'Mês' in df.columns else []
meses_unicos = sorted(meses_brutos, key=obter_chave_ordenacao)

# -------------------------------------------------------------
# FUNÇÃO MODAL (POP-UP DE DETALHES)
# -------------------------------------------------------------
@st.dialog("📋 Lista Detalhada de Chamados", width="large")
def abrir_modal_detalhes():
    filtro_nome = st.session_state.get("modal_filtro", "")
    df_dados = st.session_state.get("modal_dados", pd.DataFrame())
    
    st.subheader(f"Filtro Selecionado: {filtro_nome}")
    
    colunas_desejadas = [
        'Mês', 'Status V2', 'Título', 'Data de abertura', 
        'Marca', 'Loja', 'Tipo Campanhas', 'Data da Solução'
    ]
    cols_existentes = [c for c in colunas_desejadas if c in df_dados.columns]
    
    st.write(f"Exibindo **{len(df_dados)}** chamados registrados:")
    st.dataframe(df_dados[cols_existentes], use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# CABEÇALHO E SELETOR DE MÊS
# -------------------------------------------------------------
st.title("Painel de Compliance - GLPI")

opcoes_periodo = ["Total"] + meses_unicos

selecao_meses = st.pills(
    label="Selecione o(s) Mês(es):",
    options=opcoes_periodo,
    default=["Total"],
    selection_mode="multi"
)

if selecao_meses:
    selecao_meses = sorted([m for m in selecao_meses if m != "Total"], key=obter_chave_ordenacao) + (["Total"] if "Total" in selecao_meses else [])

if not selecao_meses or "Total" in selecao_meses:
    df_filtrado = df.copy()
    label_periodo = "Total"
else:
    df_filtrado = df[df['Mês'].isin(selecao_meses)]
    label_periodo = " + ".join([m for m in selecao_meses if m != "Total"])

st.caption(f"Exibindo: **{label_periodo}**")
st.markdown("---")

# -------------------------------------------------------------
# CÁLCULO DOS KPIS
# -------------------------------------------------------------
total_chamados = len(df_filtrado)

dias_validos = df_filtrado['Dias Numéricos'].dropna() if 'Dias Numéricos' in df_filtrado.columns else pd.Series()

if not dias_validos.empty:
    media_dias_decimal = dias_validos.mean()
    dias_inteiros = int(media_dias_decimal)
    horas_restantes = int((media_dias_decimal - dias_inteiros) * 24)
    tempo_medio_formatado = f"{dias_inteiros} dias e {horas_restantes} horas"
else:
    tempo_medio_formatado = "N/A"

col_kpi1, col_kpi2 = st.columns(2)
with col_kpi1:
    st.metric(label="TOTAL DE CHAMADOS", value=total_chamados)
with col_kpi2:
    st.metric(label="TEMPO MÉDIO DE ATENDIMENTO", value=tempo_medio_formatado)

st.write("")

# -------------------------------------------------------------
# GRÁFICOS CLEAN COM PERCENTUAIS (HOVER 100% DESATIVADO)
# -------------------------------------------------------------
col_graf1, col_graf2 = st.columns(2)

# Gráfico 1: Status dos Chamados
with col_graf1:
    st.subheader("Status dos Chamados")
    if 'Status V2' in df_filtrado.columns and not df_filtrado.empty:
        df_status = df_filtrado['Status V2'].value_counts().reset_index()
        df_status.columns = ['Status', 'Qtd']
        
        df_status['Texto_Exibicao'] = df_status.apply(
            lambda row: f"{row['Qtd']} ({(row['Qtd'] / total_chamados) * 100:.1f}%)".replace('.', ','), 
            axis=1
        )
        
        fig_status = px.bar(
            df_status,
            x='Qtd',
            y='Status',
            orientation='h',
            text='Texto_Exibicao',
            color='Status',
            color_discrete_sequence=['#00c853', '#ff6d00', '#ff1744', '#29b6f6']
        )
        fig_status.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#ffffff',
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=False, title=""),
            showlegend=False,
            height=220,
            hovermode=False,
            margin=dict(l=10, r=40, t=10, b=10)
        )
        fig_status.update_traces(textposition='outside', hovertemplate=None, hoverinfo='none', cliponaxis=False)
        
        evento_status = st.plotly_chart(
            fig_status,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="grafico_status",
            config={'displayModeBar': False}
        )
        
        if evento_status and "selection" in evento_status and "points" in evento_status["selection"]:
            pontos = evento_status["selection"]["points"]
            if len(pontos) > 0:
                st.session_state["modal_filtro"] = pontos[0]["y"]
                st.session_state["modal_dados"] = df_filtrado[df_filtrado['Status V2'] == pontos[0]["y"]]
                st.session_state["abrir_dialog"] = True

# Gráfico 2: Categorias das Solicitações
with col_graf2:
    st.subheader("Categorias das Solicitações")
    if 'Título' in df_filtrado.columns and not df_filtrado.empty:
        df_titulos = df_filtrado['Título'].value_counts().head(5).reset_index()
        df_titulos.columns = ['Categoria', 'Qtd']
        
        df_titulos['Texto_Exibicao'] = df_titulos.apply(
            lambda row: f"{row['Qtd']} ({(row['Qtd'] / total_chamados) * 100:.1f}%)".replace('.', ','), 
            axis=1
        )
        
        fig_titulos = px.bar(
            df_titulos,
            x='Qtd',
            y='Categoria',
            orientation='h',
            text='Texto_Exibicao',
            color_discrete_sequence=['#0091ea']
        )
        fig_titulos.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='#ffffff',
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=False, title="", categoryorder='total ascending'),
            showlegend=False,
            height=250,
            hovermode=False,
            margin=dict(l=10, r=40, t=10, b=10)
        )
        fig_titulos.update_traces(textposition='outside', hovertemplate=None, hoverinfo='none', cliponaxis=False)
        
        evento_categoria = st.plotly_chart(
            fig_titulos,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="grafico_categorias",
            config={'displayModeBar': False}
        )
        
        if evento_categoria and "selection" in evento_categoria and "points" in evento_categoria["selection"]:
            pontos_cat = evento_categoria["selection"]["points"]
            if len(pontos_cat) > 0:
                st.session_state["modal_filtro"] = pontos_cat[0]["y"]
                st.session_state["modal_dados"] = df_filtrado[df_filtrado['Título'] == pontos_cat[0]["y"]]
                st.session_state["abrir_dialog"] = True

# Dispara o modal caso a flag de abertura esteja ativa
if st.session_state.get("abrir_dialog", False):
    st.session_state["abrir_dialog"] = False
    abrir_modal_detalhes()
