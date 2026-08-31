"""
Módulo de Inteligência Algorítmica, Big Data e Memória de Feedback (.md).
Rastreia a anatomia completa de todos os conteúdos produzidos, processa métricas de analytics
(visualizações, retenção aos 3s, APV %, CTR %, engajamento), realiza atribuição causal de sucesso
e atualiza pesos auxiliares dinâmicos para convergir na fórmula viral sem repetir temas.
"""

import os
import json
import time
import math
from typing import Dict, List, Any, Optional, Tuple

try:
    from .logger import app_logger, LogSpan
    from .deduplication import sanitize_and_cap_title, extract_canonical_entity
    from .analytics_parser import DEFAULT_ANALYTICS_PARSER, YouTubeAnalyticsZipParser, ANALYTICS_DIR
except ImportError:
    from logger import app_logger, LogSpan
    from deduplication import sanitize_and_cap_title, extract_canonical_entity
    from analytics_parser import DEFAULT_ANALYTICS_PARSER, YouTubeAnalyticsZipParser, ANALYTICS_DIR

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(PROJECT_ROOT, "data", "algorithm_memory")

# Pesos auxiliares padrão calibrados para retenção máxima em Shorts de 60s a 120s
DEFAULT_AUXILIARY_WEIGHTS: Dict[str, float] = {
    "hook_curiosity_gap_weight": 0.95,      # Intensidade do gancho nos primeiros 3s (paradoxo/dado chocante)
    "technical_depth_weight": 0.92,         # Nível de profundidade e exatidão mecânica (vs termos genéricos)
    "anti_hype_precision_weight": 0.90,     # Penalização severa de palavras de efeito vazias e buzzwords
    "visceral_sound_focus_weight": 0.88,    # Foco em termos sonoros e busca de B-roll com pure sound/exhaust
    "telemetry_density_weight": 0.85,       # Presença de dados concretos (rpm, cv, kgfm, segundos, 0-100)
    "pacing_cadence_wpm": 185.0,            # Palavras por minuto ideais (ritmo 1.25x acelerado)
    "broll_cut_frequency_sec": 2.8,         # Tempo médio entre tomadas de corte (em segundos)
    "conflict_and_triumph_weight": 0.80,    # Presença do desafio de engenharia superado pela fabricante
    "comment_trigger_weight": 0.85          # Eficácia da pergunta final para provocar debate nos comentários
}

class AlgorithmMemorySystem:
    """
    Sistema Central de Memória Algorítmica e Inteligência de Conteúdo.
    Persiste dados analíticos em JSON e compila a memória analítica em ALGORITHM_MEMORY.md.
    """

    def __init__(self, memory_dir: Optional[str] = None, data_dir: Optional[str] = None, root_dir: Optional[str] = None):
        target_dir = memory_dir or data_dir or root_dir or MEMORY_DIR
        self.memory_dir = os.path.abspath(target_dir)
        os.makedirs(self.memory_dir, exist_ok=True)
        
        self.weights_file = os.path.join(self.memory_dir, "auxiliary_weights.json")
        self.history_file = os.path.join(self.memory_dir, "analytics_history.json")
        self.memory_md_file = os.path.join(self.memory_dir, "ALGORITHM_MEMORY.md")
        
        self._init_files_if_needed()

    def _init_files_if_needed(self):
        """Inicializa os arquivos de persistência caso ainda não existam."""
        if not os.path.exists(self.weights_file):
            self.save_weights(DEFAULT_AUXILIARY_WEIGHTS)

        if not os.path.exists(self.history_file):
            initial_history = {
                "version": 1,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_records": 0,
                "records": []
            }
            self._save_json_atomic(self.history_file, initial_history)

        if not os.path.exists(self.memory_md_file):
            self._regenerate_markdown_memory()

    def _save_json_atomic(self, file_path: str, data: Any):
        """Salva arquivo JSON atomicamente com arquivo temporário."""
        tmp = f"{file_path}.tmp.{time.time()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, file_path)

    def load_weights(self) -> Dict[str, float]:
        """Carrega os pesos auxiliares ativos."""
        try:
            if os.path.exists(self.weights_file):
                with open(self.weights_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {k: float(v) for k, v in data.items()}
        except Exception as e:
            app_logger.warning(f"[AlgorithmMemory] Erro ao ler auxiliary_weights.json: {str(e)}")
        return dict(DEFAULT_AUXILIARY_WEIGHTS)

    def save_weights(self, weights: Dict[str, float]):
        """Salva os pesos auxiliares atualizados."""
        self._save_json_atomic(self.weights_file, weights)
        app_logger.info(f"[AlgorithmMemory] Pesos auxiliares salvos: {self.weights_file}")

    def load_history(self) -> List[Dict[str, Any]]:
        """Carrega o histórico completo de vídeos e métricas."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("records", [])
        except Exception as e:
            app_logger.warning(f"[AlgorithmMemory] Erro ao ler analytics_history.json: {str(e)}")
        return []

    def record_video_generation(self, video_payload: Dict[str, Any]) -> str:
        """
        Registra a anatomia completa de um novo vídeo gerado para futuro acompanhamento analítico.
        """
        history_data = self.load_history()
        video_id = video_payload.get("video_id") or f"vid_{int(time.time()*1000)}"
        
        # Cria ou atualiza registro
        existing_idx = next((i for i, r in enumerate(history_data) if r.get("video_id") == video_id), None)
        
        raw_tema = video_payload.get("tema", "")
        clean_tema = sanitize_and_cap_title(raw_tema, max_length=100)
        
        entry = {
            "video_id": video_id,
            "batch": video_payload.get("batch", "batch_0"),
            "video_index": video_payload.get("video_index", 0),
            "tema": clean_tema,
            "core_entity": video_payload.get("core_entity") or extract_canonical_entity(clean_tema),
            "hook": video_payload.get("hook", ""),
            "dissertacao_resumo": video_payload.get("dissertacao_resumo", ""),
            "duracao_segundos": video_payload.get("duracao_segundos", 0.0),
            "palavras_totais": video_payload.get("palavras_totais", 0),
            "total_cenas": video_payload.get("total_cenas", 0),
            "estilo_voz": video_payload.get("estilo_voz", "gemini:Charon"),
            "criado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
            # Métricas analíticas a serem preenchidas pelo usuário
            "analytics": video_payload.get("analytics", {
                "views": 0,
                "retention_3s_pct": None,
                "apv_pct": None,            # Average Percentage Viewed
                "ctr_pct": None,            # Click-Through Rate
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "performance_tier": "PENDING", # S, A, B, C, D ou PENDING
                "feedback_notes": ""
            })
        }

        if existing_idx is not None:
            history_data[existing_idx] = entry
        else:
            history_data.append(entry)

        payload = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_records": len(history_data),
            "records": history_data
        }
        self._save_json_atomic(self.history_file, payload)
        self._regenerate_markdown_memory()
        app_logger.info(f"[AlgorithmMemory] Vídeo '{entry['tema']}' registrado na memória de analytics.")
        return video_id

    @staticmethod
    def _calculate_exposure_aware_tier(
        views: int,
        exposure_days: float,
        views_per_day: float,
        projected_28d_views: int,
        apv_pct: Optional[float],
        ctr_pct: Optional[float],
        retention_3s_pct: Optional[float],
        likes: int = 0
    ) -> str:
        """
        Classificação MECE imune ao viés de tempo de exposição (vídeos antigos vs recentes).
        Avalia velocidade diária (VPD), projeção 28d e retenção intrínseca (APV/CTR).
        """
        # 1. Período de Incubação (menos de 24h e menos de 10 views no Sandbox)
        if exposure_days <= 1.0 and views < 10 and (apv_pct is None or apv_pct < 50.0):
            return "INCUBATING"

        # 2. Gancho Fraco / Rejeição Imediata (Retenção 3s < 30% ou APV < 20% com amostra mínima)
        if (retention_3s_pct is not None and retention_3s_pct < 30.0) or (apv_pct is not None and apv_pct < 20.0):
            return "D"

        # 3. Tier S - Super Viral / Tração Explosiva
        # (Ou velocidade diária explosiva >= 250 views/dia, ou volume projetado >= 3000 views, ou histórico >= 5000 views)
        if (views_per_day >= 250.0 or projected_28d_views >= 3000 or views >= 5000):
            if apv_pct is None or apv_pct >= 20.0:
                return "S"

        # 4. Tier A - Excelente Tração e Retenção Forte
        if (views_per_day >= 75.0 or projected_28d_views >= 1000 or views >= 1500 or (apv_pct and apv_pct >= 65.0 and views >= 40)):
            return "A"

        # 5. Tier B - Sólido / Tração Estável
        if (views_per_day >= 15.0 or projected_28d_views >= 200 or views >= 100 or (apv_pct and apv_pct >= 40.0 and views >= 5)):
            return "B"

        # 6. Tier C - Baixa Tração / Desaceleração após exposição relevante
        if exposure_days >= 3.0 and views_per_day < 15.0 and views >= 15:
            if apv_pct and apv_pct >= 30.0:
                return "C"
            return "D"

        if views >= 1:
            return "B"
        return "PENDING"

    def ingest_analytics_feedback(
        self,
        identifier: str, # pode ser video_id ou formato "batch_1/video_0" ou parte do tema
        views: int = 0,
        retention_3s_pct: Optional[float] = None,
        apv_pct: Optional[float] = None,
        ctr_pct: Optional[float] = None,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        publish_date: Optional[str] = None,
        exposure_days: Optional[float] = None,
        views_per_day: Optional[float] = None,
        projected_28d_views: Optional[int] = None,
        growth_trajectory: Optional[str] = None,
        watch_time_hours: Optional[float] = None,
        impressions: Optional[int] = None,
        subscribers: Optional[int] = None,
        feedback_notes: str = "",
        ai_analyzer_callback = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Recebe o retorno de performance real de um conteúdo publicado no YouTube Shorts,
        calcula métricas de velocidade e evolução temporal, atualiza o registro e reavalia a IA.
        """
        history = self.load_history()
        target_record = None
        target_idx = -1

        # Busca por video_id exato, batch/video_index ou substring de tema
        for i, r in enumerate(history):
            bv_tag = f"{r.get('batch')}/{r.get('video_index')}"
            bv_tag_v = f"{r.get('batch')}/video_{r.get('video_index')}"
            if r.get("video_id") == identifier or identifier in (bv_tag, bv_tag_v) or identifier.lower() in r.get("tema", "").lower():
                target_record = r
                target_idx = i
                break

        if target_idx == -1 or not target_record:
            return False, f"Nenhum vídeo encontrado para o identificador '{identifier}'.", {}

        # Normalização temporal caso não venha precalculada
        exp_days = float(exposure_days or 1.0)
        vpd = float(views_per_day if views_per_day is not None else round(views / max(1.0, exp_days), 2))
        if projected_28d_views is not None:
            proj_views = int(projected_28d_views)
        else:
            proj_views = int(round(views * (1.0 + 1.2 * math.log(max(1.0, 28.0 / exp_days))))) if exp_days < 28.0 else views

        traj = growth_trajectory or ("VIRAL_BURST" if vpd >= 200 and exp_days <= 2 else ("STEADY_GROWTH" if vpd >= 15 else "INCUBATING"))

        # Classificação de Tier imune ao viés de tempo de publicação
        tier = self._calculate_exposure_aware_tier(
            views=views,
            exposure_days=exp_days,
            views_per_day=vpd,
            projected_28d_views=proj_views,
            apv_pct=apv_pct,
            ctr_pct=ctr_pct,
            retention_3s_pct=retention_3s_pct,
            likes=likes
        )

        analytics_update = {
            "views": views,
            "publish_date": publish_date,
            "exposure_days": exp_days,
            "views_per_day": vpd,
            "projected_28d_views": proj_views,
            "growth_trajectory": traj,
            "watch_time_hours": watch_time_hours,
            "impressions": impressions,
            "subscribers": subscribers,
            "retention_3s_pct": retention_3s_pct,
            "apv_pct": apv_pct,
            "ctr_pct": ctr_pct,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "performance_tier": tier,
            "feedback_notes": feedback_notes,
            "feedback_updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }

        target_record["analytics"] = analytics_update
        history[target_idx] = target_record

        payload = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_records": len(history),
            "records": history
        }
        self._save_json_atomic(self.history_file, payload)

        # Ajuste dinâmico de pesos auxiliares ponderado por velocidade diária e retenção
        self._recalculate_weights_from_analytics()
        self._regenerate_markdown_memory()

        msg = f"Feedback analítico registrado para '{target_record.get('tema')}'! ({vpd:.1f} views/dia) -> Classificado como Tier [{tier}]."
        app_logger.info(f"[AlgorithmMemory] {msg}")
        return True, msg, target_record

    def _recalculate_weights_from_analytics(self):
        """
        Calcula correlação estatística ponderada por velocidade temporal (VPD) e retenção intrínseca (APV)
        entre vídeos de alto desempenho (Tier S e A) e ajusta os pesos auxiliares para guiar as próximas gerações.
        """
        history = self.load_history()
        graded_videos = [r for r in history if r.get("analytics", {}).get("performance_tier") in ("S", "A", "B", "C", "D")]
        if not graded_videos:
            return

        weights = self.load_weights()
        top_tier = [r for r in graded_videos if r.get("analytics", {}).get("performance_tier") in ("S", "A")]
        low_tier = [r for r in graded_videos if r.get("analytics", {}).get("performance_tier") in ("C", "D")]

        if top_tier:
            # Ponderação estatística por velocidade diária (VPD) e APV %
            total_weight = sum(
                max(1.0, float(r.get("analytics", {}).get("views_per_day", 1.0))) * (1.0 + float(r.get("analytics", {}).get("apv_pct", 50.0) or 50.0) / 100.0)
                for r in top_tier
            )

            weighted_wpm = sum(
                ((r.get("palavras_totais", 0) / max(0.1, r.get("duracao_segundos", 60.0))) * 60.0) *
                (max(1.0, float(r.get("analytics", {}).get("views_per_day", 1.0))) * (1.0 + float(r.get("analytics", {}).get("apv_pct", 50.0) or 50.0) / 100.0))
                for r in top_tier if r.get("duracao_segundos", 0) > 0
            ) / total_weight if total_weight > 0 else 185.0

            weighted_cut_freq = sum(
                (r.get("duracao_segundos", 60.0) / max(1, r.get("total_cenas", 15))) *
                (max(1.0, float(r.get("analytics", {}).get("views_per_day", 1.0))) * (1.0 + float(r.get("analytics", {}).get("apv_pct", 50.0) or 50.0) / 100.0))
                for r in top_tier if r.get("total_cenas", 0) > 0
            ) / total_weight if total_weight > 0 else 2.8

            if 120 < weighted_wpm < 250:
                weights["pacing_cadence_wpm"] = round(0.6 * weights["pacing_cadence_wpm"] + 0.4 * weighted_wpm, 1)

            if 1.5 < weighted_cut_freq < 6.0:
                weights["broll_cut_frequency_sec"] = round(0.6 * weights["broll_cut_frequency_sec"] + 0.4 * weighted_cut_freq, 2)

            # Reforço progressivo nos pilares de alta conversão
            weights["technical_depth_weight"] = min(0.99, round(weights["technical_depth_weight"] + 0.01, 3))
            weights["hook_curiosity_gap_weight"] = min(0.99, round(weights["hook_curiosity_gap_weight"] + 0.01, 3))
            weights["anti_hype_precision_weight"] = min(0.99, round(weights["anti_hype_precision_weight"] + 0.01, 3))

        if low_tier and not top_tier:
            weights["anti_hype_precision_weight"] = min(0.99, round(weights["anti_hype_precision_weight"] + 0.03, 3))

        self.save_weights(weights)

    def _regenerate_markdown_memory(self):
        """
        Compila todos os aprendizados, métricas e pesos no arquivo legível ALGORITHM_MEMORY.md.
        """
        history = self.load_history()
        weights = self.load_weights()
        
        s_count = sum(1 for r in history if r.get("analytics", {}).get("performance_tier") == "S")
        a_count = sum(1 for r in history if r.get("analytics", {}).get("performance_tier") == "A")
        b_count = sum(1 for r in history if r.get("analytics", {}).get("performance_tier") == "B")
        c_count = sum(1 for r in history if r.get("analytics", {}).get("performance_tier") == "C")
        d_count = sum(1 for r in history if r.get("analytics", {}).get("performance_tier") == "D")
        total_views = sum(r.get("analytics", {}).get("views", 0) for r in history)

        md_content = f"""# 🧠 Base de Inteligência Algorítmica e Memória de Conteúdo (.md)
*Atualizado em: {time.strftime('%Y-%m-%d %H:%M:%S')} | Total de Vídeos Monitorados: {len(history)} | Total de Visualizações: {total_views:,}*

Este documento representa a **Memória Viva de Aprendizado de Máquina** do gerador de conteúdo automotivo.
A IA geradora consulta esta memória antes de criar qualquer novo roteiro, absorvendo a dinâmica que gerou alta retenção sem jamais repetir os temas já produzidos.

---

## 1. 🎯 Vetor de Pesos Auxiliares Ativos (Style & Retention Vector)

Os pesos abaixo guiam as diretrizes dos agentes (ProposerAgent, DissertationAgent e DirectorAgent) para convergir no estilo de maior retenção:

| Parâmetro Algorítmico | Peso Ativo | Descrição e Impacto no Roteiro |
| :--- | :---: | :--- |
| **`hook_curiosity_gap_weight`** | `{weights.get('hook_curiosity_gap_weight', 0.95):.2f}` | Impacto e paradoxo nos primeiros 3 segundos (Palavra de chamariz sem sensacionalismo) |
| **`technical_depth_weight`** | `{weights.get('technical_depth_weight', 0.92):.2f}` | Densidade de fatos de engenharia mecânica, física real e telemetria precisa |
| **`anti_hype_precision_weight`** | `{weights.get('anti_hype_precision_weight', 0.90):.2f}` | **Tolerância Zero a Sensacionalismo Vazio**: Elimina adjetivos genéricos no meio do vídeo |
| **`visceral_sound_focus_weight`** | `{weights.get('visceral_sound_focus_weight', 0.88):.2f}` | Priorização de tomadas com som puro de escape, dyno pulls e altas rotações (4K) |
| **`telemetry_density_weight`** | `{weights.get('telemetry_density_weight', 0.85):.2f}` | Inserção de dados exatos (rpm, cv, kgfm, milissegundos de troca, tempos de volta) |
| **`pacing_cadence_wpm`** | `{weights.get('pacing_cadence_wpm', 185.0):.1f} WPM` | Ritmo de fala ideal (palavras por minuto a 1.25x para manter o espectador hipnotizado) |
| **`broll_cut_frequency_sec`** | `{weights.get('broll_cut_frequency_sec', 2.8):.2f}s` | Frequência média de troca de cena (cortes rápidos a cada 2 a 3 segundos) |
| **`conflict_and_triumph_weight`** | `{weights.get('conflict_and_triumph_weight', 0.80):.2f}` | Narrativa de obstáculo da física superado pela engenharia mecânica |
| **`comment_trigger_weight`** | `{weights.get('comment_trigger_weight', 0.85):.2f}` | Força da pergunta final provocativa para explodir o algoritmo de comentários |

---

## 2. 📊 Distribuição de Performance por Tiers

- 🏆 **Tier S (Super Viral - Retenção > 85%):** {s_count} vídeos
- 🥇 **Tier A (Excelente - Retenção > 70%):** {a_count} vídeos
- 🥈 **Tier B (Sólido - Retenção 55%-70%):** {b_count} vídeos
- 🥉 **Tier C (Abaixo da Média - Retenção < 50%):** {c_count} vídeos
- ⚠️ **Tier D (Queda Imediata no Gancho):** {d_count} vídeos

---

## 3. 🔬 Diretrizes Estratégicas Aprendidas (Invariantes de Roteirização)

1. **Estrutura em Duas Fases (Dissertação $\\to$ Destilação de Alta Retenção):**
   - **Fase 1 (Dissertação Completa):** Construir primeiro uma monografia profunda sobre a máquina, com telemetria exata, fluidodinâmica e contexto histórico.
   - **Fase 2 (Destilação 60s-120s):** Sintetizar a dissertação em 160 a 260 palavras a 1.25x. Preserva a riqueza dos dados técnicos, eliminando qualquer enrolação ou adjetivação vazia.
2. **Hook Magnético nos Primeiros 3 Segundos:**
   - O início deve conter a **palavra de chamariz e a tese central** (ex: *"Por que a Ferrari baniu este motor V12 das ruas?"* ou *"A Porsche gastou 4 anos para resolver este único detalhe aerodinâmico"*).
   - Após o gancho, o meio do vídeo foca **100% na explicação mecânica real**, sem termos exagerados repetitivos.
3. **Pronúncia Fonética Perfeita:**
   - Todos os nomes estrangeiros (*Porsche, Koenigsegg, Twin-Turbo, Downforce, Horsepower, Wastegate*) são convertidos foneticamente para o áudio, garantindo autoridade máxima, com legendas perfeitamente escritas na tela.

---

## 4. 📋 Tabela de Histórico e Analytics de Conteúdos

| # | Batch/Vídeo | Título / Objeto Mecânico | Duração | Cenas | Views | Retenção 3s | APV % | Tier | Notas de Feedback |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
"""

        for idx, r in enumerate(history, 1):
            an = r.get("analytics", {})
            v_views = f"{an.get('views', 0):,}" if an.get('views') is not None else "-"
            r_3s = f"{an.get('retention_3s_pct'):.1f}%" if an.get('retention_3s_pct') is not None else "-"
            apv = f"{an.get('apv_pct'):.1f}%" if an.get('apv_pct') is not None else "-"
            t_tier = an.get("performance_tier", "PENDING")
            dur = f"{r.get('duracao_segundos', 0):.1f}s"
            cenas_cnt = r.get('total_cenas', 0)
            tema_short = r.get('tema', 'Sem Título')[:40]
            notes = an.get('feedback_notes', '')[:35]
            bv = f"{r.get('batch')}/v{r.get('video_index')}"
            
            md_content += f"| {idx} | `{bv}` | {tema_short} | {dur} | {cenas_cnt} | {v_views} | {r_3s} | {apv} | **{t_tier}** | {notes} |\n"

        if not history:
            md_content += "| - | - | Nenhum vídeo registrado ainda | - | - | - | - | - | - | Aguardando primeira geração |\n"

        md_content += """
---
*AI Slop Studio Algorithmic Intelligence • Documento Gerado e Mantido Automaticamente*
"""
        with open(self.memory_md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

    def scan_and_sync_checkpoints(self, checkpoints_dir: Optional[str] = None) -> Tuple[int, int]:
        """
        Varre todos os checkpoints de lotes de produção (ex: checkpoint/batch_X/video_Y),
        preserva os pesos e metadados originais de cada vídeo e desconsidera eventuais
        vídeos cujo metadata foi corrompido ou perdido.
        Retorna (total_validos, total_desconsiderados).
        """
        import glob
        base_dir = os.path.abspath(checkpoints_dir or os.path.join(PROJECT_ROOT, "checkpoint"))
        if not os.path.exists(base_dir):
            alt_dir = os.path.join(PROJECT_ROOT, "data", "checkpoints")
            if os.path.exists(alt_dir):
                base_dir = alt_dir

        pattern = os.path.join(base_dir, "**", "checkpoint.json")
        cp_files = sorted(glob.glob(pattern, recursive=True))
        
        history = self.load_history()
        existing_history_map = {r.get("video_id"): r for r in history}
        synced_history_map = {}
        
        valid_count = 0
        ignored_count = 0
        current_weights = self.load_weights()

        for cp_path in cp_files:
            try:
                with open(cp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                b_name = data.get("batch_name") or f"batch_{data.get('batch_index', 0)}"
                v_name = data.get("video_name") or f"video_{data.get('video_index', 0)}"
                vid_id = f"{b_name}_{v_name}"
                
                status = data.get("status", "PENDING")
                topic = data.get("topic", {})
                tema = topic.get("tema") or data.get("tema") or ""
                
                storyboard = data.get("storyboard", [])
                words_timing = data.get("words_timing", [])
                duration = 0.0
                if words_timing:
                    duration = words_timing[-1].get("end", 0.0)

                # Desconsidera vídeos com dados corrompidos ou incompletos
                if not tema or not storyboard:
                    ignored_count += 1
                    app_logger.warning(f"[AlgorithmMemory] Metadata perdido/inválido para {b_name}/{v_name}. Desconsiderando por segurança.")
                    continue

                # Preserva analíticas já digitadas pelo usuário se o vídeo já existia
                existing = existing_history_map.get(vid_id, {})
                existing_analytics = existing.get("analytics", {
                    "views": 0,
                    "retention_3s_pct": None,
                    "apv_pct": None,
                    "ctr_pct": None,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "performance_tier": "PENDING",
                    "feedback_notes": ""
                })

                # Preserva os pesos específicos com os quais o enredo foi concebido
                gen_weights = existing.get("generation_weights") or data.get("generation_weights") or dict(current_weights)

                # Extrai entidade principal
                core_entity = topic.get("core_entity") or extract_canonical_entity(tema)

                entry = {
                    "video_id": vid_id,
                    "batch": b_name,
                    "video_index": data.get("video_index", 0),
                    "tema": tema,
                    "core_entity": core_entity,
                    "hook": topic.get("hook", ""),
                    "duracao_segundos": duration,
                    "palavras_totais": len(words_timing),
                    "total_cenas": len(storyboard),
                    "estilo_voz": data.get("voice", "gemini:Charon"),
                    "status_checkpoint": status,
                    "status_metadata": "VALIDO",
                    "generation_weights": gen_weights,
                    "analytics": existing_analytics,
                    "checkpoint_file": cp_path,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
                }

                synced_history_map[vid_id] = entry
                valid_count += 1
            except Exception as e:
                ignored_count += 1
                app_logger.warning(f"[AlgorithmMemory] Erro ao ler checkpoint {cp_path}: {str(e)}")

        updated_history = list(synced_history_map.values())
        payload = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_records": len(updated_history),
            "records": updated_history
        }
        self._save_json_atomic(self.history_file, payload)
        self._regenerate_markdown_memory()
        if self.memory_dir == os.path.abspath(MEMORY_DIR):
            self.export_metrics_csv()
            self.export_metrics_markdown()
        
        app_logger.info(f"[AlgorithmMemory] Sincronização concluída: {valid_count} vídeos válidos preservados, {ignored_count} desconsiderados.")
        return valid_count, ignored_count

    def purge_batch(self, batch_name: str) -> int:
        """
        Remove todas as entradas de um batch específico da memória algorítmica.
        Regenera history.json, ALGORITHM_MEMORY.md, METRICAS_VIDEOS.csv e METRICAS_VIDEOS.md.
        """
        history = self.load_history()
        filtered = [r for r in history if r.get("batch") != batch_name]
        removed = len(history) - len(filtered)
        if removed > 0:
            payload = {
                "version": 1,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_records": len(filtered),
                "records": filtered
            }
            self._save_json_atomic(self.history_file, payload)
            self._regenerate_markdown_memory()
            if self.memory_dir == os.path.abspath(MEMORY_DIR):
                self.export_metrics_csv()
                self.export_metrics_markdown()
            app_logger.info(f"[AlgorithmMemory] {removed} registro(s) do {batch_name} expurgado(s) da memória algorítmica.")
        return removed

    def export_metrics_csv(self, csv_path: Optional[str] = None) -> str:
        """
        Gera e atualiza o arquivo template METRICAS_VIDEOS.csv na raiz do projeto.
        Preserva as views e notas já digitadas pelo usuário, adiciona novos vídeos
        e inclui colunas para todos os pesos da IA que concebeu o enredo daquele vídeo.
        """
        import csv
        target_file = os.path.abspath(csv_path or os.path.join(PROJECT_ROOT, "METRICAS_VIDEOS.csv"))
        
        # Lê valores previamente inseridos no CSV para não sobrescrever o que o usuário já digitou
        user_entered_metrics = {}
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        vid = row.get("identificador") or f"{row.get('batch')}_{row.get('video_index')}"
                        if vid:
                            user_entered_metrics[vid] = row
            except Exception as e:
                app_logger.warning(f"[AlgorithmMemory] Erro ao ler CSV existente: {str(e)}")

        history = self.load_history()
        headers = [
            "identificador",
            "batch",
            "video_index",
            "titulo",
            "veiculo",
            "hook",
            "duracao_segundos",
            "total_cenas",
            "palavras_roteiro",
            "peso_hook",
            "peso_tech",
            "peso_antihype",
            "peso_sound",
            "peso_telemetria",
            "cadencia_wpm",
            "cortes_seg",
            "peso_comentarios",
            "dias_exposicao",
            "views",
            "views_por_dia",
            "views_projetadas_28d",
            "trajetoria",
            "retencao_3s_pct",
            "apv_pct",
            "ctr_pct",
            "curtidas",
            "comentarios",
            "tier",
            "observacoes_sucesso",
            "status_metadata"
        ]

        rows = []
        for r in history:
            vid = r.get("video_id")
            an = r.get("analytics", {})
            gw = r.get("generation_weights", {})
            
            # Se o usuário digitou no CSV previamente, recupera os valores
            prev = user_entered_metrics.get(vid, {})
            
            views_val = prev.get("views") if prev.get("views") not in (None, "", "0") else (an.get("views", 0) or "")
            exp_days_val = prev.get("dias_exposicao") or an.get("exposure_days", 1.0)
            vpd_val = prev.get("views_por_dia") or an.get("views_per_day", "")
            proj28_val = prev.get("views_projetadas_28d") or an.get("projected_28d_views", "")
            traj_val = prev.get("trajetoria") or an.get("growth_trajectory", "STEADY_GROWTH")
            tier_val = an.get("performance_tier", "PENDING")

            ret3s_val = prev.get("retencao_3s_pct") if prev.get("retencao_3s_pct") not in (None, "") else (an.get("retention_3s_pct", "") if an.get("retention_3s_pct") is not None else "")
            apv_val = prev.get("apv_pct") if prev.get("apv_pct") not in (None, "") else (an.get("apv_pct", "") if an.get("apv_pct") is not None else "")
            ctr_val = prev.get("ctr_pct") if prev.get("ctr_pct") not in (None, "") else (an.get("ctr_pct", "") if an.get("ctr_pct") is not None else "")
            likes_val = prev.get("curtidas") if prev.get("curtidas") not in (None, "", "0") else (an.get("likes", 0) or "")
            comments_val = prev.get("comentarios") if prev.get("comentarios") not in (None, "", "0") else (an.get("comments", 0) or "")
            notes_val = prev.get("observacoes_sucesso") or an.get("feedback_notes", "")

            row_dict = {
                "identificador": vid,
                "batch": r.get("batch"),
                "video_index": r.get("video_index"),
                "titulo": r.get("tema", ""),
                "veiculo": r.get("core_entity", ""),
                "hook": r.get("hook", ""),
                "duracao_segundos": f"{r.get('duracao_segundos', 0.0):.1f}",
                "total_cenas": r.get("total_cenas", 0),
                "palavras_roteiro": r.get("palavras_totais", 0),
                "peso_hook": f"{gw.get('hook_curiosity_gap_weight', 0.95):.2f}",
                "peso_tech": f"{gw.get('technical_depth_weight', 0.92):.2f}",
                "peso_antihype": f"{gw.get('anti_hype_precision_weight', 0.90):.2f}",
                "peso_sound": f"{gw.get('visceral_sound_focus_weight', 0.88):.2f}",
                "peso_telemetria": f"{gw.get('telemetry_density_weight', 0.85):.2f}",
                "cadencia_wpm": f"{gw.get('pacing_cadence_wpm', 185.0):.0f}",
                "cortes_seg": f"{gw.get('broll_cut_frequency_sec', 2.8):.1f}",
                "peso_comentarios": f"{gw.get('comment_trigger_weight', 0.85):.2f}",
                "dias_exposicao": f"{float(exp_days_val):.1f}",
                "views": views_val,
                "views_por_dia": vpd_val,
                "views_projetadas_28d": proj28_val,
                "trajetoria": traj_val,
                "retencao_3s_pct": ret3s_val,
                "apv_pct": apv_val,
                "ctr_pct": ctr_val,
                "curtidas": likes_val,
                "comentarios": comments_val,
                "tier": tier_val,
                "observacoes_sucesso": notes_val,
                "status_metadata": r.get("status_metadata", "VALIDO")
            }
            rows.append(row_dict)

        with open(target_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        app_logger.info(f"[AlgorithmMemory] Arquivo template CSV exportado na raiz: {target_file}")
        return target_file

    def import_metrics_csv(self, csv_path: Optional[str] = None) -> Tuple[int, int, List[str]]:
        """
        Lê o arquivo METRICAS_VIDEOS.csv da raiz, ingere os números de views e retenção inseridos
        pelo usuário, recalibra os pesos auxiliares e regenera o ALGORITHM_MEMORY.md.
        Retorna (atualizados_count, ignorados_count, mensagens).
        """
        import csv
        target_file = os.path.abspath(csv_path or os.path.join(PROJECT_ROOT, "METRICAS_VIDEOS.csv"))
        if not os.path.exists(target_file):
            return 0, 0, [f"Arquivo CSV não encontrado em: {target_file}"]

        updated_count = 0
        ignored_count = 0
        messages = []

        with open(target_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                identificador = row.get("identificador") or f"{row.get('batch')}_{row.get('video_index')}"
                status_meta = row.get("status_metadata", "VALIDO").strip().upper()
                
                # Desconsidera vídeos cujo metadata foi perdido
                if status_meta == "PERDIDO":
                    ignored_count += 1
                    messages.append(f"Ignorado por segurança (metadata perdido): {identificador}")
                    continue

                views_str = str(row.get("views", "")).strip().replace(".", "").replace(",", "")
                exp_days_str = str(row.get("dias_exposicao", "1.0")).strip().replace(",", ".")
                vpd_str = str(row.get("views_por_dia", "")).strip().replace(",", ".")
                proj28_str = str(row.get("views_projetadas_28d", "")).strip().replace(".", "").replace(",", "")
                traj_str = str(row.get("trajetoria", "STEADY_GROWTH")).strip()

                ret3s_str = str(row.get("retencao_3s_pct", "")).strip().replace(",", ".")
                apv_str = str(row.get("apv_pct", "")).strip().replace(",", ".")
                ctr_str = str(row.get("ctr_pct", "")).strip().replace(",", ".")
                likes_str = str(row.get("curtidas", "")).strip().replace(".", "").replace(",", "")
                comments_str = str(row.get("comentarios", "")).strip().replace(".", "").replace(",", "")
                notes = str(row.get("observacoes_sucesso", "")).strip()

                try:
                    views = int(views_str) if views_str and views_str.isdigit() else 0
                    exp_days = float(exp_days_str) if exp_days_str else 1.0
                    vpd = float(vpd_str) if vpd_str else round(views / max(1.0, exp_days), 2)
                    proj28 = int(proj28_str) if proj28_str and proj28_str.isdigit() else None
                    ret_3s = float(ret3s_str) if ret3s_str else None
                    apv = float(apv_str) if apv_str else None
                    ctr = float(ctr_str) if ctr_str else None
                    likes = int(likes_str) if likes_str and likes_str.isdigit() else 0
                    comments = int(comments_str) if comments_str and comments_str.isdigit() else 0
                except Exception as e_parse:
                    messages.append(f"Erro ao converter números para {identificador}: {str(e_parse)}")
                    continue

                # Atualiza se o usuário inseriu algum dado
                if views > 0 or ret_3s is not None or apv is not None or notes:
                    ok, msg, rec = self.ingest_analytics_feedback(
                        identifier=identificador,
                        views=views,
                        exposure_days=exp_days,
                        views_per_day=vpd,
                        projected_28d_views=proj28,
                        growth_trajectory=traj_str,
                        retention_3s_pct=ret_3s,
                        apv_pct=apv,
                        ctr_pct=ctr,
                        likes=likes,
                        comments=comments,
                        shares=0,
                        feedback_notes=notes
                    )
                    if ok:
                        updated_count += 1
                        messages.append(f"Atualizado: {identificador} -> {views:,} views ({vpd:.1f} views/dia) [Tier {rec.get('analytics', {}).get('performance_tier')}]")
                    else:
                        messages.append(f"Falha ao atualizar {identificador}: {msg}")

        self.export_metrics_markdown()
        return updated_count, ignored_count, messages

    def ingest_from_analytics_zip(self, zip_path: Optional[str] = None) -> Tuple[int, int, List[str]]:
        """
        Lê um arquivo .zip exportado do YouTube Analytics, extrai as métricas de cada vídeo
        com normalização de tempo de exposição, faz o casamento inteligente com os vídeos locais
        e atualiza a base e os pesos da IA.
        Retorna (atualizados_count, ignorados_count, mensagens).
        """
        parser = DEFAULT_ANALYTICS_PARSER
        target_zip = zip_path or parser.find_latest_zip()
        if not target_zip or not os.path.exists(target_zip):
            return 0, 0, [f"Nenhum arquivo .zip encontrado em: {parser.analytics_dir}"]

        yt_items = parser.parse_zip_content(target_zip)
        if not yt_items:
            return 0, 0, [f"Nenhum dado válido extraído de {os.path.basename(target_zip)}"]

        history = self.load_history()
        matched_pairs, unmatched = parser.match_youtube_to_local_records(yt_items, history)

        updated_count = 0
        ignored_count = len(unmatched)
        messages = [f"📦 Arquivo processado: {os.path.basename(target_zip)} ({len(yt_items)} vídeos no export)"]

        for pair in matched_pairs:
            local_rec = pair["local_record"]
            yt_data = pair["youtube_data"]
            vid_id = local_rec.get("video_id")

            ok, msg, rec = self.ingest_analytics_feedback(
                identifier=vid_id,
                views=yt_data.get("views", 0),
                publish_date=yt_data.get("publish_date"),
                exposure_days=yt_data.get("exposure_days"),
                views_per_day=yt_data.get("views_per_day"),
                projected_28d_views=yt_data.get("projected_28d_views"),
                growth_trajectory=yt_data.get("growth_trajectory"),
                watch_time_hours=yt_data.get("watch_time_hours"),
                impressions=yt_data.get("impressions"),
                subscribers=yt_data.get("subscribers"),
                retention_3s_pct=yt_data.get("retention_3s_pct"),
                apv_pct=yt_data.get("apv_pct"),
                ctr_pct=yt_data.get("ctr_pct"),
                likes=yt_data.get("likes", 0),
                comments=yt_data.get("comments", 0),
                shares=yt_data.get("shares", 0),
                feedback_notes=f"YouTube: {yt_data.get('clean_title')[:30]} ({pair['match_score']:.0%})"
            )
            if ok:
                updated_count += 1
                tier = rec.get("analytics", {}).get("performance_tier", "PENDING")
                vpd = rec.get("analytics", {}).get("views_per_day", 0.0)
                proj28 = rec.get("analytics", {}).get("projected_28d_views", 0)
                traj = rec.get("analytics", {}).get("growth_trajectory", "STEADY_GROWTH")
                messages.append(
                    f"✅ Casado: '{yt_data['clean_title'][:32]}' -> `{vid_id}` | "
                    f"{yt_data.get('views', 0):,} views ({vpd:.1f} views/dia | Proj 28d: {proj28:,}) | "
                    f"APV: {yt_data.get('apv_pct', 0.0)}% | [{traj}] -> [Tier {tier}]"
                )
            else:
                messages.append(f"⚠️ Falha ao atualizar `{vid_id}`: {msg}")

        for un in unmatched:
            vpd_un = un.get("views_per_day", 0.0)
            messages.append(f"ℹ️ Não casado (sem correspondente local): '{un['clean_title'][:38]}' ({un.get('views', 0)} views | {vpd_un:.1f} v/d)")

        # Sincroniza e regenera os arquivos CSV e MD com os novos dados
        self.export_metrics_csv()
        self.export_metrics_markdown()

        return updated_count, ignored_count, messages

    def get_last_ingested_analytics_info(self) -> Dict[str, Any]:
        """Retorna informações sobre o último arquivo de analytics ingerido."""
        info_file = os.path.join(self.memory_dir, "analytics_ingestion_state.json")
        if os.path.exists(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def set_last_ingested_analytics_info(self, file_path: str, stats: Dict[str, Any]):
        """Salva o estado do arquivo de analytics ingerido para rastreamento de mudanças de nome ou conteúdo."""
        info_file = os.path.join(self.memory_dir, "analytics_ingestion_state.json")
        payload = {
            "file_name": os.path.basename(file_path),
            "file_path": os.path.abspath(file_path),
            "mtime": os.path.getmtime(file_path) if os.path.exists(file_path) else 0.0,
            "size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "stats": stats
        }
        self._save_json_atomic(info_file, payload)

    def check_and_auto_ingest_analytics(self, analytics_dir: Optional[str] = None) -> Tuple[bool, str]:
        """
        Verifica se há um novo arquivo .zip na pasta /analytics (ou se o nome do arquivo mudou).
        Se mudou, executa a ingestão automaticamente e atualiza pesos e métricas.
        Retorna (teve_atualizacao, mensagem_informativa).
        """
        parser = YouTubeAnalyticsZipParser(analytics_dir=analytics_dir) if analytics_dir else DEFAULT_ANALYTICS_PARSER
        latest_zip = parser.find_latest_zip()
        if not latest_zip:
            return False, "Nenhum arquivo .zip na pasta /analytics."

        current_file_name = os.path.basename(latest_zip)
        current_mtime = os.path.getmtime(latest_zip)
        current_size = os.path.getsize(latest_zip)

        last_info = self.get_last_ingested_analytics_info()
        last_file_name = last_info.get("file_name")
        last_mtime = last_info.get("mtime", 0.0)
        last_size = last_info.get("size", 0)

        # Checa se o nome do arquivo mudou ou se o arquivo foi atualizado
        file_changed = (
            current_file_name != last_file_name
            or abs(current_mtime - last_mtime) > 1.0
            or current_size != last_size
        )

        if not file_changed:
            return False, f"Arquivo '{current_file_name}' já está ingerido e atualizado."

        app_logger.info(f"[AlgorithmMemory] Novo pacote de analytics detectado: '{current_file_name}' (anterior: '{last_file_name}'). Ingerindo...")
        updated_count, ignored_count, msgs = self.ingest_from_analytics_zip(latest_zip)
        
        stats = {
            "updated_count": updated_count,
            "ignored_count": ignored_count
        }
        self.set_last_ingested_analytics_info(latest_zip, stats)
        
        msg = f"Novo pacote de analytics '{current_file_name}' ingerido com sucesso! ({updated_count} vídeos atualizados com normalização de idade)."
        app_logger.info(f"[AlgorithmMemory] {msg}")
        return True, msg

    def scan_and_ingest_analytics_folder(self, analytics_dir: Optional[str] = None) -> Tuple[int, int, List[str]]:
        """
        Escaneia a pasta /analytics pelo arquivo .zip mais recente e executa a ingestão.
        """
        parser = YouTubeAnalyticsZipParser(analytics_dir=analytics_dir) if analytics_dir else DEFAULT_ANALYTICS_PARSER
        latest_zip = parser.find_latest_zip()
        if latest_zip:
            updated_count, ignored_count, msgs = self.ingest_from_analytics_zip(latest_zip)
            self.set_last_ingested_analytics_info(latest_zip, {"updated_count": updated_count, "ignored_count": ignored_count})
            return updated_count, ignored_count, msgs
        return 0, 0, [f"Nenhum arquivo .zip encontrado na pasta {parser.analytics_dir}"]

    def export_metrics_markdown(self, md_path: Optional[str] = None) -> str:
        """
        Gera e atualiza o arquivo METRICAS_VIDEOS.md na raiz do diretório,
        fornecendo um relatório legível com instruções, tabela de métricas normalizadas e status dos pesos da IA.
        """
        target_file = os.path.abspath(md_path or os.path.join(PROJECT_ROOT, "METRICAS_VIDEOS.md"))
        history = self.load_history()
        weights = self.load_weights()
        
        valid_records = [r for r in history if r.get("status_metadata") != "PERDIDO"]
        ignored_records = [r for r in history if r.get("status_metadata") == "PERDIDO"]

        total_views = sum(r.get("analytics", {}).get("views", 0) for r in valid_records)
        s_count = sum(1 for r in valid_records if r.get("analytics", {}).get("performance_tier") == "S")
        a_count = sum(1 for r in valid_records if r.get("analytics", {}).get("performance_tier") == "A")
        b_count = sum(1 for r in valid_records if r.get("analytics", {}).get("performance_tier") == "B")
        c_count = sum(1 for r in valid_records if r.get("analytics", {}).get("performance_tier") == "C")
        d_count = sum(1 for r in valid_records if r.get("analytics", {}).get("performance_tier") == "D")

        # Top performers por velocidade
        sorted_by_velocity = sorted(
            [r for r in valid_records if r.get("analytics", {}).get("views", 0) > 0],
            key=lambda x: x.get("analytics", {}).get("views_per_day", 0.0),
            reverse=True
        )

        md_content = f"""# 📊 Painel de Métricas de Vídeos e Retorno do Algoritmo

*Atualizado em: {time.strftime('%Y-%m-%d %H:%M:%S')} | Total de Vídeos Válidos: {len(valid_records)} | Total de Visualizações: {total_views:,}*
*Distribuição de Tiers: 🏆 Tier S: {s_count} | 🥇 Tier A: {a_count} | 🥈 Tier B: {b_count} | 🥉 Tier C: {c_count} | ⚠️ Tier D: {d_count}*

> [!IMPORTANT]
> **Normalização de Idade & Tempo de Exposição:**
> Para eliminar o viés onde vídeos mais antigos aparentam melhor desempenho apenas por acumularem visualizações por semanas,
> nosso algoritmo avalia a **Velocidade Diária (VPD - Views Por Dia)** e a **Projeção Ponderada para 28 Dias**,
> combinadas com a **Retenção Média (APV %)** e a **Taxa de Escolha (CTR %)**.

---

## 1. 🚀 Top Vídeos por Aceleração e Velocidade Algorítmica (VPD)

| # | Identificador | Título do Vídeo | Veículo | Dias Ativo | Views Totais | **Velocidade (Views/Dia)** | Proj. 28d | APV % | Trajetória | Tier |
| :-: | :--- | :--- | :--- | :-: | :-: | :-: | :-: | :-: | :---: | :-: |
"""
        for s_idx, sr in enumerate(sorted_by_velocity[:5], 1):
            s_an = sr.get("analytics", {})
            md_content += (
                f"| {s_idx} | `{sr.get('video_id')}` | {sr.get('tema', '')[:30]} | {sr.get('core_entity', '')[:16]} | "
                f"{s_an.get('exposure_days', 1.0):.1f}d | {s_an.get('views', 0):,} | **{s_an.get('views_per_day', 0.0):.1f} v/d** | "
                f"{s_an.get('projected_28d_views', 0):,} | {s_an.get('apv_pct', 0.0):.1f}% | `{s_an.get('growth_trajectory', 'STEADY_GROWTH')}` | **Tier {s_an.get('performance_tier', 'PENDING')}** |\n"
            )

        if not sorted_by_velocity:
            md_content += "| - | - | Nenhum vídeo com visualizações registradas ainda | - | - | - | - | - | - | - | - |\n"

        md_content += f"""
---

## 2. 🎯 Tabela Completa de Metadados, Métricas e Pesos de IA

| # | Identificador | Título do Vídeo | Veículo | Dias | Views | Views/Dia | APV % | CTR % | Trajetória | Tier | Pesos IA (Hook / Tech / AntiHype / WPM) |
| :-: | :--- | :--- | :--- | :-: | :-: | :-: | :-: | :-: | :---: | :-: | :--- |
"""

        for idx, r in enumerate(valid_records, 1):
            vid = r.get("video_id")
            tema = r.get("tema", "")[:32]
            car = r.get("core_entity", "")[:16]
            
            an = r.get("analytics", {})
            exp_days_str = f"{an.get('exposure_days', 1.0):.1f}d"
            views_str = f"{an.get('views', 0):,}" if an.get('views') else "[0]"
            vpd_str = f"{an.get('views_per_day', 0.0):.1f}" if an.get('views') else "-"
            apv_str = f"{an.get('apv_pct'):.1f}%" if an.get('apv_pct') is not None else "-"
            ctr_str = f"{an.get('ctr_pct'):.1f}%" if an.get('ctr_pct') is not None else "-"
            traj_str = an.get("growth_trajectory", "-")
            tier_str = f"**Tier {an.get('performance_tier')}**" if an.get('performance_tier') not in (None, "PENDING") else "PENDING"
            
            gw = r.get("generation_weights", weights)
            weights_summary = f"{gw.get('hook_curiosity_gap_weight', 0.95):.2f}/{gw.get('technical_depth_weight', 0.92):.2f}/{gw.get('anti_hype_precision_weight', 0.90):.2f}/{gw.get('pacing_cadence_wpm', 185):.0f}"

            md_content += f"| {idx} | `{vid}` | {tema} | {car} | {exp_days_str} | {views_str} | {vpd_str} | {apv_str} | {ctr_str} | `{traj_str}` | {tier_str} | `{weights_summary}` |\n"

        if not valid_records:
            md_content += "| - | - | Nenhum vídeo válido encontrado | - | - | - | - | - | - | - | - | - |\n"

        if ignored_records:
            md_content += f"""
---

## 3. ⚠️ Vídeos Desconsiderados por Segurança (Metadata Perdido / Corrompido)

| # | Identificador | Lote / Arquivo | Motivo do Descarte |
| :-: | :--- | :--- | :--- |
"""
            for i_idx, ir in enumerate(ignored_records, 1):
                md_content += f"| {i_idx} | `{ir.get('video_id')}` | `{ir.get('checkpoint_file', 'checkpoint.json')}` | Metadata corrompido / incompleto |\n"

        md_content += f"""
---

## 4. 🧠 Status de Convergência da IA (Vetor Ativo Recalibrado)

- **`hook_curiosity_gap_weight`:** `{weights.get('hook_curiosity_gap_weight', 0.95):.2f}`
- **`technical_depth_weight`:** `{weights.get('technical_depth_weight', 0.92):.2f}`
- **`anti_hype_precision_weight`:** `{weights.get('anti_hype_precision_weight', 0.90):.2f}`
- **`pacing_cadence_wpm`:** `{weights.get('pacing_cadence_wpm', 185.0):.0f} WPM`
- **`broll_cut_frequency_sec`:** `{weights.get('broll_cut_frequency_sec', 2.8):.2f}s`

*Arquivo gerado e sincronizado automaticamente por `AlgorithmMemorySystem`.*
"""
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        app_logger.info(f"[AlgorithmMemory] Arquivo Markdown de métricas exportado na raiz: {target_file}")
        return target_file

    def get_prompt_guidance(self) -> str:
        """
        Gera o bloco de instruções e pesos auxiliares formatado para injeção
        nos prompts dos agentes (Proposer, Dissertation e Director).
        """
        weights = self.load_weights()
        return (
            f"\n[MEMÓRIA DE INTELIGÊNCIA DO ALGORITMO (.MD) & PESOS AUXILIARES ATIVOS]:\n"
            f"- Intensidade do Gancho Inicial (0-3s): {weights.get('hook_curiosity_gap_weight', 0.95):.2f}/1.0 (Palavra de chamariz de alto impacto obrigatória nos primeiros 3s).\n"
            f"- Profundidade Técnica e Física: {weights.get('technical_depth_weight', 0.92):.2f}/1.0 (Mecânica real, números exatos de telemetria, rpm, downforce e cavalaria).\n"
            f"- Tolerância Zero a Buzzwords Vazias (Anti-Hype): {weights.get('anti_hype_precision_weight', 0.90):.2f}/1.0 (PROIBIDO usar adjetivos vazios ou termos sensacionalistas no meio do vídeo. Preencha com conteúdo mecânico puro).\n"
            f"- Cadência de Pacing: ~{weights.get('pacing_cadence_wpm', 185.0):.0f} WPM a 1.25x (Frases concisas, diretas e com alta densidade informacional).\n"
            f"- Frequência Média de Tomadas: 1 corte a cada {weights.get('broll_cut_frequency_sec', 2.8):.1f}s (Cenas curtas com termos de busca em inglês focados em som e ação 4K)."
        )

# Instância singleton padrão do sistema de memória algorítmica
DEFAULT_ALGORITHM_MEMORY = AlgorithmMemorySystem()

