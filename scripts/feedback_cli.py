"""
Script CLI para Ingestão de Feedback Analítico e Inspeção da Memória Algorítmica (.md).
Permite ao criador de conteúdo inserir as métricas reais retornadas pelo YouTube Shorts
(Visualizações, Retenção aos 3s %, APV %, CTR %, Likes, Comentários) para calibrar os pesos
auxiliares e orientar a IA na geração de novos conteúdos de alta retenção sem repetir temas.

Uso:
    python scripts/feedback_cli.py --list
    python scripts/feedback_cli.py --input batch_1/video_0 --views 45000 --retention 78.5 --apv 88.0 --ctr 11.2 --notes "Excelente engajamento no motor V12"
    python scripts/feedback_cli.py --memory
    python scripts/feedback_cli.py --weights
"""

import os
import sys
import argparse
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR) if os.path.basename(CURRENT_DIR) in ("src", "scripts") else CURRENT_DIR
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

from algorithm_memory import AlgorithmMemorySystem, DEFAULT_ALGORITHM_MEMORY

def show_banner():
    print("=" * 75)
    print("🧠 AI SLOP STUDIO - SISTEMA DE FEEDBACK & MEMÓRIA ALGORÍTMICA (.MD)")
    print("=" * 75)

def list_videos(memory_sys: AlgorithmMemorySystem):
    history = memory_sys.load_history()
    print(f"\n📋 VÍDEOS REGISTRADOS NA MEMÓRIA ({len(history)} total):\n")
    if not history:
        print("  (Nenhum vídeo registrado ainda no histórico de analytics)")
        return

    print(f"{'#':<4} {'IDENTIFICADOR':<18} {'TIER':<8} {'VIEWS':<10} {'RET. 3s':<10} {'APV %':<10} {'TEMA':<35}")
    print("-" * 95)
    for idx, r in enumerate(history, 1):
        an = r.get("analytics", {})
        bv = f"{r.get('batch')}/v{r.get('video_index')}"
        tier = an.get("performance_tier", "PENDING")
        views = f"{an.get('views', 0):,}" if an.get('views') is not None else "-"
        ret_3s = f"{an.get('retention_3s_pct'):.1f}%" if an.get('retention_3s_pct') is not None else "-"
        apv = f"{an.get('apv_pct'):.1f}%" if an.get('apv_pct') is not None else "-"
        tema = r.get("tema", "")[:33]
        print(f"{idx:<4} {bv:<18} {tier:<8} {views:<10} {ret_3s:<10} {apv:<10} {tema:<35}")
    print()

def show_weights(memory_sys: AlgorithmMemorySystem):
    weights = memory_sys.load_weights()
    print("\n🎯 VETOR DE PESOS AUXILIARES ATIVOS (CALIBRAÇÃO DO ALGORITMO):\n")
    for k, v in weights.items():
        print(f"  • {k:<32} : {v}")
    print()

def show_memory_markdown(memory_sys: AlgorithmMemorySystem):
    md_path = memory_sys.memory_md_file
    print(f"\n📄 CONTEÚDO DO ARQUIVO DE MEMÓRIA: {md_path}\n")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("  (Arquivo ALGORITHM_MEMORY.md ainda não foi gerado)")

def main():
    show_banner()
    parser = argparse.ArgumentParser(description="Gestão de Feedback Analítico e Memória Algorítmica")
    parser.add_argument("--list", action="store_true", help="Lista todos os vídeos registrados e suas métricas")
    parser.add_argument("--weights", action="store_true", help="Exibe os pesos auxiliares ativos")
    parser.add_argument("--memory", action="store_true", help="Exibe o arquivo ALGORITHM_MEMORY.md completo")
    parser.add_argument("--input", type=str, help="Identificador do vídeo (ex: batch_1/video_0 ou vid_123)")
    parser.add_argument("--views", type=int, default=0, help="Número total de visualizações obtidas no YouTube Shorts")
    parser.add_argument("--retention", type=float, default=None, help="Retenção nos primeiros 3 segundos (% do gancho)")
    parser.add_argument("--apv", type=float, default=None, help="Average Percentage Viewed / Retenção Média (%)")
    parser.add_argument("--ctr", type=float, default=None, help="Taxa de Cliques no Feed de Shorts (%)")
    parser.add_argument("--likes", type=int, default=0, help="Total de curtidas")
    parser.add_argument("--comments", type=int, default=0, help="Total de comentários")
    parser.add_argument("--shares", type=int, default=0, help="Total de compartilhamentos")
    parser.add_argument("--notes", type=str, default="", help="Observações qualitativas sobre o desempenho")

    args = parser.parse_args()
    memory_sys = DEFAULT_ALGORITHM_MEMORY

    if args.input:
        print(f"📥 Processando feedback analítico para '{args.input}'...")
        ok, msg, record = memory_sys.ingest_analytics_feedback(
            identifier=args.input,
            views=args.views,
            retention_3s_pct=args.retention,
            apv_pct=args.apv,
            ctr_pct=args.ctr,
            likes=args.likes,
            comments=args.comments,
            shares=args.shares,
            feedback_notes=args.notes
        )
        if ok:
            print(f"✅ {msg}")
            print(f"📊 Memória .md e pesos auxiliares sincronizados com sucesso!")
        else:
            print(f"❌ {msg}")
        return

    if args.list:
        list_videos(memory_sys)
        return

    if args.weights:
        show_weights(memory_sys)
        return

    if args.memory:
        show_memory_markdown(memory_sys)
        return

    # Se nenhum argumento for passado, exibe o menu interativo rápido
    print("\nModo Interativo Rápido:")
    list_videos(memory_sys)
    show_weights(memory_sys)
    print("Para registrar métricas de um vídeo, use:")
    print("  python scripts/feedback_cli.py --input batch_1/video_0 --views 50000 --retention 76.5 --apv 85.0 --notes \"Ótimo gancho\"")

if __name__ == "__main__":
    main()
