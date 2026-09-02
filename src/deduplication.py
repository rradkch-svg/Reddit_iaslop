"""
Módulo de Deduplicação Heurística de Contexto e Sanitização de Histórias do Reddit (Reddit Minute).
Garante:
1. Títulos com teto estrito de 100 caracteres (<= 100 dígitos) e sem clichês.
2. Deduplicação multi-fatorial de histórias (mesmo autor, mesma URL, mesmo enredo/entidade, sobreposição de palavras-chave).
3. Detecção heurística de conflitos semânticos análogos (mesmo arquétipo de conflito + mesmos atores centrais),
   impedindo a repetição de histórias mesmo quando formuladas com variações superficiais de vocabulário.
"""

import re
import difflib
from typing import Dict, Any, List, Set, Tuple, Optional, Union

# =============================================================================
# Arquétipos Narrativos e Domínios de Conflito do Reddit
# =============================================================================
REDDIT_CONFLICT_DOMAINS: Dict[str, List[str]] = {
    "WORKPLACE_MALICIOUS_COMPLIANCE": [
        "boss", "manager", "handbook", "overtime", "shift", "clock out", "clocked out",
        "insubordination", "fired", "hr", "human resources", "severance", "micromanager",
        "promotion", "paycut", "raise", "salary", "pto", "vacation", "wfh", "return to office",
        "cubicle", "employee", "director", "executive", "vp", "billing", "contractor"
    ],
    "HOUSING_LANDLORD_TENANT": [
        "landlord", "tenant", "deposit", "security deposit", "rent", "lease", "eviction",
        "evicted", "repairs", "apartment", "unit", "landlord tenant", "property manager",
        "inspector", "damages", "water leak", "mold", "rent increase"
    ],
    "LEGAL_COURT_DAMAGES": [
        "small claims", "lawyer", "lawsuit", "sue", "sued", "court", "judge", "settlement",
        "damages", "attorney", "subpoena", "legal action", "treble damages", "judgment",
        "deposition", "police", "officer", "fine", "citation", "statute"
    ],
    "FAMILY_INHERITANCE_WEDDING": [
        "in-law", "mother-in-law", "father-in-law", "mil", "fil", "wedding", "bride",
        "groom", "inheritance", "will", "estate", "sibling", "parents", "custody",
        "trust fund", "golden child", "stepmom", "stepdad", "ex-wife", "ex-husband"
    ],
    "NEIGHBORHOOD_HOA_BOUNDARY": [
        "hoa", "homeowners association", "neighbor", "fence", "property line", "easement",
        "parking", "towing", "towed", "driveway", "yard", "tree", "property boundary",
        "noise complaint", "hoa board", "hoa president"
    ],
    "FINANCIAL_INDEPENDENCE_SCAM": [
        "scam", "debt", "credit", "taxes", "tax fraud", "irs", "refund", "bank",
        "financial", "audit", "forensic audit", "embezzlement", "wire fraud", "stolen"
    ],
    "PETTY_REVENGE_ENTITLED": [
        "karen", "entitled", "customer", "parking spot", "queue", "cut in line",
        "revenge", "petty", "airplane", "seat", "flight", "grocery", "restaurant"
    ]
}

# Stopwords em inglês e português para filtragem conceitual
STOPWORDS_EN_PT: Set[str] = {
    # English stopwords
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "how", "why",
    "what", "when", "where", "who", "which", "this", "that", "these", "those", "my",
    "your", "his", "her", "its", "our", "their", "i", "you", "he", "she", "it",
    "we", "they", "me", "him", "her", "us", "them", "so", "as", "if", "not", "all",
    "any", "out", "very", "just", "got", "get", "told", "said", "one", "two", "back",
    "off", "down", "then", "now", "here", "there", "even", "only", "would", "could",
    "should", "story", "stories", "reddit", "post", "update", "part", "chapter", "full",
    # Portuguese stopwords
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "da", "do", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "como", "que", "se", "seu",
    "sua", "seus", "suas", "ao", "aos", "pelo", "pela", "pelos", "pelas", "sem", "sob"
}

# Sufixos e clichês proibidos em títulos do Reddit
FORBIDDEN_TITLE_PATTERNS: List[str] = [
    r"\|\s*Reddit\s+Stories\b",
    r"-\s*Reddit\s+Stories\b",
    r"\|\s*Reddit\s+Minute\b",
    r"-\s*Reddit\s+Minute\b",
    r"\|\s*Segredos?\s+da\s+Engenharia\b",
    r"-\s*Segredos?\s+da\s+Engenharia\b",
    r"\[\s*30\s*MIN\s*FULL\s*STORY\s*\]",
    r"\[\s*25\s*MIN\s*FULL\s*STORY\s*\]",
    r"#Shorts\b",
    r"#RedditStories\b",
    r"🔥\s*",
    r"⚡\s*",
    r"👉\s*"
]

def sanitize_and_cap_title(title: str, max_length: int = 100) -> str:
    """
    Limpa sufixos de clichês (ex: '| Reddit Stories', tags, emojis prefixados)
    e garante que o título do vídeo NUNCA tenha mais de max_length caracteres (padrão 100).
    Realiza quebra elegante na última palavra para nunca cortar letras no meio.
    """
    if not title:
        return ""

    cleaned = str(title).strip()

    # 1. Remove sufixos e prefixos proibidos
    for pattern in FORBIDDEN_TITLE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Normaliza pontuações soltas e espaços múltiplos
    cleaned = re.sub(r"\s*\|\s*$", "", cleaned)
    cleaned = re.sub(r"\s*-\s*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 3. Teto estrito de 100 caracteres com truncamento em limite de palavra
    if len(cleaned) > max_length:
        truncated = cleaned[:max_length].strip()
        last_space = truncated.rfind(" ")
        if last_space > int(max_length * 0.70):
            cleaned = truncated[:last_space].rstrip(",;:-. ")
        else:
            cleaned = truncated.rstrip(",;:-. ")

    return cleaned

def extract_canonical_entity(text: str) -> str:
    """
    Extrai e normaliza o ator/entidade central do conflito (ex: landlord, manager, neighbor, hoa, mother-in-law),
    removendo marcadores de subreddits (AITA, WIBTA, TIFU) e adjetivação.
    """
    if not text:
        return ""

    # Remove prefixos clássicos do Reddit
    cleaned = re.sub(
        r"^(AITA\s+(?:for|if)|AITAH\s+(?:for|if)|WIBTA\s+(?:for|if)|TIFU\s+by|Update\s*:?|Part\s*\d+\s*:?)\s*",
        "", str(text).strip(), flags=re.IGNORECASE
    )

    t_low = cleaned.lower()
    
    # Entidades canônicas mapeadas prioritariamente
    core_actors = [
        "mother-in-law", "father-in-law", "sister-in-law", "brother-in-law",
        "landlord", "property manager", "tenant", "roommate",
        "micromanager", "boss", "manager", "executive", "director", "supervisor",
        "coworker", "colleague", "employee", "contractor",
        "neighbor", "hoa president", "hoa board", "hoa",
        "bride", "groom", "in-laws", "sibling", "brother", "sister",
        "client", "customer", "lawyer", "police"
    ]
    for actor in core_actors:
        if re.search(rf"\b{re.escape(actor)}\b", t_low):
            return actor

    # Fallback: primeiras palavras significativas
    words = [w.strip() for w in re.sub(r"[^\w\s\-]", " ", cleaned).split() if w.lower() not in STOPWORDS_EN_PT and len(w) > 2]
    return " ".join(words[:3]).strip() if words else cleaned[:30].strip()

def classify_reddit_domains(text: str) -> List[str]:
    """Identifica quais domínios e arquétipos narrativos estão presentes no texto."""
    if not text:
        return []
    t_low = text.lower()
    matched = []
    for domain, keywords in REDDIT_CONFLICT_DOMAINS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", t_low):
                if domain not in matched:
                    matched.append(domain)
                break
    return matched

def extract_semantic_stems(text: str) -> Set[str]:
    """Extrai conjunto de tokens conceituais significativos em minúsculas (sem stopwords)."""
    if not text:
        return set()
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [w.strip() for w in clean.split() if len(w.strip()) > 2]
    return {w for w in tokens if w not in STOPWORDS_EN_PT}

class ContextualTopicAuditor:
    """
    Motor Heurístico de Auditoria e Deduplicação Contextual para o Reddit Story Studio.
    Avalia novos candidatos contra a base histórica de vídeos sob 6 dimensões:
    1. Autor Único: Bloqueia posts repetidos do mesmo autor (`author` ou `u/author`).
    2. URL/ID de Post: Bloqueia submissões com mesma URL ou identificador.
    3. Similaridade Textual de Título: SequenceMatcher com teto de 60%.
    4. Entidade + Domínio de Conflito: Bloqueia mesmo ator central no mesmo arquétipo narrativo.
    5. Jaccard de Stems Semânticos: Mede interseção lexical de enredo (teto de 45%).
    6. Similaridade de Corpo da História: Mede sobreposição de fatos no texto completo.
    """

    def __init__(self, title_sim_threshold: float = 0.60, jaccard_threshold: float = 0.45):
        self.title_sim_threshold = title_sim_threshold
        self.jaccard_threshold = jaccard_threshold

    def evaluate_candidate(
        self,
        candidate_topic: Union[str, Dict[str, Any]],
        existing_items: List[Dict[str, Any]]
    ) -> Tuple[bool, float, str]:
        """
        Avalia se a história proposta é uma duplicata de alguma história já registrada na Blacklist.
        """
        if not candidate_topic:
            return False, 0.0, "Tema vazio"

        cand_dict = candidate_topic if isinstance(candidate_topic, dict) else {"tema": str(candidate_topic)}
        cand_title = cand_dict.get("tema") or cand_dict.get("title") or cand_dict.get("titulo") or ""
        cand_title = sanitize_and_cap_title(cand_title)
        cand_author = (cand_dict.get("author") or "").strip().lower()
        cand_url = (cand_dict.get("url") or "").strip().lower()
        cand_sub = (cand_dict.get("subreddit") or "").strip().lower()
        cand_body = cand_dict.get("body") or cand_dict.get("explicacao_tecnica") or cand_dict.get("hook") or ""

        cand_full = f"{cand_title} {cand_body}".strip()
        cand_entity = cand_dict.get("core_entity") or extract_canonical_entity(cand_title)
        cand_domains = classify_reddit_domains(cand_full)
        cand_stems = extract_semantic_stems(cand_title)
        cand_body_stems = extract_semantic_stems(cand_body)

        for existing in existing_items:
            ex_title = existing.get("tema") or existing.get("title") or existing.get("titulo") or ""
            ex_title = sanitize_and_cap_title(ex_title)
            ex_author = (existing.get("author") or "").strip().lower()
            ex_url = (existing.get("url") or "").strip().lower()
            ex_sub = (existing.get("subreddit") or "").strip().lower()
            ex_body = existing.get("explicacao_tecnica") or existing.get("body") or existing.get("hook") or ""
            
            ex_full = f"{ex_title} {ex_body}".strip()
            ex_entity = existing.get("core_entity") or extract_canonical_entity(ex_title)
            ex_domains = classify_reddit_domains(ex_full)
            ex_stems = extract_semantic_stems(ex_title)
            ex_body_stems = extract_semantic_stems(ex_body)

            # 1. Verificação de Autor (se não for placeholder genérico)
            if cand_author and ex_author and cand_author not in ("u/reddituser", "reddituser", "unknown", "u/unknown"):
                if cand_author == ex_author:
                    return (
                        True,
                        1.0,
                        f"Autor '{cand_author}' já possui história produzida anteriormente ('{ex_title[:45]}...')"
                    )

            # 2. Verificação de URL / Link
            if cand_url and ex_url and len(cand_url) > 10:
                if cand_url == ex_url:
                    return (
                        True,
                        1.0,
                        f"URL idêntica à história já registrada: {cand_url}"
                    )

            # 3. Similaridade Textual Direta do Título (difflib SequenceMatcher)
            text_sim = difflib.SequenceMatcher(None, cand_title.lower(), ex_title.lower()).ratio()
            if text_sim >= self.title_sim_threshold:
                return (
                    True,
                    text_sim,
                    f"Título textualmente similar ({text_sim:.0%}) ao vídeo já gravado '{ex_title}'"
                )

            # 4. Sobreposição de Entidade Canônica + Domínio de Conflito
            same_entity = (
                cand_entity and ex_entity and
                (cand_entity.lower() == ex_entity.lower() or
                 difflib.SequenceMatcher(None, cand_entity.lower(), ex_entity.lower()).ratio() >= 0.80)
            )
            domain_overlap = set(cand_domains).intersection(set(ex_domains))
            
            if same_entity and domain_overlap:
                stem_overlap = cand_stems.intersection(ex_stems)
                if len(stem_overlap) >= 2:
                    overlap_words = ", ".join(list(stem_overlap)[:4])
                    return (
                        True,
                        0.90,
                        f"Mesma entidade central ('{cand_entity}') no domínio [{', '.join(domain_overlap)}] com termos análogos ({overlap_words}) em '{ex_title}'"
                    )

            # 5. Jaccard Global de Stems do Título
            if cand_stems and ex_stems:
                overlap = cand_stems.intersection(ex_stems)
                union = cand_stems.union(ex_stems)
                jaccard = len(overlap) / len(union) if union else 0.0
                if jaccard >= self.jaccard_threshold:
                    overlap_words = ", ".join(list(overlap)[:4])
                    return (
                        True,
                        jaccard,
                        f"Alta sobreposição de palavras-chave ({jaccard:.0%}, termos: {overlap_words}) com '{ex_title}'"
                    )

            # 6. Jaccard de Corpo da História (quando disponível)
            if len(cand_body_stems) >= 15 and len(ex_body_stems) >= 15:
                b_overlap = cand_body_stems.intersection(ex_body_stems)
                b_union = cand_body_stems.union(ex_body_stems)
                b_jaccard = len(b_overlap) / len(b_union) if b_union else 0.0
                if b_jaccard >= 0.40:
                    return (
                        True,
                        b_jaccard,
                        f"Enredo e texto da história altamente sobrepostos ({b_jaccard:.0%}) ao vídeo '{ex_title}'"
                    )

        return False, 0.0, "Tema inédito e aprovado"

DEFAULT_CONTEXTUAL_AUDITOR = ContextualTopicAuditor()
