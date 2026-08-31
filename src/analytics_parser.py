"""
Módulo de Ingestão e Processamento de Relatórios do YouTube Analytics (.zip).
Totalmente imune ao viés de exposição temporal (vídeos antigos vs recentes).
Realiza:
1. Descoberta automática de arquivos .zip em /analytics.
2. Leitura resiliente multi-encoding (UTF-8, UTF-8-BOM, CP1252, Latin1).
3. Normalização temporal de idade (Publish Time vs Janela de 28 Dias).
4. Cálculo de Velocidade Diária (VPD - Views Por Dia) e Volume Projetado em 28 Dias.
5. Análise de Trajetória e Momentum a partir de séries temporais diárias (Chart data.csv).
6. Casamento inteligente com os vídeos gerados localmente.
"""

import os
import re
import csv
import io
import glob
import time
import math
import zipfile
import difflib
import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

try:
    from .logger import app_logger, LogSpan
    from .deduplication import sanitize_and_cap_title, extract_canonical_entity
except ImportError:
    from logger import app_logger, LogSpan
    from deduplication import sanitize_and_cap_title, extract_canonical_entity

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYTICS_DIR = os.path.join(PROJECT_ROOT, "analytics")

MONTHS_MAP = {
    "jan": 1, "feb": 2, "fev": 2, "mar": 3, "apr": 4, "abr": 4,
    "may": 5, "mai": 5, "jun": 6, "jul": 7, "aug": 8, "ago": 8,
    "sep": 9, "set": 9, "oct": 10, "out": 10, "nov": 11, "dec": 12, "dez": 12
}

COLUMN_ALIASES: Dict[str, List[str]] = {
    "title": ["titulo_do_video", "título_do_vídeo", "video_title", "title", "titulo", "título"],
    "youtube_id": ["conteudo", "conteúdo", "content", "video_id", "id_do_video", "id_do_vídeo", "video", "vídeo"],
    "publish_time": ["horario_de_publicacao_do_video", "horário_de_publicação_do_vídeo", "video_publish_time", "publish_time", "data_de_publicacao", "publish_date"],
    "duration_sec": ["duracao", "duração", "duration", "video_duration_seconds", "duração_do_vídeo_segundos", "video_duration"],
    "views": ["visualizacoes", "visualizações", "views", "views_from_youtube_shorts_feed", "visualizações_do_feed_dos_shorts"],
    "watch_time_hours": ["tempo_de_exibicao_horas", "tempo_de_exibição_horas", "watch_time_hours", "watch_time"],
    "subscribers": ["inscritos", "subscribers", "inscricoes", "inscrições", "subscribers_gained", "inscrições_ganhas"],
    "impressions": ["impressoes", "impressões", "impressions"],
    "ctr_pct": ["taxa_de_cliques_de_impressoes", "taxa_de_cliques_de_impressões", "taxa_de_cliques_das_impressões", "impressions_click_through_rate", "impressions_ctr", "ctr"],
    "apv_pct": ["porcentagem_media_visualizada", "porcentagem_média_visualizada", "average_percentage_viewed", "apv", "media_de_visualizacao"],
    "retention_3s_pct": ["visualizado_em_vez_de_ignorado", "viewed_vs_swiped_away", "shown_in_feed", "exibições_no_feed"],
    "likes": ["marcacoes_gostei", "marcações_gostei", "likes", "curtidas", "gostei"],
    "comments": ["comentarios_adicionados", "comentários_adicionados", "comments_added", "comments", "comentarios", "comentários"],
    "shares": ["compartilhamentos", "shares"]
}

def normalize_column_name(col_name: str) -> str:
    """Normaliza nome de coluna para casamento agnóstico a acentuação, maiúsculas e pontuação."""
    c = col_name.lower().strip()
    c = c.replace("\xad", "") # remove soft-hyphen
    c = re.sub(r"[^\w\s]", " ", c)
    c = re.sub(r"\s+", "_", c).strip("_")
    
    # 1. Correspondência exata primeiro
    for standard_key, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            clean_alias = re.sub(r"[^\w\s]", " ", alias.lower()).strip().replace(" ", "_")
            if c == clean_alias:
                return standard_key

    # 2. Correspondência por prefixo
    for standard_key, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            clean_alias = re.sub(r"[^\w\s]", " ", alias.lower()).strip().replace(" ", "_")
            if c.startswith(clean_alias):
                return standard_key
    return c

def parse_float_safe(val: Any) -> Optional[float]:
    """Converte valor para float lidando com formatação brasileira e americana."""
    if val is None:
        return None
    s = str(val).strip().replace("%", "").replace(" ", "")
    if not s or s == "-":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def parse_int_safe(val: Any) -> int:
    """Converte valor para int com segurança."""
    if val is None:
        return 0
    s = str(val).strip().replace(" ", "")
    if not s or s == "-":
        return 0
    mult = 1
    if s.lower().endswith("k"):
        mult = 1_000
        s = s[:-1].replace(",", ".")
    elif s.lower().endswith("m"):
        mult = 1_000_000
        s = s[:-1].replace(",", ".")
    else:
        s = s.replace(".", "").replace(",", "")
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0

def clean_youtube_title(title: str) -> str:
    """Remove hashtags, emojis e menções de canais de um título do YouTube para casamento."""
    t = re.sub(r"#\w+", "", title)
    t = re.sub(r"[🏎️🔥⚡🏆🚀💥✨💬🔔]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def parse_publish_date(date_str: Any) -> Optional[datetime.date]:
    """Interpreta datas de publicação em múltiplos idiomas e formatos (ISO, EN, PT)."""
    if not date_str or not str(date_str).strip():
        return None
    s = str(date_str).strip().lower()

    # Formato ISO: YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m_iso:
        try:
            return datetime.date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except ValueError:
            pass

    # Formato Inglês: "Aug 27, 2026"
    m_en = re.search(r"([a-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})", s)
    if m_en:
        m_name = m_en.group(1)[:3]
        month = MONTHS_MAP.get(m_name)
        if month:
            try:
                return datetime.date(int(m_en.group(3)), month, int(m_en.group(2)))
            except ValueError:
                pass

    # Formato Português: "27 de ago. de 2026"
    m_pt = re.search(r"(\d{1,2})\s+de\s+([a-z]{3,9})\.?\s+de\s+(\d{4})", s)
    if m_pt:
        m_name = m_pt.group(2)[:3]
        month = MONTHS_MAP.get(m_name)
        if month:
            try:
                return datetime.date(int(m_pt.group(3)), month, int(m_pt.group(1)))
            except ValueError:
                pass

    # Formato Barra: "27/08/2026"
    m_slash = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m_slash:
        try:
            return datetime.date(int(m_slash.group(3)), int(m_slash.group(2)), int(m_slash.group(1)))
        except ValueError:
            pass

    return None

def extract_reference_date_from_filename(filename: str) -> datetime.date:
    """Extrai a data final da janela de exportação a partir do nome do arquivo (ex: Content 2026-07-30_2026-08-27.zip)."""
    m = re.findall(r"\d{4}-\d{2}-\d{2}", filename)
    if len(m) >= 2:
        try:
            parts = m[1].split("-")
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            pass
    elif len(m) == 1:
        try:
            parts = m[0].split("-")
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            pass
    return datetime.date.today()

class YouTubeAnalyticsZipParser:
    """
    Parser avançado e normalizador temporal para relatórios .zip do YouTube Studio.
    """

    def __init__(self, analytics_dir: Optional[str] = None):
        self.analytics_dir = os.path.abspath(analytics_dir or ANALYTICS_DIR)
        os.makedirs(self.analytics_dir, exist_ok=True)

    def find_latest_zip(self) -> Optional[str]:
        """Localiza o arquivo .zip mais recente dentro da pasta /analytics."""
        zips = glob.glob(os.path.join(self.analytics_dir, "*.zip"))
        if not zips:
            return None
        zips.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return zips[0]

    def list_all_zips(self) -> List[str]:
        """Lista todos os arquivos .zip presentes na pasta /analytics."""
        zips = glob.glob(os.path.join(self.analytics_dir, "*.zip"))
        zips.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return zips

    def parse_zip_content(self, zip_path: str) -> List[Dict[str, Any]]:
        """
        Lê o arquivo .zip em memória, decodifica a tabela principal e as séries temporais diárias,
        e calcula métricas ajustadas pelo tempo de exposição (VPD e Projeção 28d).
        """
        if not os.path.exists(zip_path):
            app_logger.error(f"[AnalyticsParser] Arquivo não encontrado: {zip_path}")
            return []

        app_logger.info(f"[AnalyticsParser] Lendo pacote de analytics: {zip_path}")
        ref_date = extract_reference_date_from_filename(os.path.basename(zip_path))
        results = []

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                namelist = z.namelist()
                
                # 1. Extração da série temporal diária (Chart data.csv) se disponível
                timeseries_by_video: Dict[str, Dict[str, int]] = {}
                chart_csv_name = next((n for n in namelist if "chart" in n.lower() and n.lower().endswith(".csv")), None)
                if chart_csv_name:
                    chart_bytes = z.read(chart_csv_name)
                    timeseries_by_video = self._parse_chart_timeseries(chart_bytes)

                # 2. Localização da tabela principal de dados (Table data.csv)
                target_csv_name = None
                for candidate in ["Table data.csv", "Dados da tabela.csv", "Content.csv", "Conteúdo.csv", "Video.csv", "Vídeo.csv"]:
                    for n in namelist:
                        if n.lower().endswith(candidate.lower()):
                            target_csv_name = n
                            break
                    if target_csv_name:
                        break

                if not target_csv_name:
                    for n in namelist:
                        if n.lower().endswith(".csv") and "totals" not in n.lower() and "chart" not in n.lower():
                            target_csv_name = n
                            break

                if not target_csv_name:
                    target_csv_name = namelist[0] if namelist else None

                if not target_csv_name:
                    app_logger.warning(f"[AnalyticsParser] Nenhum CSV válido no ZIP {zip_path}")
                    return []

                raw_bytes = z.read(target_csv_name)
                results = self._parse_table_csv_bytes(
                    raw_bytes=raw_bytes,
                    ref_date=ref_date,
                    timeseries_map=timeseries_by_video,
                    source_name=f"{os.path.basename(zip_path)}/{target_csv_name}"
                )

        except Exception as e:
            app_logger.error(f"[AnalyticsParser] Erro ao processar ZIP {zip_path}: {str(e)}")

        return results

    def _parse_chart_timeseries(self, chart_bytes: bytes) -> Dict[str, Dict[str, int]]:
        """Extrai o histórico diário de visualizações de cada vídeo."""
        text = self._decode_bytes_safe(chart_bytes)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return {}

        headers = [normalize_column_name(h) for h in rows[0]]
        date_idx = headers.index("data") if "data" in headers else 0
        id_idx = headers.index("youtube_id") if "youtube_id" in headers else 1
        views_idx = headers.index("views") if "views" in headers else (len(headers) - 1)

        timeseries: Dict[str, Dict[str, int]] = {}
        for row in rows[1:]:
            if len(row) > max(date_idx, id_idx, views_idx):
                d_str = row[date_idx].strip()
                v_id = row[id_idx].strip()
                v_count = parse_int_safe(row[views_idx])
                if v_id and d_str:
                    timeseries.setdefault(v_id, {})[d_str] = v_count
        return timeseries

    def _decode_bytes_safe(self, raw_bytes: bytes) -> str:
        """Decodifica bytes tentando múltiplos encodings de forma resiliente."""
        for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1", "iso-8859-1"]:
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw_bytes.decode("utf-8", errors="replace")

    def _parse_table_csv_bytes(
        self,
        raw_bytes: bytes,
        ref_date: datetime.date,
        timeseries_map: Dict[str, Dict[str, int]],
        source_name: str = ""
    ) -> List[Dict[str, Any]]:
        """Decodifica e processa a tabela principal com normalização temporal rigorosa."""
        text = self._decode_bytes_safe(raw_bytes)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return []

        header_row = rows[0]
        normalized_headers = [normalize_column_name(h) for h in header_row]

        parsed_items = []
        for row in rows[1:]:
            if not row or not any(row):
                continue
            
            first_val = str(row[0]).strip().lower()
            if first_val in ("total", "totais", "totals", "sum"):
                continue

            row_dict = {}
            for col_idx, col_name in enumerate(normalized_headers):
                if col_idx < len(row):
                    row_dict[col_name] = row[col_idx].strip()

            yt_id = row_dict.get("youtube_id", "")
            raw_title = row_dict.get("title", "")
            if not raw_title and yt_id:
                raw_title = yt_id

            if not raw_title:
                continue

            clean_title = clean_youtube_title(raw_title)
            views = parse_int_safe(row_dict.get("views"))
            watch_time_h = parse_float_safe(row_dict.get("watch_time_hours"))
            duration_sec = parse_float_safe(row_dict.get("duration_sec"))
            subscribers = parse_int_safe(row_dict.get("subscribers"))
            impressions = parse_int_safe(row_dict.get("impressions"))
            ctr_pct = parse_float_safe(row_dict.get("ctr_pct"))
            apv_pct = parse_float_safe(row_dict.get("apv_pct"))
            retention_3s = parse_float_safe(row_dict.get("retention_3s_pct"))
            likes = parse_int_safe(row_dict.get("likes"))
            comments = parse_int_safe(row_dict.get("comments"))
            shares = parse_int_safe(row_dict.get("shares"))

            # 1. Normalização e cálculo de dias de exposição
            pub_date_raw = row_dict.get("publish_time", "")
            pub_date = parse_publish_date(pub_date_raw)
            
            if pub_date:
                days_diff = (ref_date - pub_date).days
                exposure_days = max(1.0, float(days_diff + 1))
            else:
                exposure_days = 1.0 # fallback conservador para vídeos recentes

            exposure_days = min(28.0, exposure_days)

            # 2. Métricas de Velocidade e Projeção Temporal Normalizada
            views_per_day = round(views / exposure_days, 2)
            
            # Curva logarítmica de decaimento típica do Shorts
            if exposure_days < 28.0:
                projected_28d_views = int(round(views * (1.0 + 1.2 * math.log(max(1.0, 28.0 / exposure_days)))))
            else:
                projected_28d_views = views

            # 3. Derivação de APV % caso não venha explícito no CSV
            if apv_pct is None and watch_time_h is not None and views > 0 and duration_sec and duration_sec > 0:
                avg_view_duration_sec = (watch_time_h * 3600.0) / float(views)
                derived_apv = (avg_view_duration_sec / float(duration_sec)) * 100.0
                apv_pct = round(min(100.0, derived_apv), 2)

            # 4. Análise de Trajetória e Momentum a partir de dados diários
            v_daily = timeseries_map.get(yt_id, {})
            if views_per_day >= 200.0 and exposure_days <= 2.0:
                trajectory = "VIRAL_BURST"
            elif views_per_day >= 50.0:
                trajectory = "ACCELERATING"
            elif views_per_day >= 15.0:
                trajectory = "STEADY_GROWTH"
            elif exposure_days >= 4.0 and views_per_day < 5.0:
                trajectory = "PLATEAU"
            elif views < 10 and exposure_days <= 2.0:
                trajectory = "INCUBATING"
            else:
                trajectory = "STEADY_GROWTH"

            parsed_items.append({
                "youtube_id": yt_id,
                "raw_title": raw_title,
                "clean_title": clean_title,
                "publish_date": pub_date.isoformat() if pub_date else None,
                "exposure_days": exposure_days,
                "views": views,
                "views_per_day": views_per_day,
                "projected_28d_views": projected_28d_views,
                "growth_trajectory": trajectory,
                "watch_time_hours": watch_time_h,
                "duration_seconds": duration_sec,
                "subscribers": subscribers,
                "impressions": impressions,
                "ctr_pct": ctr_pct,
                "apv_pct": apv_pct,
                "retention_3s_pct": retention_3s,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "source": source_name
            })

        app_logger.info(f"[AnalyticsParser] Extraídos {len(parsed_items)} registros com normalização de idade de {source_name}")
        return parsed_items

    def match_youtube_to_local_records(
        self,
        yt_items: List[Dict[str, Any]],
        local_records: List[Dict[str, Any]],
        sim_threshold: float = 0.55
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Realiza o casamento inteligente e probabilístico entre os vídeos do YouTube
        e os registros do histórico local de geração.
        """
        matched = []
        unmatched = []

        for yt in yt_items:
            yt_title = yt["clean_title"]
            yt_raw = yt["raw_title"]
            yt_entity = extract_canonical_entity(yt_title).lower()
            yt_dur = yt.get("duration_seconds")

            best_match = None
            best_score = 0.0
            best_reason = ""

            for loc in local_records:
                loc_id = loc.get("video_id", "")
                loc_title = loc.get("tema") or loc.get("titulo") or ""
                loc_entity = (loc.get("core_entity") or extract_canonical_entity(loc_title)).lower()
                loc_dur = loc.get("duracao_segundos", 0.0)

                # 1. Correspondência exata de ID ou título limpo
                if yt_raw.strip() == loc_title.strip() or yt_title.strip() == loc_title.strip():
                    best_match = loc
                    best_score = 1.0
                    best_reason = "Título idêntico"
                    break

                # 2. Similaridade difflib no título
                text_sim = difflib.SequenceMatcher(None, yt_title.lower(), loc_title.lower()).ratio()
                
                # 3. Sobreposição de entidade de veículo
                entity_match = False
                if yt_entity and loc_entity:
                    if yt_entity in loc_title.lower() or loc_entity in yt_title.lower():
                        entity_match = True
                    elif difflib.SequenceMatcher(None, yt_entity, loc_entity).ratio() >= 0.70:
                        entity_match = True

                # 4. Proximidade de duração (tolerância de +/- 5s)
                dur_match = False
                if yt_dur and loc_dur and abs(yt_dur - loc_dur) <= 6.0:
                    dur_match = True

                # Pontuação combinada ponderada
                combined_score = text_sim * 0.60
                if entity_match:
                    combined_score += 0.30
                if dur_match:
                    combined_score += 0.10

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = loc
                    best_reason = f"Similaridade {combined_score:.0%} (Entidade: {entity_match}, Dur: {dur_match})"

            if best_match and best_score >= sim_threshold:
                matched.append({
                    "local_record": best_match,
                    "youtube_data": yt,
                    "match_score": best_score,
                    "match_reason": best_reason
                })
            else:
                unmatched.append(yt)

        return matched, unmatched

DEFAULT_ANALYTICS_PARSER = YouTubeAnalyticsZipParser()
