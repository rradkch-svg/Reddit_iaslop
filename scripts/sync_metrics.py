"""
Script de Sincronização de Métricas do YouTube & Memória Algorítmica.
Lê o arquivo METRICAS_VIDEOS.csv (ou METRICAS_VIDEOS.md) na raiz do projeto,
ingere as visualizações e retenções informadas pelo criador de conteúdo,
preserva os metadados dos pesos da IA que concebeu o enredo daquele vídeo específico,
desconsidera por segurança vídeos com metadados perdidos, e recalibra a convergência algorítmica.

Uso:
    python scripts/sync_metrics.py
    python scripts/sync_metrics.py --export-only
    python scripts/sync_metrics.py --scan-checkpoints
"""

import os
import sys
import argparse

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
    print("🧠 AI SLOP STUDIO - SINCRONIZADOR DE MÉTRICAS & BIG DATA (.CSV / .MD)")
    print("=" * 75)

def main():
    show_banner()
    parser = argparse.ArgumentParser(description="Sincronizador de Métricas de Vídeos e Memória Algorítmica")
    parser.add_argument("--scan-checkpoints", action="store_true", help="Varre a pasta de checkpoints e atualiza a base")
    parser.add_argument("--export-only", action="store_true", help="Apenas regera os templates METRICAS_VIDEOS.csv e .md")
    parser.add_argument("--zip", type=str, default=None, help="Caminho explícito para arquivo .zip do YouTube Analytics")
    parser.add_argument("--csv", type=str, default=None, help="Caminho alternativo para o arquivo CSV de métricas")
    args = parser.parse_args()

    memory_sys = DEFAULT_ALGORITHM_MEMORY
    analytics_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "analytics"))
    csv_file = os.path.abspath(args.csv or os.path.join(PROJECT_ROOT, "METRICAS_VIDEOS.csv"))
    md_file = os.path.abspath(os.path.join(PROJECT_ROOT, "METRICAS_VIDEOS.md"))

    print(f"📁 Diretório Raiz     : {PROJECT_ROOT}")
    print(f"📦 Pasta /analytics   : {analytics_dir}")
    print(f"📄 Arquivo CSV        : {csv_file}")
    print(f"📄 Arquivo MD         : {md_file}")
    print()

    # 1. Varredura e sincronização de checkpoints existentes
    print("🔍 [1/3] Varrendo checkpoints e preservando metadados de pesos da IA...")
    val_cnt, ign_cnt = memory_sys.scan_and_sync_checkpoints()
    print(f"  ✅ {val_cnt} vídeos válidos com metadados preservados.")
    if ign_cnt > 0:
        print(f"  ⚠️ {ign_cnt} vídeos com metadata perdido/corrompido desconsiderados por segurança.")

    if args.export_only:
        print("\n✨ Arquivos de métricas exportados com sucesso na raiz!")
        return

    # 2. Ingestão prioritária do arquivo .zip do YouTube Analytics em /analytics
    from analytics_parser import DEFAULT_ANALYTICS_PARSER
    target_zip = args.zip or DEFAULT_ANALYTICS_PARSER.find_latest_zip()
    
    if target_zip and os.path.exists(target_zip):
        print(f"\n📦 [2/3] Detectado pacote de exportação do YouTube Analytics: {os.path.basename(target_zip)}")
        print("  ⚡ Extraindo métricas (Visualizações, Retenção, APV, CTR, Inscritos, Duração)...")
        upd_cnt, ign_cnt, msgs = memory_sys.ingest_from_analytics_zip(target_zip)
        for m in msgs:
            print(f"  • {m}")
        print(f"\n  📊 Total de vídeos sincronizados do YouTube: {upd_cnt}")
    else:
        # Fallback para importação manual de CSV caso não haja ZIP
        print("\n📥 [2/3] Nenhum .zip encontrado em /analytics. Processando dados de METRICAS_VIDEOS.csv...")
        upd_cnt, ign_csv, msgs = memory_sys.import_metrics_csv(csv_file)
        for m in msgs:
            print(f"  • {m}")
        print(f"\n  📊 Total de vídeos com métricas processadas via CSV: {upd_cnt}")

    # 3. Exibição do resumo de inteligência algorítmica
    print("\n🎯 [3/3] Vetor de Pesos Auxiliares Calibrado:")
    weights = memory_sys.load_weights()
    for k, v in weights.items():
        print(f"  • {k:<30} : {v}")

    print("\n" + "=" * 75)
    print("🎉 Sincronização concluída com sucesso!")
    print(f"📦 Para atualizar no futuro, basta soltar o novo .zip exportado do YouTube em '{analytics_dir}'")
    print(f"📄 Consulte 'METRICAS_VIDEOS.md' e 'data/algorithm_memory/ALGORITHM_MEMORY.md' para ver o aprendizado da IA.")
    print("=" * 75)

if __name__ == "__main__":
    main()
