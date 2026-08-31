import os
import sys
import time
import json
import wave
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Configuração de caminhos
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from agents import resolve_gemini_api_keys

# Texto padronizado de alta densidade técnica automotiva para benchmark comparativo
BENCHMARK_TEXT_RAW = (
    "Por que o motor V10 do Lexus LFA gira tão rápido que a física quase não acompanha? "
    "A Yamaha e a Lexus gastaram dez anos para criar o lendário 1LR-GUE de 4.8 litros. "
    "Ele atinge 9.000 RPM em apenas 0.6 segundos, usando válvulas de titânio e bielas forjadas ultraleves. "
    "O som do escapamento foi afinado acusticamente como um instrumento musical de Fórmula 1. "
    "Mas me diz nos comentários: você prefere a sinfonia desse V10 aspirado ou o torque bruto de um Porsche Twin-Turbo?"
)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "testes-tts")

def pcm_to_mp3(pcm_bytes: bytes, sample_rate: int, output_path: str):
    """Converte bytes PCM 16-bit mono brutos em MP3 192k."""
    temp_wav = output_path.replace(".mp3", "_temp.wav")
    with wave.open(temp_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

    cmd = [
        "ffmpeg", "-y", "-i", temp_wav,
        "-codec:a", "libmp3lame", "-b:a", "192k",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if os.path.exists(temp_wav):
        try:
            os.remove(temp_wav)
        except:
            pass

def generate_gemini_tts_with_rotation(
    voice_name: str,
    output_file: str,
    text: str,
    style_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """Gera áudio com Google Gemini 2.5 Flash TTS com rotação automática de chaves e cooldown inteligente."""
    from google import genai
    from google.genai import types

    keys = resolve_gemini_api_keys()
    if not keys:
        raise ValueError("Nenhuma chave GEMINI_API_KEY encontrada no arquivo .env!")

    t0 = time.time()
    
    if style_prompt:
        instruction = f"{style_prompt}\n\nLeia exatamente o texto a seguir em português do Brasil sem alterar as palavras:\n{text}"
    else:
        instruction = f"Você é um narrador profissional de documentários automotivos. Leia o seguinte texto em português com entonação humana ultra natural:\n\n{text}"

    max_attempts = 5
    for attempt in range(max_attempts):
        for k_idx, key in enumerate(keys):
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts",
                    contents=instruction,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                            )
                        )
                    )
                )
                audio_part = response.candidates[0].content.parts[0]
                raw_pcm = audio_part.inline_data.data
                elapsed = time.time() - t0

                pcm_to_mp3(raw_pcm, sample_rate=24000, output_path=output_file)
                
                return {
                    "engine": "Google Gemini 2.5 Flash Generative TTS",
                    "voice": f"Gemini {voice_name}",
                    "voice_type": "Multimodal Neural Generative (AI Speech)",
                    "sample_rate": "24.0 kHz Studio",
                    "latency_sec": round(elapsed, 2),
                    "file": os.path.basename(output_file),
                    "style": style_prompt or "Padrão de Documentário de Alta Naturalidade"
                }
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    print(f"    ⚠️ Cota na chave #{k_idx+1}. Tentando próxima...")
                    continue
                else:
                    raise e
        
        wait_time = 25
        print(f"    ⏳ Todas as chaves em cooldown. Aguardando {wait_time}s para liberação de cota (Tentativa {attempt+1}/{max_attempts})...")
        time.sleep(wait_time)

    raise Exception("Falha após esgotar tentativas de cooldown no Gemini TTS.")

def run_gemini_exclusive_benchmark():
    """Apaga toda a pasta testes-tts e gera uma galeria exclusiva com todas as possibilidades do Gemini."""
    if os.path.exists(OUTPUT_DIR):
        print(f"🧹 Limpando diretório anterior: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 80)
    print("🌟 AI SLOP STUDIO - LABORATÓRIO EXCLUSIVO GOOGLE GEMINI NEURAL TTS")
    print("=" * 80)
    print(f"📁 Diretório de Saída : {OUTPUT_DIR}")
    print(f"📄 Texto de Teste     : {BENCHMARK_TEXT_RAW[:80]}...\n")

    # Matriz Completa de Variações do Gemini (Vozes Predefinidas + Perfis de Entonação)
    gemini_configs = [
        # --- VOZES PRINCIPAIS BASE ---
        ("Puck", "01_gemini_puck_natural.mp3", None, "Puck (Voz Masculina Jovem & Dinâmica - Padrão)"),
        ("Charon", "02_gemini_charon_natural.mp3", None, "Charon (Voz Masculina Grave & Cinematográfica - Padrão)"),
        ("Kore", "03_gemini_kore_natural.mp3", None, "Kore (Voz Feminina Cristalina & Envolvente - Padrão)"),
        ("Fenrir", "04_gemini_fenrir_natural.mp3", None, "Fenrir (Voz Masculina Encorpada & Vigorosa - Padrão)"),
        ("Aoede", "05_gemini_aoede_natural.mp3", None, "Aoede (Voz Feminina Suave & Melódica - Padrão)"),
        
        # --- PERFIS DE ESTILO DE LOCUÇÃO & ATUAÇÃO ---
        ("Puck", "06_gemini_puck_shorts_adrenalina.mp3", 
         "Você é um criador de conteúdo jovem, hipnótico e enérgico para YouTube Shorts. Fale em ritmo acelerado e entusiasmado nos primeiros segundos para prender a atenção total.", 
         "Puck — Preset Shorts & Adrenalina (Ritmo Acelerado 1.25x)"),
         
        ("Charon", "07_gemini_charon_documentario_epico.mp3", 
         "Você é um narrador de documentário automotivo de prestígio internacional (estilo BBC Top Gear). Use tom solene, autoritário, com pausas dramáticas de respiração.", 
         "Charon — Preset Documentário Épico / BBC (Grave & Solene)"),
         
        ("Fenrir", "08_gemini_fenrir_entusiasta_ronco.mp3", 
         "Você é um apaixonado por supercarros e velocidade. Fale com pura emoção e ênfase visceral na cavalaria, nas 9.000 RPM e no som do escape.", 
         "Fenrir — Preset Entusiasta de Pista (Ênfase Visceral)"),
         
        ("Kore", "09_gemini_kore_engenharia_precisa.mp3", 
         "Você é uma engenheira mecânica de precisão. Explique cada detalhe termodinâmico com clareza cristalina, elegância e ritmo firme.", 
         "Kore — Preset Engenharia de Precisão (Clara & Didática)")
    ]

    results = []
    for idx, (v_name, filename, style_prompt, desc) in enumerate(gemini_configs, 1):
        out_path = os.path.join(OUTPUT_DIR, filename)
        print(f"[{idx}/{len(gemini_configs)}] Sintetizando '{desc}'...", flush=True)
        try:
            info = generate_gemini_tts_with_rotation(v_name, out_path, BENCHMARK_TEXT_RAW, style_prompt)
            info["description"] = desc
            results.append(info)
            print(f"  ✅ Concluído em {info['latency_sec']}s -> {filename}", flush=True)
        except Exception as e:
            print(f"  ❌ Erro ao sintetizar {desc}: {str(e)}", flush=True)
        # Pausa de cadência para respeitar o teto de 10 requisições/minuto da cota gratuita
        if idx < len(gemini_configs):
            time.sleep(6.5)

    # Salva metadata JSON
    meta_json_path = os.path.join(OUTPUT_DIR, "metadata_benchmarks.json")
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "text": BENCHMARK_TEXT_RAW,
            "engine": "Google Gemini 2.5 Flash Multimodal Generative TTS",
            "total_options": len(results),
            "options": results
        }, f, indent=2, ensure_ascii=False)

    # Gera documentação Markdown
    generate_gemini_markdown_report(results)
    # Gera player HTML visual
    generate_gemini_html_player(results)

    print("\n" + "=" * 80)
    print(f"🎉 LABORATÓRIO GEMINI CONCLUÍDO! ({len(results)} alternativas geradas)")
    print(f"📂 Diretório exclusivo: {OUTPUT_DIR}")
    print(f"🌐 Abra '{os.path.join(OUTPUT_DIR, 'index.html')}' no seu navegador para ouvir todas lado a lado!")
    print("=" * 80)

def generate_gemini_markdown_report(results: List[Dict[str, Any]]):
    """Cria README.md no diretório testes-tts com a análise de todas as vozes do Gemini."""
    md_path = os.path.join(OUTPUT_DIR, "README.md")
    
    md_content = f"""# 🎙️ Laboratório Exclusivo Google Gemini Generative TTS
*Gerado em: {time.strftime('%Y-%m-%d %H:%M:%S')} | Total de Alternativas Gemini: {len(results)}*

Este diretório contém amostras de áudio geradas **exclusivamente com o motor generativo multimodal Google Gemini 2.5 Flash TTS**, explorando todas as vozes fundamentais da arquitetura e variações de estilo/prosódia para documentários automotivos.

---

## 📄 Texto Padronizado Utilizado no Teste

> "{BENCHMARK_TEXT_RAW}"

---

## 📊 Matriz das Vozes & Estilos do Google Gemini

| # | Arquivo de Áudio | Voz Gemini | Perfil / Atuação | Latência | Características Principais |
| :-: | :--- | :--- | :--- | :---: | :--- |
"""
    for idx, r in enumerate(results, 1):
        md_content += (
            f"| {idx:02d} | [`{r['file']}`]({r['file']}) | **{r['voice']}** | "
            f"`{r['description']}` | `{r['latency_sec']}s` | {r.get('style', '')} |\n"
        )

    md_content += f"""
---

## 🔬 Análise das Vozes do Google Gemini

### 1. 🏆 As 5 Vozes Fundamentais da Arquitetura Gemini
- **`Puck` (Masculino Jovem):** Tom dinâmico, ágil e altamente natural. É a voz mais adequada para o público de Shorts, Reels e TikTok, com dicção viva e sem cansaço.
- **`Charon` (Masculino Grave):** Tom profundo, autoritário e cinematográfico. Excelente para criar a sensação de documentário de alta produção (estilo Discovery/BBC).
- **`Fenrir` (Masculino Robusto):** Voz forte, encorpada e de impacto, perfeita para supercarros com motores V8/V10 e corridas.
- **`Kore` (Feminina Cristalina):** Dicção impecável, elegante e envolvente para explicar a física e engenharia sem parecer artificial.
- **`Aoede` (Feminina Suave):** Cadência melódica e calma.

### 2. 🎭 Por que o Gemini Supera Sintetizadores Convencionais?
Diferente de sistemas convencionais de TTS (que apenas leem fonemas sem entender o texto), o **Google Gemini compreende o contexto semântico** antes de emitir a onda sonora. Ele identifica onde está o gancho, onde estão os números de telemetria (*"9.000 RPM", "4.8 litros"*) e adiciona respirações humanas reais e ênfase vocal nos momentos de clímax.

---

## 🎧 Como Ouvir Todas as Amostras
Basta abrir o arquivo [`index.html`](index.html) diretamente no seu navegador para ter o comparador visual em Dark Mode com todos os reprodutores lado a lado.
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

def generate_gemini_html_player(results: List[Dict[str, Any]]):
    """Gera um player de áudio HTML5 moderno exclusivo para as vozes do Gemini."""
    html_path = os.path.join(OUTPUT_DIR, "index.html")

    cards_html = ""
    for idx, r in enumerate(results, 1):
        cards_html += f"""
        <div class="card">
            <div class="card-header">
                <div class="card-title">
                    <span class="badge-idx">#{idx:02d}</span>
                    <span class="title-text">{r['description']}</span>
                </div>
                <span class="badge-engine">
                    Google Gemini 2.5 Flash
                </span>
            </div>
            <div class="card-body">
                <div class="meta-row">
                    <span><strong>Voz Base:</strong> <code>{r['voice']}</code></span>
                    <span><strong>Fidelidade:</strong> 24.0 kHz Studio</span>
                    <span><strong>Latência:</strong> {r['latency_sec']}s</span>
                </div>
                <p class="desc-text">{r.get('style', '')}</p>
                <div class="audio-container">
                    <audio controls preload="metadata">
                        <source src="{r['file']}" type="audio/mpeg">
                        Seu navegador não suporta áudio HTML5.
                    </audio>
                </div>
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌟 Laboratório Google Gemini Generative TTS</title>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #151c2d;
            --border-color: #26334d;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #8b5cf6;
            --accent-glow: rgba(139, 92, 246, 0.2);
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 2.5rem 1.5rem;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 2.5rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
        }}
        h1 {{
            font-size: 2.3rem;
            font-weight: 800;
            background: linear-gradient(135deg, #a78bfa, #c084fc, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.8rem;
        }}
        .subtitle {{
            color: var(--text-muted);
            font-size: 1.05rem;
            max-width: 800px;
            margin: 0 auto;
        }}
        .script-box {{
            background: rgba(21, 28, 45, 0.8);
            border: 1px solid var(--border-color);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 1.2rem 1.5rem;
            margin-bottom: 2.5rem;
        }}
        .script-title {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #a78bfa;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        .script-content {{
            font-size: 0.98rem;
            color: #e2e8f0;
            font-style: italic;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(540px, 1fr));
            gap: 1.5rem;
        }}
        @media (max-width: 768px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        }}
        .card:hover {{
            transform: translateY(-2px);
            border-color: #3b4d75;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .card-header {{
            padding: 1.2rem 1.2rem 0.8rem 1.2rem;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 1rem;
        }}
        .card-title {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }}
        .badge-idx {{
            font-weight: 800;
            font-size: 0.85rem;
            background: #0b0f19;
            color: #a78bfa;
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}
        .title-text {{
            font-size: 1.05rem;
            font-weight: 700;
            color: #f1f5f9;
        }}
        .badge-engine {{
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.25rem 0.6rem;
            border-radius: 20px;
            background-color: rgba(139, 92, 246, 0.15);
            color: #c084fc;
            border: 1px solid rgba(139, 92, 246, 0.3);
            white-space: nowrap;
        }}
        .card-body {{
            padding: 0 1.2rem 1.2rem 1.2rem;
        }}
        .meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-bottom: 0.6rem;
            padding-bottom: 0.6rem;
            border-bottom: 1px solid rgba(38, 51, 77, 0.5);
        }}
        .meta-row code {{
            background: #0b0f19;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            color: #cbd5e1;
        }}
        .desc-text {{
            font-size: 0.88rem;
            color: #94a3b8;
            margin-bottom: 1rem;
            min-height: 2.6em;
        }}
        .audio-container {{
            background: #0b0f19;
            padding: 0.6rem;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}
        audio {{
            width: 100%;
            height: 38px;
            filter: invert(0.9) hue-rotate(240deg);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌟 Laboratório Google Gemini Generative TTS</h1>
            <p class="subtitle">
                Galeria exclusiva contendo todas as vozes neurais e estilos de atuação gerados pelo Google Gemini 2.5 Flash.
            </p>
        </header>

        <div class="script-box">
            <div class="script-title">Texto Padronizado de Teste (Mecânica Pura & Telemetria)</div>
            <div class="script-content">"{BENCHMARK_TEXT_RAW}"</div>
        </div>

        <div class="grid">
            {cards_html}
        </div>
    </div>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    run_gemini_exclusive_benchmark()
