"""
Módulo de Deduplicação Heurística de Contexto e Sanitização de Títulos Automotivos.
Garante:
1. Títulos com teto estrito de 100 caracteres (<= 100 dígitos).
2. Remoção absoluta de sufixos clichês como '| Segredos da Engenharia'.
3. Detecção heurística de duplicatas contextuais (mesmo veículo + mesmo domínio mecânico ou tema semântico),
   impedindo a repetição de assuntos mesmo quando os títulos são formulados com palavras completamente distintas.
"""

import re
import difflib
from typing import Dict, Any, List, Set, Tuple, Optional, Union

# Dicionário de taxonomia de domínios e subsistemas de engenharia automotiva
TECHNICAL_DOMAINS: Dict[str, List[str]] = {
    "AERODINAMICA_DOWNFORCE": [
        "downforce", "asa", "aero", "aerodinamica", "arrasto", "difusor", "venturi",
        "efeito solo", "drs", "flaps", "vortex", "ground effect", "sustentacao",
        "teto", "duto", "spoiler", "splitter", "canards"
    ],
    "SOBREALIMENTACAO_TURBO": [
        "turbo", "biturbo", "twin turbo", "twin-turbo", "supercharger", "compressor",
        "intercooler", "boost", "wastegate", "lag", "water-spray", "water spray",
        "mivec", "pressao", "pressurizacao", "blow-off", "spool"
    ],
    "MOTORIZACAO_COMBUSTAO": [
        "v10", "v12", "v8", "v6", "w16", "aspirado", "9000 rpm", "rpm", "giro",
        "som puro", "ronco", "escapamento", "coletor", "valvulas", "virabrequim",
        "bloco", "ferro", "flat-plane", "crossplane", "wankel", "4-rotor", "rotativo",
        "taxa de compressao", "cilindrada", "cilindros", "combustao", "ignicao"
    ],
    "TRANSMISSAO_DRIVETRAIN": [
        "pdk", "dupla embreagem", "dct", "cambio", "transmissao", "sequencial",
        "manual", "paddle shift", "launch control", "embreagem", "trocas",
        "arrancada", "relacao de marcha", "e-diff", "diferencial"
    ],
    "CHASSI_MATERIAIS_LEVES": [
        "fibra de carbono", "teto de carbono", "peso", "alivio", "monocoque",
        "titanio", "magnesio", "distribuicao de peso", "50-50", "centro de gravidade",
        "rigidez", "torcional", "tubular", "resina"
    ],
    "SUSPENSAO_DINAMICA": [
        "suspensao", "amortecedor", "magnetica", "bose", "multilink",
        "wishbone", "camber", "caster", "anti-roll", "eletromagnetica",
        "geometria", "estabilidade", "rolagem"
    ],
    "TRACAO_VETORIZACAO": [
        "attesa", "quattro", "awd", "4wd", "tracao integral", "diferencial",
        "vetorizacao de torque", "lsd", "torque vectoring", "torque split", "4x4"
    ],
    "FRENAGEM_TERMICA": [
        "freio", "carbono ceramica", "ceramica", "pastilhas", "calipers",
        "frenagem", "fading", "dissipacao", "pistas", "discos ventilados"
    ],
    "HISTORICO_RACING_LEMANS": [
        "le mans", "nurburgring", "grupo b", "f1", "cauda curta", "banido",
        "homologacao", "recorde", "venceu", "24 horas", "campeonato"
    ],
    "PROPULSAO_AERONAUTICA_JATO": [
        "turbina", "pos-combustao", "afterburner", "turbofan", "turbojet", "turboelice",
        "turboprop", "ramjet", "scramjet", "mach", "compressao axial", "empuxo",
        "aviacao", "caca", "blackbird", "sr-71", "concorde", "j58", "ge90", "tf34", "spitfire", "merlin"
    ],
    "PROPULSAO_MILITAR_BLINDADOS": [
        "tanque", "turbina a gas", "abrams", "m1 abrams", "leopard", "blindado",
        "maybach", "mtu", "honeywell agt1500", "panzer", "tiger", "t-90", "t-72", "blindagem"
    ],
    "MOTOCICLETAS_ALTO_GIRO": [
        "moto", "supermoto", "desmodromico", "desmodromica", "ninja h2r", "h2r",
        "panigale", "v4r", "crossplane", "16000 rpm", "yamaha r1", "hayabusa", "cbx 1000", "supercharger centrifugo"
    ],
    "PROPULSAO_ELETRICA_ALTA_TENSAO": [
        "eletrico", "inversor", "sic", "carbeto de silicio", "800v", "rotor de carbono",
        "fluxo axial", "yasa", "rimac", "nevera", "mcmurtry", "speirling", "plaid", "taycan", "torque instantaneo"
    ],
    "CICLO_DIESEL_ALTA_PRESSAO": [
        "diesel", "turbodiesel", "common rail", "bomba injetora", "cummins", "duramax",
        "powerstroke", "tdi", "r10 tdi", "r18 tdi", "pressao de injecao", "wartsila"
    ],
    "CICLO_WANKEL_ROTATIVO": [
        "wankel", "rotativo", "apex seal", "apex seals", "camara trocoidal", "13b",
        "20b", "r26b", "4 rotores", "4-rotor", "mazda 787b", "queima de oleo", "triangulo"
    ]
}

# Stopwords em português e termos vazios para filtragem contextual
STOPWORDS_PT: Set[str] = {
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "como", "que", "se", "seu", "sua", "seus", "suas",
    "ao", "aos", "pelo", "pela", "pelos", "pelas", "sem", "sob", "sobre",
    "e", "ou", "mas", "porque", "por que", "qual", "quais", "quem",
    "segredo", "segredos", "fisica", "engenharia", "mecanica", "tecnologia",
    "insana", "insano", "brutal", "incrivel", "revolucionario", "obra", "prima",
    "tudo", "nada", "mais", "menos", "muito", "pouco", "este", "esta", "esse", "essa"
}

# Sufixos e clichês proibidos em títulos
FORBIDDEN_TITLE_PATTERNS: List[str] = [
    r"\|\s*Segredos?\s+da\s+Engenharia\b",
    r"-\s*Segredos?\s+da\s+Engenharia\b",
    r"\|\s*Curiosidades?\s+Automotivas?\b",
    r"\|\s*AutoTech\b",
    r"\|\s*AI\s+Slop\b",
    r"🏎️\s*",
    r"🔥\s*",
    r"⚡\s*"
]

def sanitize_and_cap_title(title: str, max_length: int = 100) -> str:
    """
    Limpa sufixos de clichês (ex: '| Segredos da Engenharia', emojis prefixados)
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
    Extrai e normaliza a entidade veicular central (marca + modelo + chassi/geração),
    removendo adjetivação e verbos introdutórios.
    """
    if not text:
        return ""
    
    parts = text.split(":")
    main_part = parts[0] if len(parts) > 1 else text
    
    # Remove chamadas iniciais
    cleaned = re.sub(
        r"^(O Segredo d[oa]|Como funciona o|Por que o|A física d[oa]|A engenharia d[oa]|Tudo sobre o|O Motor d[oa]|A Asa d[oa]|A Suspensão d[oa]|A Insana Inovação d[oa]|A Insana Aerodinâmica d[oa]|A Insana Física d[oa]|O Sistema d[oa]|O Monstro d[oa]|O Rugido d[oa]|A Brutalidade Mecânica d[oa]|A Complexa Engenharia d[oa]|A Genialidade d[oa]|A Engenharia Implacável d[oa]|A Engenharia Secreta d[oa]|A Engenharia do|A Engenharia Absurda d[oa])\s*",
        "", main_part, flags=re.IGNORECASE
    )
    
    cleaned = re.sub(r"[^\w\s\-\.]", " ", cleaned)
    cleaned = re.sub(r"\b(e seu|e sua|no|na|com|de|da|do|dos|das|para|sobre|o|a|os|as|que|por|ser|bom|demais)\b", " ", cleaned, flags=re.IGNORECASE)
    
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return " ".join(words[:6]).strip() if words else text.strip()

def classify_technical_domains(text: str) -> List[str]:
    """
    Identifica quais domínios e sistemas mecânicos estão presentes no texto (título, hook ou explicação).
    """
    t_low = text.lower()
    matched_domains = []
    for domain, keywords in TECHNICAL_DOMAINS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", t_low):
                if domain not in matched_domains:
                    matched_domains.append(domain)
                break
    return matched_domains

def extract_semantic_stems(text: str) -> Set[str]:
    """
    Extrai o conjunto de tokens conceituais significativos (sem stopwords e com mais de 2 letras).
    """
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [w.strip() for w in clean.split() if len(w.strip()) > 2]
    return {w for w in tokens if w not in STOPWORDS_PT}

class ContextualTopicAuditor:
    """
    Motor Heurístico de Auditoria e Deduplicação Contextual.
    Compara o candidato com a base histórica de vídeos já produzidos sob 4 dimensões:
    1. Entidade Veicular / Máquina (mesmo carro ou variação direta).
    2. Domínio Técnico de Engenharia (mesmo subsistema mecânico).
    3. Sobreposição Semântica de Ação / Princípio Físico (Jaccard de Stems).
    4. Proximidade Estrutural e Textual (difflib SequenceMatcher).
    """

    def __init__(self, vehicle_sim_threshold: float = 0.70, text_sim_threshold: float = 0.65):
        self.vehicle_sim_threshold = vehicle_sim_threshold
        self.text_sim_threshold = text_sim_threshold

    def evaluate_candidate(
        self,
        candidate_topic: Union[str, Dict[str, Any]],
        existing_items: List[Dict[str, Any]]
    ) -> Tuple[bool, float, str]:
        """
        Avalia se o tema candidato é uma repetição de assunto em relação aos itens existentes.
        
        Retorna:
        - `is_duplicate` (bool): True se for duplicata contextual, False se for inédito.
        - `confidence` (float): Nível de confiança da detecção (0.0 a 1.0).
        - `reason` (str): Justificativa técnica e detalhada para rejeição ou aprovação.
        """
        if not candidate_topic:
            return False, 0.0, "Tema vazio"

        cand_title = candidate_topic.get("tema") if isinstance(candidate_topic, dict) else str(candidate_topic)
        cand_title = sanitize_and_cap_title(cand_title)
        cand_hook = candidate_topic.get("hook", "") if isinstance(candidate_topic, dict) else ""
        cand_tech = candidate_topic.get("explicacao_tecnica", "") if isinstance(candidate_topic, dict) else ""
        
        cand_full_text = f"{cand_title} {cand_hook} {cand_tech}".strip()
        cand_entity = extract_canonical_entity(cand_title)
        cand_domains = classify_technical_domains(cand_full_text)
        cand_stems = extract_semantic_stems(cand_full_text)
        cand_entity_stems = extract_semantic_stems(cand_entity)

        for existing in existing_items:
            ex_title = existing.get("tema") or existing.get("titulo") or ""
            ex_title = sanitize_and_cap_title(ex_title)
            ex_hook = existing.get("hook", "")
            ex_tech = existing.get("explicacao_tecnica") or existing.get("dissertacao_resumo") or ""
            ex_full_text = f"{ex_title} {ex_hook} {ex_tech}".strip()
            
            ex_entity = existing.get("core_entity") or extract_canonical_entity(ex_title)
            ex_domains = classify_technical_domains(ex_full_text)
            ex_stems = extract_semantic_stems(ex_full_text)
            ex_entity_stems = extract_semantic_stems(ex_entity)

            # 1. Similaridade Textual Direta (difflib)
            text_sim = difflib.SequenceMatcher(None, cand_title.lower(), ex_title.lower()).ratio()
            if text_sim >= self.text_sim_threshold:
                return (
                    True,
                    text_sim,
                    f"Título textualmente muito similar ({text_sim:.0%}) ao vídeo já gravado '{ex_title}'"
                )

            # 2. Avaliação de Entidade Veicular / Máquina
            entity_jaccard = 0.0
            if cand_entity_stems and ex_entity_stems:
                entity_overlap = cand_entity_stems.intersection(ex_entity_stems)
                entity_union = cand_entity_stems.union(ex_entity_stems)
                entity_jaccard = len(entity_overlap) / len(entity_union) if entity_union else 0.0

            entity_str_sim = difflib.SequenceMatcher(None, cand_entity.lower(), ex_entity.lower()).ratio()
            same_vehicle = (
                entity_jaccard >= self.vehicle_sim_threshold or
                entity_str_sim >= 0.78 or
                (len(cand_entity) >= 4 and cand_entity.lower() in ex_title.lower()) or
                (len(ex_entity) >= 4 and ex_entity.lower() in cand_title.lower())
            )

            # 3. Se for o mesmo veículo / máquina:
            if same_vehicle:
                # 3a. Checa sobreposição de Domínios Técnicos de Engenharia
                domain_overlap = set(cand_domains).intersection(set(ex_domains))
                if domain_overlap:
                    domain_names = ", ".join(list(domain_overlap))
                    return (
                        True,
                        0.95,
                        f"O veículo '{cand_entity}' já possui vídeo abordando o domínio mecânico [{domain_names}] em '{ex_title}'"
                    )

                # 3b. Checa sobreposição de Stems Semânticos (Ações e Componentes)
                stem_overlap = cand_stems.intersection(ex_stems) - cand_entity_stems
                if len(stem_overlap) >= 3:
                    overlap_words = ", ".join(list(stem_overlap)[:4])
                    return (
                        True,
                        0.90,
                        f"O veículo '{cand_entity}' já foi abordado com termos e conceitos mecânicos análogos ({overlap_words}) em '{ex_title}'"
                    )

                # 3c. Se for um modelo de nicho super específico sem domínio explícito, bloqueia duplicação de veículo no mesmo canal
                if len(cand_entity_stems) >= 2 and entity_jaccard >= 0.85:
                    return (
                        True,
                        0.85,
                        f"Veículo '{cand_entity}' já foi protagonista do vídeo '{ex_title}'"
                    )

            # 4. Caso os títulos sejam semanticamente quase idênticos mesmo com veículos diferentes
            stems_intersection = cand_stems.intersection(ex_stems)
            stems_union = cand_stems.union(ex_stems)
            jaccard_global = len(stems_intersection) / len(stems_union) if stems_union else 0.0
            if jaccard_global >= 0.65:
                return (
                    True,
                    jaccard_global,
                    f"Alta sobreposição temática e semântica ({jaccard_global:.0%}) com o vídeo '{ex_title}'"
                )

        return False, 0.0, "Tema 100% inédito e aprovado"

DEFAULT_CONTEXTUAL_AUDITOR = ContextualTopicAuditor()
