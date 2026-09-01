#!/usr/bin/env python3
"""
CLI de Limpeza de Mídia dos Batches (Reddit Minute)
Uso:
  python scripts/clean_batch_media.py --batch 1     # Limpa apenas o batch 1
  python scripts/clean_batch_media.py --all         # Limpa todos os batches
  python scripts/clean_batch_media.py --generate    # Apenas gera/atualiza os scripts clean_media.py em cada batch
"""
import os
import sys
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.batch_manager import BatchManager

def main():
    parser = argparse.ArgumentParser(description="Limpeza de mídia pesada dos batches do Reddit Minute.")
    parser.add_argument("--batch", type=int, default=None, help="Número do batch a ser limpo (ex: 1, 2, 3)")
    parser.add_argument("--all", action="store_true", help="Limpa a mídia pesada de TODOS os batches")
    parser.add_argument("--generate", action="store_true", help="Gera os scripts clean_media.py dentro de cada pasta de batch")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simula a limpeza sem deletar arquivos")

    args = parser.parse_args()
    mgr = BatchManager()
    mgr.generate_all_batch_cleaners()

    if args.generate:
        print("✅ Scripts de limpeza gerados em todas as pastas de batch.")
        return

    if args.batch is not None:
        deleted, freed = mgr.clean_batch_media(args.batch, dry_run=args.dry_run)
        freed_mb = freed / (1024 * 1024)
        print(f"Batch {args.batch}: {deleted} arquivos removidos, {freed_mb:.1f} MB liberados.")
    elif args.all:
        batches = mgr.list_batches()
        total_deleted = 0
        total_freed = 0
        for b in batches:
            d, f = mgr.clean_batch_media(b, dry_run=args.dry_run)
            total_deleted += d
            total_freed += f
        freed_mb = total_freed / (1024 * 1024)
        freed_gb = freed_mb / 1024
        size_str = f"{freed_gb:.2f} GB" if freed_gb >= 1.0 else f"{freed_mb:.1f} MB"
        print(f"Total de todos os batches: {total_deleted} arquivos removidos, {size_str} liberados.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
