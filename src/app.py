import streamlit as st
import os
import sys
import time
import json
import tempfile
from google import genai

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "src" else CURRENT_DIR
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

try:
    from .agents import (
        ProposerAgent,
        EvaluatorAgent,
        DissertationAgent,
        DirectorAgent,
        ReviewerAgent,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key,
        resolve_gemini_api_keys,
        save_video_metadata_file
    )
    from .audio import AudioEngine, FALLBACK_VOICES, VOICE_PROSODY_PRESETS
    from .broll_engine import BRollEngine, find_cookie_file
    from .visual_engine import VisualEngine
    from .subtitles import convert_words_to_ass
    from .render import assemble_multi_scene_video
    from .checkpoint_manager import CheckpointManager
    from .algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY
    from .pronunciation import DEFAULT_PRONUNCIATION_ENGINE
    from .logger import (
        app_logger,
        get_recent_ui_logs,
        analyze_logs,
        LOGS_DIR,
        get_active_throttling_alerts,
        get_throttling_summary
    )
except ImportError:
    from agents import (
        ProposerAgent,
        EvaluatorAgent,
        DissertationAgent,
        DirectorAgent,
        ReviewerAgent,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key,
        resolve_gemini_api_keys,
        save_video_metadata_file
    )
    from audio import AudioEngine, FALLBACK_VOICES, VOICE_PROSODY_PRESETS
    from broll_engine import BRollEngine, find_cookie_file
    from visual_engine import VisualEngine
    from subtitles import convert_words_to_ass
    from render import assemble_multi_scene_video
    from checkpoint_manager import CheckpointManager
    from algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY
    from pronunciation import DEFAULT_PRONUNCIATION_ENGINE
    from logger import (
        app_logger,
        get_recent_ui_logs,
        analyze_logs,
        LOGS_DIR,
        get_active_throttling_alerts,
        get_throttling_summary
    )

st.set_page_config(
    page_title="AI Slop Studio - Automotive 9:16 Edition",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF4B4B, #FF8F00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #9E9E9E;
        margin-bottom: 1.5rem;
    }
    .badge-approved {
        background-color: #1B5E20;
        color: #81C784;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .badge-rejected {
        background-color: #B71C1C;
        color: #EF9A9A;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .stProgress > div > div > div > div {
        background-color: #FF8F00;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/sports-car.png", width=70)
    st.markdown("## ⚙️ Configurações do Estúdio")
    
    api_keys_env = resolve_gemini_api_keys()
    primary_val = api_keys_env[0] if len(api_keys_env) > 0 else ""
    fallback_val = api_keys_env[1] if len(api_keys_env) > 1 else ""

    api_key_primary = st.text_input("🔑 Gemini API Key (Principal):", value=primary_val, type="password")
    api_key_fallback = st.text_input("🛡️ Gemini API Key (Redundância/Fallback):", value=fallback_val, type="password", help="Chave secundária de backup acionada automaticamente caso a primária atinja o teto de cota (HTTP 429).")
    
    if api_key_primary:
        os.environ["GEMINI_API_KEY"] = api_key_primary
    if api_key_fallback:
        os.environ["GEMINI_FALLBACK_API_KEY"] = api_key_fallback

    if api_key_primary and api_key_fallback:
        st.success("🛡️ **Redundância Ativa:** 2 chaves prontas para fallback.")
    elif api_key_primary:
        st.info("ℹ️ Chave primária ativa.")

    st.markdown("---")
    st.markdown("### 🍪 Autenticação YouTube")
    cookie_path = find_cookie_file()
    if cookie_path:
        st.success(f"🛡️ `cookies.txt` ativo (`{os.path.basename(cookie_path)}`)")
    else:
        st.info("ℹ️ Modo anônimo. Insira `cookies.txt` na raiz para evitar bloqueios anti-bot do YouTube.")
        
    st.markdown("---")
    st.markdown("### 🤖 Modelo & Gestão de Quota")
    
    model_choice = st.selectbox(
        "Modelo Principal Gemini:",
        options=DEFAULT_FALLBACK_MODELS,
        index=0,
        help="Modelos ultrarrápidos e testados com cota gratuita abundante."
    )
    
    auto_fallback = st.checkbox(
        "🔄 Fallback Automático de Modelo",
        value=True,
        help="Se o modelo atingir cota ou timeout (>60s), tenta automaticamente o próximo modelo disponível."
    )
    
    auto_cooldown = st.checkbox(
        "⏳ Cooldown com Contador Regressivo",
        value=True,
        help="Se todos os modelos baterem cota, aguarda com contagem regressiva na tela."
    )
    
    st.markdown("---")
    st.markdown("### 🎙️ Voz, Dinâmica & Fonética")
    voice_choice = st.selectbox(
        "Voz do Narrador (Google Gemini Generativo):",
        options=FALLBACK_VOICES,
        index=0
    )
    
    style_preset_choice = st.selectbox(
        "🎭 Perfil de Dinâmica Vocal:",
        options=list(VOICE_PROSODY_PRESETS.keys()),
        index=0,
        help="Configura entonação, pitch e modulação rítmica para prender a atenção do público."
    )
    preset_data = VOICE_PROSODY_PRESETS.get(style_preset_choice, {})
    st.caption(f"ℹ️ {preset_data.get('description', '')}")
    
    rate_choice = st.selectbox(
        "⚡ Velocidade & Dinâmica (Pacing):",
        options=[
            f"{preset_data.get('rate', '+25%')} (Recomendado do Perfil)",
            "+35% (1.35x - Ultra Rápido)",
            "+25% (1.25x - Dinâmico)",
            "+15% (1.15x - Moderado)",
            "+0% (1.0x - Tradicional)"
        ],
        index=0,
        help="Controla a velocidade da locução neural e o ritmo dos cortes. O valor 1.25x (+25%) elimina pausas mortas e maximiza a retenção nos Shorts."
    )
    selected_rate = rate_choice.split()[0]
    selected_pitch = preset_data.get("pitch", "+3Hz")
    
    st.success("🗣️ **Pronúncia Fonética Ativa:** Termos em inglês e marcas são falados com sotaque nativo perfeito.")
    
    st.markdown("---")
    st.markdown("### ⚡ Concorrência & Paralelismo")
    workers_choice = st.selectbox(
        "Workers Concorrentes (Threads):",
        options=[1, 2, 3, 4, 5, 6, 8],
        index=3,
        help="Quantidade de downloads e análises do Gemini Vision processadas em paralelo. Padrão recomendado: 4."
    )
    
    st.markdown("---")
    st.markdown("### 🎨 Cores das Legendas")
    primary_col = st.color_picker("Cor Principal do Texto:", "#FFFFFF")
    highlight_col = st.color_picker("Cor da Caixa / Pill (Hormozi):", "#FFE500")
    
    st.markdown("---")
    st.caption("⚡ B-rolls Únicos (YouTube Fair Use) • Visual Cards IA 1080x1920 • Legendas Hormozi")

# Header Principal
st.markdown('<div class="main-header">⚡ AI Slop - Motores & Veículos Extremos (9:16)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Produção autônoma para entusiastas de motores e mecânica pesada (Carros, Aviões, Caças, Tanques, Motos, Náutica, Wankel, Diesel e Elétrico) com ritmo acelerado 1.25x e Gemini Charon.</div>', unsafe_allow_html=True)

def render_throttling_alerts_ui():
    """Exibe alertas de throttling de API e Download de Vídeo na WebUI (Item 1)."""
    alerts = get_active_throttling_alerts(max_age_seconds=180)
    if alerts:
        for al in alerts[-3:]:
            if al["source"] == "API_GEMINI":
                st.error(
                    f"🚨 **Alerta de Throttling na API Gemini [{al['time_str']}]:** {al['message']} "
                    f"(Aguardando liberação de cota: {al['retry_after']}s). Concorrência ajustada para 4 workers com cooldown automático ativo."
                )
            elif al["source"] == "YOUTUBE_DOWNLOAD":
                st.warning(
                    f"⚠️ **Alerta de Throttling no Download de Vídeo [{al['time_str']}]:** {al['message']} "
                    f"(Cooldown aplicado: {al['retry_after']}s)."
                )

# Tabs Principais: Produção, Batches/Checkpoints, Memória Algorítmica, Laboratório TTS & Logs/Diagnóstico
tab_prod, tab_batches, tab_memory, tab_tts, tab_diag = st.tabs([
    "🎬 Estúdio de Produção",
    "📦 Batches & Checkpoints (Auto)",
    "🧠 Memória Algorítmica & Feedback (.md)",
    "🎙️ Laboratório de Vozes (TTS)",
    "📊 Central de Logs & Diagnóstico"
])

with tab_prod:
    render_throttling_alerts_ui()
    if "temas" not in st.session_state:
        st.session_state.temas = []
    if "avaliacoes" not in st.session_state:
        st.session_state.avaliacoes = {}
    if "last_generated_video" not in st.session_state:
        st.session_state.last_generated_video = None

    def create_ui_cooldown_handler(container):
        def cooldown_callback(remaining, total, model_name):
            if remaining > 0:
                pct = 1.0 - (remaining / total)
                container.warning(
                    f"⏳ **Limite de Requisições Atingido no Modelo `{model_name}`!**\n\n"
                    f"Aguardando liberação de cota: **{remaining} segundos restantes**..."
                )
                container.progress(pct)
            else:
                container.empty()
        return cooldown_callback

    # Área de Controle de Temas
    col_ctrl1, col_ctrl2 = st.columns([1.2, 4])
    with col_ctrl1:
        btn_gerar = st.button("💡 Propor 10 Novos Temas (1-2 min)", type="primary", use_container_width=True)

    cooldown_box_top = st.empty()

    if btn_gerar:
        if not api_key:
            st.error("❌ Por favor, configure a sua chave de API do Gemini no menu lateral antes de continuar.")
        else:
            with st.status("🧠 **ProposerAgent** minerando os segredos mecânicos de carros lendários...", expanded=True) as status:
                live_status = st.empty()
                
                def on_proposer_status(msg):
                    live_status.markdown(f"📡 {msg}")
                    
                proposer = ProposerAgent(
                    model_name=model_choice,
                    auto_fallback=auto_fallback,
                    auto_cooldown=auto_cooldown
                )
                cooldown_fn = create_ui_cooldown_handler(cooldown_box_top)
                
                try:
                    has_new_an, an_msg = DEFAULT_ALGORITHM_MEMORY.check_and_auto_ingest_analytics()
                    if has_new_an:
                        st.toast(f"📊 {an_msg}", icon="🚀")
                    ckpt_mgr = CheckpointManager()
                    blacklist_titles = ckpt_mgr.get_blacklist_titles()
                    temas = proposer.generate_topics(
                        count=10,
                        blacklist=blacklist_titles,
                        cooldown_callback=cooldown_fn,
                        status_callback=on_proposer_status
                    )
                    if isinstance(temas, list) and len(temas) > 0:
                        st.session_state.temas = temas
                        st.session_state.avaliacoes = {}
                        status.update(label="✅ 10 Novos Temas Automotivos Gerados!", state="complete", expanded=False)
                        st.rerun()
                    else:
                        status.update(label="❌ Erro ao estruturar temas", state="error")
                        st.error(f"Resposta inesperada do Gemini: {temas}")
                except Exception as e:
                    status.update(label="❌ Falha na geração de temas", state="error")
                    st.error(f"Erro: {str(e)}")

    # Exibição dos Temas Propostos
    if st.session_state.temas:
        st.markdown("---")
        st.markdown("### 📋 Temas Automotivos em Pauta")
        
        for idx, tema in enumerate(st.session_state.temas):
            with st.container():
                st.markdown(f"#### 🎯 #{idx+1}: {tema.get('tema', 'Curiosidade Automotiva')}")
                
                c_hook, c_tech = st.columns([1, 1])
                with c_hook:
                    st.info(f"🎣 **Hook (Primeiros 3 segundos):**\n\n\"{tema.get('hook', '')}\"")
                with c_tech:
                    st.markdown(f"🔬 **Explicação Física/Mecânica:**\n\n{tema.get('explicacao_tecnica', '')}")
                
                # Exibição de Descrição e Tags geradas pela IA
                desc_text = tema.get("descricao", "")
                tags_data = tema.get("tags") or tema.get("hashtags")
                tags_str = " ".join([f"#{t.lstrip('#')}" for t in tags_data]) if isinstance(tags_data, list) else str(tags_data or "")
                if desc_text or tags_str:
                    with st.expander("📄 Descrição & Hashtags para o YouTube (Geradas pela IA)", expanded=False):
                        if desc_text:
                            st.markdown(f"**Descrição:**\n\n{desc_text}")
                        if tags_str:
                            st.markdown(f"**Hashtags:** `{tags_str}`")
                
                # Botões de Ação
                b_col1, b_col2, b_col3 = st.columns([1.2, 1.4, 3])
                
                with b_col1:
                    btn_eval = st.button(f"🧐 Avaliação #{idx+1}", key=f"eval_btn_{idx}", use_container_width=True)
                with b_col2:
                    btn_prod = st.button(f"🎬 Produzir Vídeo 9:16 #{idx+1}", key=f"prod_btn_{idx}", type="primary", use_container_width=True)
                
                # Processamento de Avaliação Cega
                if btn_eval:
                    cooldown_box_eval = st.empty()
                    with st.status(f"🧐 **EvaluatorAgent** analisando o tema #{idx+1}...", expanded=True) as eval_status:
                        eval_live = st.empty()
                        
                        evaluator = EvaluatorAgent(
                            model_name=model_choice,
                            auto_fallback=auto_fallback,
                            auto_cooldown=auto_cooldown
                        )
                        
                        def on_eval_status(msg):
                            eval_live.markdown(f"📡 {msg}")
                            
                        cooldown_eval_fn = create_ui_cooldown_handler(cooldown_box_eval)
                        
                        try:
                            avaliacao = evaluator.evaluate_topic(
                                tema,
                                cooldown_callback=cooldown_eval_fn,
                                status_callback=on_eval_status
                            )
                            st.session_state.avaliacoes[idx] = avaliacao
                            eval_status.update(label="✅ Avaliação Concluída!", state="complete", expanded=False)
                            st.rerun()
                        except Exception as e:
                            eval_status.update(label="❌ Falha na Avaliação", state="error")
                            st.error(f"Erro: {str(e)}")
                
                # Exibição da Avaliação Cega se já realizada
                if idx in st.session_state.avaliacoes:
                    av = st.session_state.avaliacoes[idx]
                    nota = av.get('nota', 0.0)
                    veredicto = av.get('veredicto', 'Em análise')
                    badge_class = "badge-approved" if (isinstance(nota, (int, float)) and nota >= 7.0) else "badge-rejected"
                    
                    st.markdown(f"""
                    <div style="background-color: #252530; padding: 12px; border-radius: 8px; margin-top: 8px; border-left: 4px solid {'#81C784' if (isinstance(nota, (int, float)) and nota>=7.0) else '#EF9A9A'};">
                        <span class="{badge_class}">Nota: {nota}/10 • {veredicto}</span>
                        <p style="margin-top: 8px; margin-bottom: 0px; font-size: 0.95rem;"><b>Parecer do Diretor:</b> {av.get('justificativa', '')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # PIPELINE DE PRODUÇÃO MULTI-CENAS 9:16
                if btn_prod:
                    st.markdown("---")
                    st.markdown(f"### ⚙️ Linha de Produção Ativa: *{tema.get('tema')}*")
                    
                    cooldown_box_prod = st.empty()
                    progress_bar = st.progress(0, text="Iniciando Estúdio de Produção...")
                    status_widget = st.status("🎬 **Preparando Produção Multi-Cenas...**", expanded=True)
                    status_live = status_widget.empty()
                    
                    st.markdown("##### 📜 Terminal de Execução ao Vivo (Streaming)")
                    log_placeholder = st.empty()
                    logs = []
                    
                    def add_log(msg):
                        logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                        log_placeholder.code("\n".join(logs[-25:]), language="text")
                    
                    def update_status_live(msg):
                        status_live.markdown(f"📡 {msg}")
                        add_log(msg)
                    
                    cooldown_prod_fn = create_ui_cooldown_handler(cooldown_box_prod)
                    
                    project_dir = os.path.join(os.getcwd(), f"project_{idx}")
                    os.makedirs(project_dir, exist_ok=True)
                    meta_path = save_video_metadata_file(project_dir, tema)
                    add_log(f"Metadados criados (Título, Descrição e Hashtags): {meta_path}")
                    
                    try:
                        # ETAPA 1: DissertationAgent redigindo monografia de engenharia mecânica (Fase 1)
                        progress_bar.progress(8, text="[1/6] DissertationAgent redigindo dissertação técnica profunda...")
                        update_status_live(f"🔬 **DissertationAgent:** Construindo estudo de engenharia mecânica com `{model_choice}`...")
                        
                        dissertator = DissertationAgent(
                            model_name=model_choice,
                            auto_fallback=auto_fallback,
                            auto_cooldown=auto_cooldown
                        )
                        
                        def on_dissertation_status(msg):
                            status_live.markdown(f"🔬 **Dissertation:** {msg}")
                            add_log(msg)
                            
                        dissertacao_data = dissertator.generate_dissertation(
                            tema,
                            cooldown_callback=cooldown_prod_fn,
                            status_callback=on_dissertation_status
                        )
                        add_log(f"Dissertação técnica concluída ({len(dissertacao_data.get('dissertacao_completa', '').split())} palavras de engenharia pura)!")
                        
                        with st.expander("🔬 Dissertação Técnica Profunda (Fase 1 da Síntese)", expanded=False):
                            st.markdown(f"**Desafio Físico:** {dissertacao_data.get('desafio_de_engenharia')}")
                            st.markdown(f"**Solução Mecânica:** {dissertacao_data.get('solucao_mecanica')}")
                            st.markdown(f"**Telemetria & Pista:** {dissertacao_data.get('impacto_historico_telemetria')}")
                            st.markdown(f"**Texto Completo:**\n{dissertacao_data.get('dissertacao_completa')}")

                        # ETAPA 2: DirectorAgent destilando a dissertação em roteiro de alta retenção (Fase 2)
                        progress_bar.progress(18, text="[2/6] DirectorAgent destilando roteiro dinâmico e plano de cortes...")
                        update_status_live(f"✍️ **DirectorAgent:** Destilando monografia em 14 a 22 cortes dinâmicos com `{model_choice}`...")
                        
                        director = DirectorAgent(
                            model_name=model_choice,
                            auto_fallback=auto_fallback,
                            auto_cooldown=auto_cooldown
                        )
                        
                        def on_director_status(msg):
                            status_live.markdown(f"✍️ **Director:** {msg}")
                            add_log(msg)
                            
                        cenas = director.generate_storyboard(
                            tema,
                            dissertacao_data=dissertacao_data,
                            cooldown_callback=cooldown_prod_fn,
                            status_callback=on_director_status
                        )
                        
                        if not cenas:
                            raise Exception("Falha ao gerar storyboard com cenas.")
                            
                        add_log(f"Storyboard concluído com {len(cenas)} cenas planejadas!")
                        
                        with st.expander(f"📋 Plano de Cenas & Storyboard ({len(cenas)} Cortes)", expanded=False):
                            for c_i, c in enumerate(cenas):
                                st.markdown(f"**Cena #{c_i+1} [{c.get('tipo', 'broll').upper()}]:** \"{c.get('fala', '')}\"")
                                if c.get('tipo') == 'broll':
                                    st.caption(f"🔍 Busca YouTube: `{c.get('youtube_query')}`")
                                else:
                                    st.caption(f"🎨 Infográfico: `{c.get('card_data', {}).get('titulo', 'Card')}`")
                        
                        # ETAPA 3: Síntese de Voz com Google Gemini Generative TTS (Charon)
                        progress_bar.progress(30, text="[3/6] Sintetizando Narração Generativa com Google Gemini...")
                        update_status_live(f"🎙️ **Gemini TTS:** Gravando áudio ({voice_choice}) e alinhando timestamps...")
                        
                        full_script = " ".join([c.get("fala", "").strip() for c in cenas if c.get("fala")])
                        if not full_script:
                            full_script = tema.get('hook', '') + " " + tema.get('explicacao_tecnica', '')
                            
                        audio_engine = AudioEngine(voice=voice_choice, rate=selected_rate, pitch=selected_pitch)
                        mp3_path = os.path.join(project_dir, "audio.mp3")
                        
                        success_audio, words_timing = audio_engine.generate_audio(full_script, mp3_path)
                        if not success_audio:
                            raise Exception(f"Falha na síntese de voz: {words_timing}")
                            
                        total_audio_duration = words_timing[-1].get("end", 60.0) if words_timing else 60.0
                        add_log(f"Narração concluída: {total_audio_duration:.1f}s de áudio ({len(words_timing)} palavras, velocidade {selected_rate}).")
                        
                        # ETAPA 3: Obtenção e Auditoria Concorrente em Batches (Parallel Processing)
                        progress_bar.progress(40, text="[3/5] Coletando e auditando B-rolls em paralelo (Gemini Vision Concorrente)...")
                        update_status_live("🎬 **Produção Visual Concorrente:** Baixando e auditando cenas em paralelo...")
                        
                        broll_engine = BRollEngine(max_search_results=6)
                        reviewer = ReviewerAgent(
                            model_name=model_choice,
                            auto_fallback=auto_fallback,
                            auto_cooldown=auto_cooldown
                        )
                        global_topic_name = tema.get('tema', 'Carro Esportivo')
                        
                        def on_parallel_progress(done_count, total_count):
                            try:
                                pct = int(40 + (done_count / total_count) * 35)
                                progress_bar.progress(pct, text=f"[3/5] Cenas auditadas e aprovadas: {done_count}/{total_count}...")
                            except:
                                pass
                        
                        def on_parallel_status(msg):
                            try:
                                update_status_live(msg)
                            except:
                                pass
                            try:
                                add_log(msg)
                            except:
                                pass

                        scene_clips, scene_audits = broll_engine.process_all_scenes_parallel(
                            cenas=cenas,
                            global_topic=global_topic_name,
                            reviewer_agent=reviewer,
                            project_dir=project_dir,
                            total_audio_duration=total_audio_duration,
                            words_timing=words_timing,
                            tail_overhead=0.5,
                            max_workers=workers_choice,
                            status_callback=on_parallel_status,
                            progress_callback=on_parallel_progress
                        )
                                
                        if not scene_clips:
                            raise Exception("Nenhum clipe visual foi aprovado para produção.")
                            
                        add_log(f"Total de {len(scene_clips)} clipes auditados e APROVADOS pelo ReviewerAgent em processamento concorrente!")
                        
                        with st.expander(f"🛡️ Relatório de Auditoria Visual do ReviewerAgent ({len(scene_audits)} Cortes Aprovados)", expanded=False):
                            for sa in scene_audits:
                                st.markdown(f"**Cena #{sa['cena']}:** *\"{sa['fala'][:60]}...\"*")
                                st.markdown(f"🎬 **Vídeo:** `{sa['titulo']}` | ⭐ **Nota:** `{sa['score']}/10`")
                                st.caption(f"🔍 **Parecer do Reviewer:** {sa['motivo']} • *Detectado: {sa['elementos']}*")
                                st.divider()
                        
                        # ETAPA 4: Legendas Dinâmicas Hormozi (Pill Amarela Neon)
                        progress_bar.progress(80, text="[4/5] Formatando Legendas Dinâmicas com Pill Box (.ass)...")
                        update_status_live("🎨 **Subtitles:** Compilando legendas com destaque de caixa amarela...")
                        
                        ass_path = os.path.join(project_dir, "subtitles.ass")
                        p_hex = primary_col.lstrip("#")
                        h_hex = highlight_col.lstrip("#")
                        convert_words_to_ass(words_timing, ass_path, primary_color=p_hex, highlight_color=h_hex, tail_overhead=0.4)
                        add_log(f"Legendas ASS geradas com destaque Pill Box: {ass_path}")
                        
                        # ETAPA 5: Montagem Multi-Cenas e Renderização FFmpeg
                        progress_bar.progress(90, text="[5/5] Renderizando Composição Final 9:16 no FFmpeg...")
                        update_status_live("⚡ **FFmpeg:** Unindo clipes, sincronizando áudio e queimando legendas...")
                        
                        final_mp4 = os.path.join(project_dir, "final_video.mp4")
                        success_render, msg = assemble_multi_scene_video(
                            clip_paths=scene_clips,
                            audio_path=mp3_path,
                            ass_path=ass_path,
                            output_path=final_mp4,
                            status_callback=update_status_live
                        )
                        
                        if not success_render:
                            raise Exception(f"Falha no FFmpeg: {msg}")
                            
                        progress_bar.progress(100, text="🎉 Produção 9:16 Concluída com Sucesso!")
                        status_widget.update(label="🚀 **Vídeo 9:16 Renderizado e Pronto para Publicação!**", state="complete", expanded=False)
                        add_log(f"🎬 Vídeo final concluído: {final_mp4} ({os.path.getsize(final_mp4)} bytes)")
                        
                        # Registro na Memória Algorítmica (.md)
                        try:
                            DEFAULT_ALGORITHM_MEMORY.record_video_generation({
                                "video_id": f"project_{idx}",
                                "batch": "ui_manual",
                                "video_index": idx,
                                "tema": tema.get("tema", ""),
                                "core_entity": extract_core_entity(tema.get("tema", "")),
                                "hook": tema.get("hook", ""),
                                "dissertacao_resumo": dissertacao_data.get("dissertacao_completa", "")[:200],
                                "duracao_segundos": total_audio_duration,
                                "palavras_totais": len(words_timing),
                                "total_cenas": len(cenas),
                                "estilo_voz": voice_choice
                            })
                            DEFAULT_ALGORITHM_MEMORY.export_metrics_csv()
                            DEFAULT_ALGORITHM_MEMORY.export_metrics_markdown()
                            add_log("🧠 Vídeo registrado na Base de Inteligência e METRICAS_VIDEOS.csv atualizado na raiz!")
                        except Exception as e_mem:
                            app_logger.warning(f"Erro ao registrar vídeo na memória: {str(e_mem)}")

                        st.session_state.last_generated_video = final_mp4
                        
                        # Exibição do Vídeo Final
                        st.markdown("---")
                        st.success("🎉 **VÍDEO 9:16 PRONTO!** Confira o resultado final:")
                        
                        v_col1, v_col2 = st.columns([1, 1.2])
                        with v_col1:
                            st.video(final_mp4)
                        with v_col2:
                            st.markdown("#### 📦 Arquivos do Projeto")
                            st.audio(mp3_path)
                            with open(final_mp4, "rb") as vf:
                                st.download_button(
                                    label="📥 Baixar Vídeo Final (MP4 1080x1920 9:16)",
                                    data=vf,
                                    file_name="curiosidade_automotiva_9x16.mp4",
                                    mime="video/mp4",
                                    type="primary"
                                )
                            with open(ass_path, "rb") as af:
                                st.download_button(
                                    label="📄 Baixar Legendas (.ass)",
                                    data=af,
                                    file_name="subtitles.ass",
                                    mime="text/plain"
                                )
                            meta_file = os.path.join(project_dir, "metadata.txt")
                            if os.path.exists(meta_file):
                                with open(meta_file, "r", encoding="utf-8") as mf:
                                    meta_txt = mf.read()
                                st.download_button(
                                    label="📋 Baixar Título, Descrição & Hashtags (.txt)",
                                    data=meta_txt,
                                    file_name="metadata_youtube_shorts.txt",
                                    mime="text/plain"
                                )
                                with st.expander("📋 Ver Título, Descrição e Hashtags (.txt)", expanded=False):
                                    st.code(meta_txt, language="text")
                                
                    except Exception as err:
                        progress_bar.progress(100, text="❌ Ocorreu um erro durante a produção")
                        status_widget.update(label="❌ **Falha no Pipeline**", state="error")
                        st.error(f"Erro no pipeline: {str(err)}")
                        add_log(f"ERRO: {str(err)}")
                
                st.markdown("<br>", unsafe_allow_html=True)

with tab_batches:
    st.markdown("### 📦 Gerenciamento de Lotes (Batches) & Checkpoints")
    st.caption("Acompanhe o processamento autônomo contínuo (batches de 10 vídeos cada) com recuperação automática de estado pós-queda de energia.")

    ckpt_mgr = CheckpointManager()
    
    col_b_act1, col_b_act2, col_b_act3 = st.columns([1.5, 1.5, 3])
    with col_b_act1:
        if st.button("🔄 Atualizar Painel de Checkpoints", use_container_width=True):
            st.rerun()
    with col_b_act2:
        if st.button("🛠️ Reconstruir Estado do Disco", use_container_width=True):
            ckpt_mgr.rebuild_global_state_from_disk()
            st.success("Estado global sincronizado com os arquivos físicos no disco!")
            st.rerun()

    global_state = ckpt_mgr.load_global_state()
    blacklist_items = ckpt_mgr.load_blacklist()
    
    # Métricas Gerais
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vídeos 100% Finalizados", global_state.get("total_videos_completed", 0))
    m2.metric("Lote (Batch) Ativo", f"batch_{global_state.get('current_batch_index', 0)}")
    m3.metric("Temas na Blacklist", len(blacklist_items))
    
    # Checagem rápida de agendamento no startup
    startup_path = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AISlopStudio_AutoRecovery.lnk")
    is_startup_active = os.path.exists(startup_path)
    m4.metric("Auto-Recuperação no Windows", "✅ ATIVO" if is_startup_active else "ℹ️ Standby")

    st.markdown("---")
    
    # Sub-tabs: Visualização de Batches e Tabela da Blacklist
    subtab_batches, subtab_blacklist = st.tabs(["🗂️ Lotes de Produção (batch_0 .. batch_N)", "🚫 Blacklist de Temas Já Gravados"])
    
    with subtab_batches:
        batches_dict = global_state.get("batches", {})
        if not batches_dict:
            st.info("Nenhum lote foi iniciado ainda. Execute o arquivo `iniciar_auto_geracao.bat` para iniciar a linha de produção autônoma contínua!")
        else:
            for b_name in sorted(batches_dict.keys(), key=lambda x: int(x.split('_')[1]) if '_' in x else 0):
                b_info = batches_dict[b_name]
                b_idx = b_info.get("batch_index", 0)
                comp_cnt = b_info.get("completed_videos_count", 0)
                tot_cnt = b_info.get("total_videos", 10)
                is_comp = b_info.get("status") == "COMPLETED"
                
                status_badge = "🟢 CONCLUÍDO" if is_comp else f"🟡 EM ANDAMENTO ({comp_cnt}/{tot_cnt})"
                
                with st.expander(f"📦 **{b_name.upper()}** — {status_badge}", expanded=(not is_comp)):
                    cols = st.columns(2)
                    for v_idx in range(tot_cnt):
                        col = cols[v_idx % 2]
                        v_ckpt = ckpt_mgr.load_video_checkpoint(b_idx, v_idx)
                        v_status = v_ckpt.get("status", "PENDING")
                        topic = v_ckpt.get("topic", {})
                        t_title = topic.get("tema", f"Vídeo #{v_idx+1} (Pendente)")
                        
                        with col:
                            card_border = "#81C784" if v_status == "COMPLETED" else "#FFB74D" if v_status != "PENDING" else "#424242"
                            st.markdown(f"""
                            <div style="background-color: #1E1E28; border-left: 4px solid {card_border}; padding: 10px; border-radius: 6px; margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <b>video_{v_idx}</b>
                                    <span style="font-size: 0.8rem; background-color: #2D2D3D; padding: 2px 8px; border-radius: 4px;">{v_status}</span>
                                </div>
                                <div style="margin-top: 6px; font-size: 0.9rem; color: #E0E0E0;"><b>Tema:</b> {t_title}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            v_dir = ckpt_mgr.get_video_dir(b_idx, v_idx)
                            final_video_file = os.path.join(v_dir, "final_video.mp4")
                            if os.path.exists(final_video_file) and os.path.getsize(final_video_file) > 100_000:
                                st.video(final_video_file)
                                dl_c1, dl_c2 = st.columns([1, 1])
                                with dl_c1:
                                    with open(final_video_file, "rb") as vf:
                                        st.download_button(
                                            label=f"📥 Vídeo MP4",
                                            data=vf,
                                            file_name=f"{b_name}_video_{v_idx}.mp4",
                                            mime="video/mp4",
                                            key=f"dl_b_{b_idx}_v_{v_idx}",
                                            use_container_width=True
                                        )
                                with dl_c2:
                                    meta_file = os.path.join(v_dir, "metadata.txt")
                                    if not os.path.exists(meta_file) and topic:
                                        meta_file = save_video_metadata_file(v_dir, topic)
                                    if os.path.exists(meta_file):
                                        with open(meta_file, "r", encoding="utf-8") as mf:
                                            m_txt = mf.read()
                                        st.download_button(
                                            label=f"📄 Metadados .txt",
                                            data=m_txt,
                                            file_name=f"{b_name}_video_{v_idx}_metadata.txt",
                                            mime="text/plain",
                                            key=f"dl_meta_{b_idx}_{v_idx}",
                                            use_container_width=True
                                        )

    with subtab_blacklist:
        st.markdown("#### 📜 Registro de Temas Proibidos (Blacklist)")
        st.caption("Todos os temas listados abaixo são alimentados automaticamente ao `ProposerAgent` para garantir que o sistema jamais repita o mesmo conteúdo.")
        
        if not blacklist_items:
            st.info("A Blacklist está vazia no momento. Conforme os vídeos forem propostos e gravados, eles serão registrados aqui automaticamente.")
        else:
            table_data = []
            for item in reversed(blacklist_items):
                table_data.append({
                    "Tema": item.get("tema", ""),
                    "Veículo/Entidade": item.get("core_entity", ""),
                    "Lote/Vídeo": f"{item.get('batch', '')}/{item.get('video', '')}",
                    "Registrado Em": item.get("timestamp", "")
                })
            st.dataframe(table_data, use_container_width=True)

with tab_memory:
    st.markdown("### 🧠 Inteligência Algorítmica, Big Data & Memória (.md)")
    st.caption(
        "A IA geradora possui memória contínua em `.md` com pesos auxiliares dinâmicos. "
        "Insira os dados analíticos retornados pelo YouTube (views, retenção aos 3s, APV, CTR) "
        "para calibrar automaticamente a convergência do estilo de sucesso sem repetir o assunto."
    )
    
    memory_sys = DEFAULT_ALGORITHM_MEMORY
    
    subtab_feedback, subtab_weights, subtab_csv, subtab_md = st.tabs([
        "📥 Ingestão Rápida de Métricas",
        "🎯 Pesos Auxiliares Ativos (Style Vector)",
        "📊 Planilha METRICAS_VIDEOS.csv (Raiz)",
        "📄 Visualizador de ALGORITHM_MEMORY.md"
    ])
    
    with subtab_feedback:
        st.markdown("#### 📥 Registrar Métricas Reais do YouTube")
        history = memory_sys.load_history()
        
        col_f1, col_f2 = st.columns([1.5, 1])
        with col_f1:
            video_options = []
            for r in history:
                b = r.get("batch", "batch_0")
                v = r.get("video_index", 0)
                t = r.get("tema", "")
                video_options.append(f"{b}/video_{v} — {t[:40]}")
                
            if not video_options:
                st.info("Nenhum vídeo registrado no histórico ainda. Gere vídeos no Estúdio ou via Batches para habilitar a ingestão de feedback.")
                selected_v = st.text_input("Ou digite o identificador manual do vídeo:", "batch_0/video_0")
            else:
                selected_opt = st.selectbox("Selecione o vídeo publicado:", video_options)
                selected_v = selected_opt.split(" — ")[0]
                
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                views_in = st.number_input("Visualizações Totais (Views):", min_value=0, value=10000, step=500)
                ret_3s_in = st.slider("Retenção aos 3 Segundos (%):", min_value=0.0, max_value=100.0, value=75.0, step=0.5, help="Métrica crucial do gancho/hook.")
                ctr_in = st.slider("Taxa de Cliques no Feed / CTR (%):", min_value=0.0, max_value=100.0, value=10.0, step=0.5)
            with c_m2:
                apv_in = st.slider("Average Percentage Viewed / APV (%):", min_value=0.0, max_value=200.0, value=82.0, step=0.5, help="Retenção média ao longo de todo o vídeo.")
                likes_in = st.number_input("Curtidas (Likes):", min_value=0, value=850, step=50)
                comments_in = st.number_input("Comentários:", min_value=0, value=45, step=5)
                
            notes_in = st.text_area("Observações Qualitativas / Motivo do Destaque:", "Ótimo ritmo nos cortes e explicação clara da física.")
            
            if st.button("💾 Salvar Feedback & Recalibrar Memória Algorítmica", type="primary", use_container_width=True):
                ok, msg, rec = memory_sys.ingest_analytics_feedback(
                    identifier=selected_v,
                    views=views_in,
                    retention_3s_pct=ret_3s_in,
                    apv_pct=apv_in,
                    ctr_pct=ctr_in,
                    likes=likes_in,
                    comments=comments_in,
                    shares=0,
                    feedback_notes=notes_in
                )
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
                    
        with col_f2:
            st.markdown("#### 🏆 Classificação de Tiers de Desempenho")
            st.markdown("""
            - 🏆 **Tier S (Super Viral):** APV > 85% e Retenção 3s > 75%
            - 🥇 **Tier A (Excelente):** APV > 70% e Retenção 3s > 65%
            - 🥈 **Tier B (Sólido):** APV > 55% e Retenção 3s > 50%
            - 🥉 **Tier C (Abaixo da Média):** APV < 50%
            - ⚠️ **Tier D (Queda Imediata no Gancho):** Retenção 3s < 45%
            """)
            
        st.markdown("---")
        st.markdown("#### 📋 Histórico Consolidado de Desempenho")
        if history:
            tbl = []
            for r in history:
                an = r.get("analytics", {})
                tbl.append({
                    "Lote/Vídeo": f"{r.get('batch')}/v{r.get('video_index')}",
                    "Tema": r.get("tema", ""),
                    "Tier": an.get("performance_tier", "PENDING"),
                    "Views": an.get("views", "-"),
                    "Ret. 3s": f"{an.get('retention_3s_pct')}%" if an.get('retention_3s_pct') is not None else "-",
                    "APV %": f"{an.get('apv_pct')}%" if an.get('apv_pct') is not None else "-",
                    "Notas": an.get("feedback_notes", "")
                })
            st.dataframe(tbl, use_container_width=True)
            
    with subtab_weights:
        st.markdown("#### 🎯 Calibração dos Pesos Auxiliares (Algorithmic Guidance)")
        st.caption("Estes pesos modulam a densidade técnica, a frequência de cortes e o tom do roteirista.")
        weights = memory_sys.load_weights()
        
        w_cols = st.columns(2)
        with w_cols[0]:
            hook_w = st.slider("hook_curiosity_gap_weight (Curiosidade & Gancho):", 0.0, 1.0, float(weights.get("hook_curiosity_gap_weight", 0.95)), 0.01)
            tech_w = st.slider("technical_depth_weight (Densidade Técnica):", 0.0, 1.0, float(weights.get("technical_depth_weight", 0.92)), 0.01)
            anti_hype_w = st.slider("anti_hype_precision_weight (Zero Buzzwords Vazias):", 0.0, 1.0, float(weights.get("anti_hype_precision_weight", 0.90)), 0.01)
            sound_w = st.slider("visceral_sound_focus_weight (Foco em Som Puro 4K):", 0.0, 1.0, float(weights.get("visceral_sound_focus_weight", 0.88)), 0.01)
        with w_cols[1]:
            telemetry_w = st.slider("telemetry_density_weight (Telemetria & Dados Exatos):", 0.0, 1.0, float(weights.get("telemetry_density_weight", 0.85)), 0.01)
            cadence_w = st.slider("pacing_cadence_wpm (Velocidade em Palavras/Minuto):", 140.0, 240.0, float(weights.get("pacing_cadence_wpm", 185.0)), 5.0)
            cut_freq_w = st.slider("broll_cut_frequency_sec (Frequência de Cortes em Segundos):", 1.5, 5.0, float(weights.get("broll_cut_frequency_sec", 2.8)), 0.1)
            comment_w = st.slider("comment_trigger_weight (Provocação Final de Comentários):", 0.0, 1.0, float(weights.get("comment_trigger_weight", 0.85)), 0.01)
            
        if st.button("💾 Salvar Ajuste Manual de Pesos Auxiliares", type="secondary"):
            weights.update({
                "hook_curiosity_gap_weight": hook_w,
                "technical_depth_weight": tech_w,
                "anti_hype_precision_weight": anti_hype_w,
                "visceral_sound_focus_weight": sound_w,
                "telemetry_density_weight": telemetry_w,
                "pacing_cadence_wpm": cadence_w,
                "broll_cut_frequency_sec": cut_freq_w,
                "comment_trigger_weight": comment_w
            })
            memory_sys.save_weights(weights)
            memory_sys.generate_memory_markdown()
            memory_sys.export_metrics_csv()
            memory_sys.export_metrics_markdown()
            st.success("Pesos auxiliares atualizados e ALGORITHM_MEMORY.md regravado com sucesso!")
            st.rerun()

    with subtab_csv:
        st.markdown("#### 📦 Ingestão Automática de Analytics do YouTube (.zip em `/analytics`)")
        st.caption("Solte o arquivo `.zip` exportado diretamente do YouTube Studio na pasta `analytics/` ou envie pelo botão abaixo para sincronizar visualizações, APV % e retenção automaticamente.")

        from analytics_parser import DEFAULT_ANALYTICS_PARSER
        detected_zips = DEFAULT_ANALYTICS_PARSER.list_all_zips()

        col_zip_info, col_zip_act = st.columns([2, 1])
        with col_zip_info:
            if detected_zips:
                st.success(f"📦 **{len(detected_zips)} export(s) .zip detectado(s) em `/analytics`:**")
                for zp in detected_zips[:3]:
                    z_size_kb = os.path.getsize(zp) / 1024
                    z_time = time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(zp)))
                    st.write(f"- `{os.path.basename(zp)}` ({z_size_kb:.1f} KB - {z_time})")
            else:
                st.info("ℹ️ Nenhum arquivo `.zip` encontrado na pasta `analytics/`. Coloque o arquivo exportado do YouTube Studio lá.")

        with col_zip_act:
            if detected_zips:
                if st.button("🚀 Processar Export do YouTube (.zip)", type="primary", use_container_width=True):
                    upd_c, ign_c, msgs = memory_sys.ingest_from_analytics_zip(detected_zips[0])
                    st.success(f"🎉 Sincronizados {upd_c} vídeos com o YouTube!")
                    with st.expander("Ver detalhes do casamento de vídeos", expanded=True):
                        for m in msgs:
                            st.write(m)
                    st.rerun()

        # Uploader direto no navegador como alternativa conveniente
        uploaded_zip = st.file_uploader("Ou envie o arquivo .zip do YouTube Studio aqui:", type=["zip"])
        if uploaded_zip is not None:
            save_path = os.path.join(DEFAULT_ANALYTICS_PARSER.analytics_dir, uploaded_zip.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_zip.getbuffer())
            st.success(f"Arquivo `{uploaded_zip.name}` salvo em `/analytics`!")
            upd_c, ign_c, msgs = memory_sys.ingest_from_analytics_zip(save_path)
            st.success(f"Processados {upd_c} vídeos do YouTube!")
            st.rerun()

        st.markdown("---")
        st.markdown("#### 📊 Planilha Local de Métricas (`METRICAS_VIDEOS.csv`)")
        
        c_sync1, c_sync2, c_sync3 = st.columns([1.5, 1.5, 2])
        with c_sync1:
            if st.button("🔍 Varrer Checkpoints & Atualizar CSV", use_container_width=True):
                val_c, ign_c = memory_sys.scan_and_sync_checkpoints()
                st.success(f"Sincronizados {val_c} vídeos válidos! ({ign_c} descartados por segurança)")
                st.rerun()
        with c_sync2:
            if st.button("🔄 Importar Views do CSV Manual", use_container_width=True):
                upd_c, ign_c, msgs = memory_sys.import_metrics_csv()
                st.success(f"Processados {upd_c} vídeos com novas métricas!")
                st.rerun()
                
        csv_path_root = os.path.join(os.getcwd(), "METRICAS_VIDEOS.csv")
        md_path_root = os.path.join(os.getcwd(), "METRICAS_VIDEOS.md")
        
        if os.path.exists(csv_path_root):
            with open(csv_path_root, "rb") as cf:
                st.download_button(
                    label="📥 Baixar METRICAS_VIDEOS.csv",
                    data=cf,
                    file_name="METRICAS_VIDEOS.csv",
                    mime="text/csv"
                )
            
            # Exibição da tabela formatada
            history_data = memory_sys.load_history()
            table_records = []
            for r in history_data:
                an = r.get("analytics", {})
                gw = r.get("generation_weights", {})
                table_records.append({
                    "Identificador": r.get("video_id"),
                    "Título": r.get("tema"),
                    "Veículo": r.get("core_entity"),
                    "Dias Ativo": f"{an.get('exposure_days', 1.0):.1f}d",
                    "Views": an.get("views", 0),
                    "Views/Dia (VPD)": an.get("views_per_day", 0.0),
                    "Proj. 28d": an.get("projected_28d_views", 0),
                    "APV %": an.get("apv_pct"),
                    "CTR %": an.get("ctr_pct"),
                    "Trajetória": an.get("growth_trajectory", "STEADY_GROWTH"),
                    "Tier": an.get("performance_tier", "PENDING"),
                    "Peso Hook": gw.get("hook_curiosity_gap_weight", 0.95),
                    "Peso Tech": gw.get("technical_depth_weight", 0.92),
                    "Status": r.get("status_metadata", "VALIDO")
                })
            if table_records:
                st.dataframe(table_records, use_container_width=True)
        else:
            st.info("Arquivo METRICAS_VIDEOS.csv ainda não foi gerado. Clique em 'Varrer Checkpoints' para criá-lo agora.")

    with subtab_md:
        st.markdown("#### 📄 Documento da Memória em Markdown (`ALGORITHM_MEMORY.md`)")
        md_file = memory_sys.memory_md_file
        if os.path.exists(md_file):
            with open(md_file, "r", encoding="utf-8") as mf:
                md_content = mf.read()
            st.markdown(md_content)
            with st.expander("📝 Ver Código-Fonte Markdown Puro", expanded=False):
                st.code(md_content, language="markdown")
        else:
            st.info("O arquivo ALGORITHM_MEMORY.md ainda não foi gerado.")

with tab_tts:
    st.markdown("### 🎙️ Laboratório Comparativo de Vozes Neurais & TTS")
    st.markdown("Ouça e compare todas as **20 alternativas de áudio geradas automaticamente** pelos múltiplos motores de IA para encontrar a opção com maior naturalidade, respiração e cadência.")
    
    testes_dir = os.path.join(os.getcwd(), "testes-tts")
    meta_file = os.path.join(testes_dir, "metadata_benchmarks.json")
    
    col_t1, col_t2 = st.columns([1.5, 3])
    with col_t1:
        if st.button("⚡ Re-executar Benchmark Completo", type="primary", use_container_width=True):
            with st.spinner("Sintetizando todas as alternativas em paralelo..."):
                import subprocess
                subprocess.run(["py", "-3.11", "scripts/benchmark_tts.py"], check=True)
                st.success("Benchmark concluído! Áudios atualizados.")
                st.rerun()
    with col_t2:
        if os.path.exists(meta_file):
            with open(meta_file, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
            st.info(f"📁 **{meta_data.get('total_options', 0)} alternativas geradas** em `{meta_data.get('generated_at')}`.")
            
    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
        options = meta_data.get("options", [])
        
        st.markdown("---")
        st.markdown(f"**Texto Padronizado de Teste:** *\"{meta_data.get('text', '')}\"*")
        st.markdown("---")
        
        for i in range(0, len(options), 2):
            c1, c2 = st.columns(2)
            for col, opt_idx in [(c1, i), (c2, i + 1)]:
                if opt_idx < len(options):
                    opt = options[opt_idx]
                    with col:
                        with st.container(border=True):
                            st.markdown(f"##### #{opt_idx+1:02d} — {opt.get('description', opt['voice'])}")
                            st.caption(f"**Motor:** `{opt['engine']}` | **Voz:** `{opt['voice']}` | **Latência:** `{opt['latency_sec']}s`")
                            st.caption(f"ℹ️ {opt.get('notes', '')}")
                            audio_file_path = os.path.join(testes_dir, opt["file"])
                            if os.path.exists(audio_file_path):
                                with open(audio_file_path, "rb") as af:
                                    st.audio(af.read(), format="audio/mp3")
                            else:
                                st.warning("Arquivo de áudio não encontrado.")
    else:
        st.warning("Nenhum áudio gerado ainda. Clique no botão acima para rodar o benchmark.")

with tab_diag:
    st.markdown("### 📊 Análise de Logs & Diagnóstico de Execução")
    render_throttling_alerts_ui()
    
    col_d1, col_d2 = st.columns([1, 3])
    with col_d1:
        if st.button("🔄 Atualizar Análise de Logs", type="secondary", use_container_width=True):
            st.rerun()
            
    stats = analyze_logs()
    th_stats = get_throttling_summary()
    
    if stats.get("status") != "empty":
        m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
        m_c1.metric("Linhas de Log", stats["total_lines"])
        m_c2.metric("Erros Registrados", stats["error_count"], delta=f"-{stats['error_count']}" if stats["error_count"]>0 else "0", delta_color="inverse")
        m_c3.metric("B-rolls Processados", stats.get("brolls_count", 0))
        m_c4.metric("Throttling API (429)", th_stats["api_throttling_hits"])
        m_c5.metric("Throttling Download", th_stats["download_throttling_hits"])
        
        if stats["recommendations"]:
            st.markdown("#### 💡 Recomendações do Sistema:")
            for rec in stats["recommendations"]:
                st.info(f"👉 {rec}")
    
    st.markdown("#### 📜 Logs Persistentes Recentes (`logs/latest.log`)")
    recent_logs = get_recent_ui_logs(limit=40)
    if recent_logs:
        log_text_lines = [f"[{entry['timestamp']}] [{entry['level']}] [{entry['module']}] {entry['message']}" for entry in recent_logs]
        st.code("\n".join(log_text_lines), language="text")
    else:
        st.caption("Nenhum log no buffer de memória ainda.")
