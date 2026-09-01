import os
import sys
import time
import json
import glob
import streamlit as st

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) == "src" else CURRENT_DIR
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Carregar variáveis de ambiente (.env)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

try:
    from .gemini_client import (
        resolve_gemini_api_keys,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key
    )
    from .logger import app_logger, LogSpan
    from .reddit_scraper import (
        HIGH_CPM_SUBREDDITS,
        scrape_subreddit_rss,
        fetch_top_high_cpm_stories
    )
    from .reddit_agents import RedditStoryDirectorAgent, PERSONA_VOICE_MAP, ENGAGEMENT_QUESTIONS
    from .reddit_audio import RedditAudioEngine, REDDIT_PERSONA_VOICES
    from .reddit_visuals import RedditVisualEngine
    from .reddit_pipeline import run_reddit_story_pipeline, generate_teaser_short_video
    from .reddit_longform import generate_25min_single_story_video
    from .batch_manager import BatchManager
    from .checkpoint_manager import DEFAULT_CHECKPOINT_MANAGER, CheckpointManager
except ImportError:
    from gemini_client import (
        resolve_gemini_api_keys,
        DEFAULT_FALLBACK_MODELS,
        resolve_gemini_api_key
    )
    from logger import app_logger, LogSpan
    from reddit_scraper import (
        HIGH_CPM_SUBREDDITS,
        scrape_subreddit_rss,
        fetch_top_high_cpm_stories
    )
    from reddit_agents import RedditStoryDirectorAgent, PERSONA_VOICE_MAP, ENGAGEMENT_QUESTIONS
    from reddit_audio import RedditAudioEngine, REDDIT_PERSONA_VOICES
    from reddit_visuals import RedditVisualEngine
    from reddit_subtitles import generate_reddit_ass_subtitles
    from reddit_render import render_reddit_story_video, find_ffmpeg_binary, get_media_duration, get_orbital_backgrounds
    from reddit_pipeline import run_reddit_story_pipeline, generate_teaser_short_video

    from reddit_longform import generate_25min_single_story_video
    from batch_manager import BatchManager
    from checkpoint_manager import DEFAULT_CHECKPOINT_MANAGER, CheckpointManager

st.set_page_config(
    page_title="Reddit Story Studio - High CPM Video Generator",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização Customizada Dark Theme
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF4500, #FF8700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #B0B3B8;
        margin-bottom: 1.5rem;
    }
    .reddit-badge {
        background-color: #FF4500;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8rem;
    }
    .stProgress > div > div > div > div {
        background-color: #FF4500;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar de Configurações
with st.sidebar:
    st.image("https://www.redditstatic.com/desktop2x/img/favicon/apple-icon-180x180.png", width=60)
    st.markdown("## ⚙️ Configurações do Estúdio")
    
    api_keys_env = resolve_gemini_api_keys()
    primary_val = api_keys_env[0] if len(api_keys_env) > 0 else ""
    fallback_val = api_keys_env[1] if len(api_keys_env) > 1 else ""

    api_key_primary = st.text_input("🔑 Gemini API Key (Principal):", value=primary_val, type="password")
    api_key_fallback = st.text_input("🛡️ Gemini API Key (Fallback):", value=fallback_val, type="password", help="Chave secundária de backup automática.")
    
    if api_key_primary:
        os.environ["GEMINI_API_KEY"] = api_key_primary
    if api_key_fallback:
        os.environ["GEMINI_FALLBACK_API_KEY"] = api_key_fallback

    if api_key_primary and api_key_fallback:
        st.success("🛡️ **Redundância Ativa:** 2 chaves prontas para fallback.")
    elif api_key_primary:
        st.info("ℹ️ Chave primária ativa.")
    else:
        st.warning("⚠️ Modo algorítmico sem API Key (roteirização estruturada ativa).")

    st.markdown("---")
    st.markdown("### 🤖 Modelo Gemini IA")
    model_choice = st.selectbox("Modelo:", options=DEFAULT_FALLBACK_MODELS, index=0)
    auto_fallback = st.checkbox("🔄 Fallback Automático de Modelo", value=True)

    st.markdown("---")
    st.markdown("### 🎮 Backgrounds de Gameplay (1080p60 HD)")
    bg_vert = get_orbital_backgrounds("9:16")
    bg_horiz = get_orbital_backgrounds("16:9")
    st.caption(f"📁 Disponíveis: **{len(bg_vert)} verticais (9:16)** | **{len(bg_horiz)} horizontais (16:9)**")
    
    if st.button("📥 Baixar Novos Backgrounds 1080p60"):
        st.info("Iniciando script de download de backgrounds em 1080p60...")
        subprocess.Popen([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "download_hd_backgrounds.py")])
        st.success("Download iniciado em segundo plano!")

# Cabeçalho Principal
st.markdown('<div class="main-header">🔥 Reddit Story Studio — Alto CPM (Shorts & 25-Min Sagas)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Produção automatizada de vídeos virais do Reddit com Cards Oficiais em alta resolução, gameplay HD 1080p60, narração neural por persona e legendas dinâmicas Hormozi.</div>', unsafe_allow_html=True)

# Tabs Principais
tab_shorts, tab_longform, tab_blacklist, tab_scraper, tab_visuals, tab_voice, tab_gallery = st.tabs([
    "📱 Shorts (até 2.5 min + CTA)",
    "🎬 História Única (25 Minutos)",
    "🛡️ Dual Blacklists",
    "📡 Explorador do Reddit",
    "🎨 Cards do Reddit & Gameplay HD",
    "🎙️ Laboratório de Vozes",
    "📁 Galeria de Masters"
])

# -------------------------------------------------------------
# TAB 1: SHORTS (9:16 - até 2.5 min com CTA de engajamento)
# -------------------------------------------------------------
with tab_shorts:
    st.markdown("### 📱 Produção de Vídeos Curtos (Shorts / Reels / TikTok)")
    st.caption("Gera vídeos verticais 9:16 de até 2.5 minutos com Card Oficial do Reddit, ritmo acelerado e pergunta de engajamento no final.")

    col1, col2 = st.columns([1, 1])
    with col1:
        selected_sub = st.selectbox(
            "Subreddit Alvo:",
            options=["maliciouscompliance", "antiwork", "legaladvice", "AITAH", "pettyrevenge", "tifu", "financialindependence"],
            index=0
        )
        use_custom = st.checkbox("✍️ Inserir História Customizada")

    custom_post_obj = None
    if use_custom:
        cust_title = st.text_input("Título do Post:", value="Boss demanded I follow the handbook to the letter...")
        cust_author = st.text_input("Autor (Reddit):", value="u/OvertimeHero")
        cust_score = st.text_input("Upvotes:", value="34.5k")
        cust_body = st.text_area("Texto Completo da História:", height=180)
        if cust_title and cust_body:
            custom_post_obj = {
                "subreddit": f"r/{selected_sub}",
                "title": cust_title,
                "author": cust_author,
                "score": cust_score,
                "body": cust_body
            }
            is_dup, reason = DEFAULT_CHECKPOINT_MANAGER.is_in_blacklist(custom_post_obj, video_type="shorts")
            if is_dup:
                st.warning(f"⚠️ **Atenção:** Este tema já consta na **Blacklist de Shorts**: {reason}")
            else:
                st.success("✅ **Tema inédito para Shorts!**")

    if st.button("🚀 Gerar Short 9:16 (até 2.5 min)", type="primary", use_container_width=True):
        status_box = st.empty()
        prog_bar = st.progress(0)

        def cb(msg):
            status_box.info(msg)

        try:
            cb("Iniciando pipeline de Shorts...")
            prog_bar.progress(20)
            res = run_reddit_story_pipeline(
                target_subreddit=selected_sub,
                custom_post=custom_post_obj,
                model_name=model_choice,
                export_dual_format=True,
                status_callback=cb
            )
            prog_bar.progress(100)
            status_box.success("🎉 Short gerado com sucesso!")

            if res.get("video_shorts_9x16") and os.path.exists(res.get("video_shorts_9x16")):
                st.video(res["video_shorts_9x16"])
                st.markdown(f"**Pasta:** `{res.get('video_dir')}`")
        except Exception as e:
            status_box.error(f"Erro na produção: {str(e)}")

# -------------------------------------------------------------
# TAB 2: HISTÓRIA ÚNICA DE 25 MINUTOS (16:9)
# -------------------------------------------------------------
with tab_longform:
    st.markdown("### 🎬 Produção de Vídeo Longo (25 Minutos — História Única)")
    st.caption("Desenvolve uma ÚNICA história real em uma saga cinematográfica de 25 minutos dividida em 8 capítulos cronológicos da mesma história com Cards de cada capítulo e timestamps para o YouTube.")

    col_lf1, col_lf2 = st.columns([1, 1])
    with col_lf1:
        lf_sub = st.selectbox(
            "Subreddit da História:",
            options=["maliciouscompliance", "antiwork", "legaladvice", "pettyrevenge", "talesfromtechsupport", "financialindependence"],
            index=0,
            key="lf_sub_select"
        )
        target_mins = st.slider("Duração Alvo (Minutos):", min_value=20.0, max_value=30.0, value=25.0, step=1.0)
        use_custom_lf = st.checkbox("✍️ Inserir História Customizada para Longform", key="use_custom_lf")
    with col_lf2:
        gen_teaser_check = st.checkbox("⚡ Gerar também o Teaser Short 9:16 (com Gancho Final)", value=True)
        st.caption("Cria simultaneamente o clipe vertical promocional com badge '👉 FULL 25-MIN SAGA ON CHANNEL' e CTA de tela.")

    custom_lf_obj = None
    if use_custom_lf:
        cust_lf_title = st.text_input("Título da História Longform:", value="Strict executive banned working from home for IT team...")
        cust_lf_author = st.text_input("Autor (Reddit):", value="u/SysAdminHero", key="cust_lf_author")
        cust_lf_score = st.text_input("Upvotes:", value="36.8k", key="cust_lf_score")
        cust_lf_body = st.text_area("Texto Completo da História:", height=180, key="cust_lf_body")
        if cust_lf_title and cust_lf_body:
            custom_lf_obj = {
                "subreddit": f"r/{lf_sub}",
                "title": cust_lf_title,
                "author": cust_lf_author,
                "score": cust_lf_score,
                "body": cust_lf_body
            }
            is_dup_lf, reason_lf = DEFAULT_CHECKPOINT_MANAGER.is_in_blacklist(custom_lf_obj, video_type="longform")
            if is_dup_lf:
                st.warning(f"⚠️ **Atenção:** Este tema já consta na **Blacklist de Long Videos**: {reason_lf}")
            else:
                st.success("✅ **Tema inédito para Long Videos!**")

    if st.button("🚀 Produzir Vídeo Épico de 25 Minutos (História Única)", type="primary", use_container_width=True):
        status_lf = st.empty()
        prog_lf = st.progress(0)

        def cb_lf(msg):
            status_lf.info(msg)

        try:
            cb_lf(f"Iniciando produção de história única de {target_mins:.0f} minutos...")
            prog_lf.progress(15)
            res_lf = generate_25min_single_story_video(
                target_subreddit=lf_sub,
                custom_post=custom_lf_obj,
                target_duration_minutes=target_mins,
                status_callback=cb_lf
            )
            prog_lf.progress(70)

            res_teaser = None
            if gen_teaser_check:
                cb_lf("⚡ Renderizando Teaser Short 9:16 com Gancho Final...")
                res_teaser = generate_teaser_short_video(
                    story_raw={"title": res_lf.get("title", ""), "subreddit": lf_sub, "body": ""},
                    custom_output_dir=res_lf["work_dir"],
                    teaser_data=res_lf.get("teaser_short_data"),
                    status_callback=cb_lf
                )

            prog_lf.progress(100)
            status_lf.success(f"🎉 Vídeo de {res_lf.get('total_duration_minutes', 25):.1f} minutos gerado com sucesso!")

            if res_teaser and res_teaser.get("teaser_video") and os.path.exists(res_teaser["teaser_video"]):
                v_col1, v_col2 = st.columns([1.6, 1])
                with v_col1:
                    st.markdown("#### 🎬 Master Longform 25 Minutos (16:9)")
                    st.video(res_lf["output_video"])
                    st.caption(f"Pasta: `{res_lf.get('longform_dir')}`")
                with v_col2:
                    st.markdown("#### ⚡ Teaser Short (9:16)")
                    st.video(res_teaser["teaser_video"])
                    st.caption(f"Pasta: `{res_teaser.get('teaser_dir')}`")
            elif res_lf.get("output_video") and os.path.exists(res_lf["output_video"]):
                st.video(res_lf["output_video"])
                st.markdown(f"**Arquivo Master:** `{res_lf['output_video']}`")
                
            if os.path.exists(res_lf.get("metadata_file", "")):
                with open(res_lf["metadata_file"], "r", encoding="utf-8") as f:
                    meta_txt = f.read()
                st.text_area("📋 Metadados e Timestamps do YouTube:", value=meta_txt, height=200)
        except Exception as e:
            status_lf.error(f"Erro na produção do vídeo longo: {str(e)}")

# -------------------------------------------------------------
# TAB 3: DUAL BLACKLISTS (SHORTS & LONG VIDEOS)
# -------------------------------------------------------------
with tab_blacklist:
    st.markdown("### 🛡️ Gestão de Dual Blacklists (Prevenção de Repetição)")
    st.caption("Controle isolado de temas já produzidos para Pure Shorts (9:16) e Long Videos (16:9 / 25-Min Sagas).")

    bl_format = st.radio(
        "Selecione o formato para gerenciar:",
        ["📱 Pure Shorts (blacklist_shorts)", "🎬 Long Videos (blacklist_longform)"],
        horizontal=True
    )
    v_type_selected = "shorts" if "Shorts" in bl_format else "longform"
    items = DEFAULT_CHECKPOINT_MANAGER.load_blacklist(video_type=v_type_selected)
    paths = DEFAULT_CHECKPOINT_MANAGER._get_blacklist_paths(video_type=v_type_selected)

    st.markdown(f"**Arquivo:** `{os.path.relpath(paths[0], PROJECT_ROOT)}` • **Total de Temas Cadastrados:** `{len(items)}`")

    col_bl1, col_bl2 = st.columns([2, 1])
    with col_bl1:
        search_kw = st.text_input("🔍 Pesquisar na blacklist ativa:", placeholder="Ex: boss, overtime, landlord...")
    with col_bl2:
        st.write("")
        st.write("")
        if st.button("🔄 Sincronizar Batches do Disco", use_container_width=True):
            res_sync = DEFAULT_CHECKPOINT_MANAGER.sync_blacklists_from_batches()
            st.success(f"Sincronização concluída! (+{res_sync['shorts_synced']} Shorts, +{res_sync['longform_synced']} Longform)")
            st.rerun()

    # Filtra itens
    if search_kw:
        filtered_items = [it for it in items if search_kw.lower() in it.get("tema", "").lower() or search_kw.lower() in it.get("core_entity", "").lower()]
    else:
        filtered_items = items

    if filtered_items:
        st.markdown(f"#### 📋 Itens Registrados ({len(filtered_items)}):")
        for it in reversed(filtered_items):
            with st.expander(f"📌 [{it.get('batch', 'batch_0')}/{it.get('video', 'video_0')}] {it.get('tema', 'Sem título')}"):
                st.markdown(f"- **Entidade Principal:** `{it.get('core_entity', '-')}`")
                st.markdown(f"- **Data de Registro:** `{it.get('timestamp', '-')}`")
                if it.get("hook"):
                    st.markdown(f"- **Gancho (Hook):** {it.get('hook')}")
    else:
        st.info("Nenhum item registrado nesta blacklist.")

    st.markdown("---")
    st.markdown("#### 🗑️ Exclusão / Limpeza de Temas")
    col_del1, col_del2 = st.columns([3, 1])
    with col_del1:
        del_kw = st.text_input("Palavra-chave a remover da blacklist ativa:", placeholder="Ex: landlord")
    with col_del2:
        st.write("")
        st.write("")
        if st.button("🗑️ Remover da Blacklist", type="secondary", use_container_width=True):
            if del_kw:
                n_rem = DEFAULT_CHECKPOINT_MANAGER.remove_from_blacklist(keyword=del_kw, video_type=v_type_selected)
                st.success(f"{n_rem} item(ns) removido(s) com sucesso!")
                st.rerun()
            else:
                st.warning("Informe uma palavra-chave para remover.")

# -------------------------------------------------------------
# TAB 4: EXPLORADOR DO REDDIT (LIVE SCRAPER)
# -------------------------------------------------------------
with tab_scraper:
    st.markdown("### 📡 Raspador em Tempo Real de Subreddits de Alto CPM")
    scrape_sub = st.selectbox("Escolha o Subreddit:", options=HIGH_CPM_SUBREDDITS, index=0)
    
    if st.button("🔍 Buscar Top Histórias do Mês", use_container_width=True):
        with st.spinner(f"Raspando r/{scrape_sub}..."):
            posts = scrape_subreddit_rss(subreddit=scrape_sub, time_filter="month", limit=8)
            if not posts:
                director = RedditStoryDirectorAgent()
                posts = [director.synthesize_authentic_reddit_post(subreddit=f"r/{scrape_sub}")]


            st.session_state["scraped_posts"] = posts

    if "scraped_posts" in st.session_state:
        for idx, p in enumerate(st.session_state["scraped_posts"]):
            with st.expander(f"📌 [{p.get('score', '20k')}] {p.get('title')}"):
                st.markdown(f"**Autor:** `{p.get('author')}` • **Subreddit:** `{p.get('subreddit')}`")
                st.write(p.get("body", "")[:600] + "...")
                st.markdown(f"[Ver post original]({p.get('url', '#')})")

# -------------------------------------------------------------
# TAB 5: CARDS DO REDDIT & GAMEPLAY HD
# -------------------------------------------------------------
with tab_visuals:
    st.markdown("### 🎨 Pré-visualização de Cards Oficiais do Reddit")
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        card_channel = st.text_input("Nome do Canal:", value="Reddit Minute")
        card_icon = st.text_input("Caminho do Ícone:", value=r"C:\Users\Aluno\Downloads\icon.jpg")
        card_sc = st.text_input("Score (Upvotes):", value="42.8k")
        card_tit = st.text_input("Título do Card:", value="Boss told me to strictly follow protocol. It cost them $42k.")
        card_aspect = st.selectbox("Proporção:", ["9:16 (Shorts)", "16:9 (Long-form)"])

    ve = RedditVisualEngine()
    ratio_str = "9:16" if "9:16" in card_aspect else "16:9"
    preview_png = os.path.join(PROJECT_ROOT, "checkpoint", f"preview_card_{ratio_str.replace(':', 'x')}.png")
    
    card_data = {
        "channel_name": card_channel,
        "icon_path": card_icon,
        "score": card_sc,
        "display_title": card_tit
    }
    ve.render_reddit_card(card_data, preview_png, aspect_ratio=ratio_str)
    
    with col_c2:
        st.markdown("**Pré-visualização do Card em Alta Resolução (Dark Theme):**")
        st.image(preview_png, width=380 if ratio_str == "9:16" else 550)

    st.markdown("---")
    st.markdown("### 🎮 Biblioteca de Gameplay 1080p60 HD")
    bg_files = glob.glob(os.path.join(PROJECT_ROOT, "assets", "backgrounds", "*.mp4"))
    if bg_files:
        for bf in bg_files:
            sz = os.path.getsize(bf) / (1024 * 1024)
            st.markdown(f"- 🎮 `{os.path.basename(bf)}` — **{sz:.1f} MB**")
    else:
        st.warning("Nenhum vídeo em assets/backgrounds. Clique em 'Baixar Novos Backgrounds' na barra lateral.")

# -------------------------------------------------------------
# TAB 6: LABORATÓRIO DE VOZES
# -------------------------------------------------------------
with tab_voice:
    st.markdown("### 🎙️ Teste de Personas Vocais Neurais")
    test_persona = st.selectbox("Persona Vocal:", list(REDDIT_PERSONA_VOICES.keys()))
    test_voice = REDDIT_PERSONA_VOICES[test_persona]
    test_text = st.text_area(
        "Texto para teste:",
        value="My boss told me that if I touched the valve without his written permission, I would be fired. So I let the entire plant shut down."
    )
    if st.button("🔊 Sintetizar Voz de Teste"):
        with st.spinner("Sintetizando..."):
            audio_eng = RedditAudioEngine(voice=test_voice, rate="+20%")
            test_mp3 = os.path.join(PROJECT_ROOT, "checkpoint", "test_persona.mp3")
            audio_eng.generate_speech(test_text, test_mp3, voice_name=test_voice)
            if os.path.exists(test_mp3):
                st.audio(test_mp3)

# -------------------------------------------------------------
# TAB 7: GALERIA DE MASTERS & BATCHES
# -------------------------------------------------------------
with tab_gallery:
    st.markdown("### 📁 Galeria de Lotes (batch_1, batch_2...) & Vídeos")
    
    # Resumo dos Batches Organizados
    bm = BatchManager(base_dir=os.path.join(PROJECT_ROOT, "checkpoint", "auto_batches"))
    summary = bm.get_summary()
    if summary:
        st.markdown("#### 📊 Status dos Lotes Ativos:")
        cols = st.columns(min(max(len(summary), 1), 4))
        for idx, b_info in enumerate(summary):
            with cols[idx % len(cols)]:
                status_lbl = "Completo (10/10)" if b_info["is_full"] else f"{b_info['video_count']}/10 vídeos"
                st.metric(
                    label=f"📁 {b_info['batch_name']}",
                    value=status_lbl,
                    delta="Cheio" if b_info["is_full"] else f"{10 - b_info['video_count']} vagas"
                )
        st.markdown("---")

    rendered_videos = glob.glob(os.path.join(PROJECT_ROOT, "checkpoint", "**", "*.mp4"), recursive=True)
    if rendered_videos:
        for vid in rendered_videos:
            if "chapter" not in os.path.basename(vid) and "part_" not in os.path.basename(vid) and "test" not in os.path.basename(vid):
                rel_path = os.path.relpath(vid, PROJECT_ROOT)
                st.markdown(f"#### 🎬 `{rel_path}`")
                st.caption(f"Arquivo: `{vid}`")
                st.video(vid)
                st.markdown("---")
    else:
        st.info("Nenhum vídeo master finalizado encontrado no diretório `checkpoint/`.")
