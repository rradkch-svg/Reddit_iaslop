"""
Módulo de Pronúncia Automotiva e Léxico Fonético Especializado.
Converte termos técnicos em inglês, marcas estrangeiras, modelos e jargões automotivos
em grafias fonéticas adaptadas ao Edge-TTS (pt-BR) para uma narração natural e fluida,
enquanto mantém o texto original para as legendas ASS exibidas na tela.
"""

import re
from typing import Dict, List, Tuple, Any, Optional

# Dicionário mestre de substituição fonética para TTS em Português Brasileiro (pt-BR)
# Mapeia termos em inglês / marcas / siglas automotivas para grafia fonética em pt-BR
AUTOMOTIVE_PHONETIC_LEXICON: Dict[str, str] = {
    # -------------------------------------------------------------------------
    # Marcas e Fabricantes Internacionais
    # -------------------------------------------------------------------------
    "porsche": "Pór-xê",
    "koenigsegg": "Kônig-zég",
    "mclaren": "Mac-Láren",
    "lamborghini": "Lam-bor-guíni",
    "ferrari": "Ferrári",
    "bugatti": "Bu-gáti",
    "chevrolet": "Xevrolê",
    "corvette": "Corvét",
    "dodge": "Dódji",
    "viper": "Váiper",
    "hellcat": "Rél-quét",
    "demon": "Dímon",
    "shelby": "Xélbi",
    "mustang": "Mustâng",
    "aston martin": "Éston Mártin",
    "aston": "Éston",
    "martin": "Mártin",
    "alfa romeo": "Álfa Romêu",
    "pagani": "Pa-guáni",
    "rimac": "Rí-mats",
    "maserati": "Ma-ze-ráti",
    "lexus": "Léksus",
    "subaru": "Su-báru",
    "nissan": "Ní-ssan",
    "skyline": "Scái-láin",
    "toyota": "Toióta",
    "supra": "Súpra",
    "mazda": "Mázda",
    "honda": "Rônda",
    "audi": "Áudi",
    "bmw": "Bê-Eme-Dáblio",
    "amg": "A-Eme-Guê",
    "mercedes": "Mer-cêdes",
    "mercedes-amg": "Mer-cêdes A-Eme-Guê",
    "volkswagen": "Fôlks-vághen",
    "cadillac": "Cá-di-lac",
    "jaguar": "Djá-guar",
    "peugeot": "Pê-jô",
    "renault": "Re-nô",
    "citroen": "Ci-tro-ên",
    "citroën": "Ci-tro-ên",
    "lotus": "Lótus",
    "yangwang": "Iâng-uâng",
    "zeekr": "Zí-ker",
    "nio": "Ní-o",
    "xpeng": "Eks-pêng",
    "lucid": "Lú-cid",
    "rivian": "Rí-vian",

    # -------------------------------------------------------------------------
    # Motores, Sobrealimentação e Componentes Mecânicos
    # -------------------------------------------------------------------------
    "twin-turbo": "tuin târbo",
    "twin turbo": "tuin târbo",
    "twinturbo": "tuin târbo",
    "bi-turbo": "bi-târbo",
    "biturbo": "bi-târbo",
    "single turbo": "síngol târbo",
    "quad-turbo": "quód târbo",
    "quad turbo": "quód târbo",
    "turbocharger": "târbo-tchárdjer",
    "turbochargers": "târbo-tchárdjers",
    "supercharger": "súper-tchárdjer",
    "superchargers": "súper-tchárdjers",
    "supercharged": "súper-tchárdjed",
    "turbocharged": "târbo-tchárdjed",
    "intercooler": "ínter-cúler",
    "intercoolers": "ínter-cúlers",
    "wastegate": "uéist-gueit",
    "wastegates": "uéist-gueits",
    "blow-off": "blôu-óf",
    "blow off": "blôu-óf",
    "blowoff": "blôu-óf",
    "gearbox": "guíar-bóks",
    "paddle shift": "pédol shift",
    "paddle shifts": "pédol shifts",
    "paddle-shift": "pédol shift",
    "paddle shifter": "pédol shifter",
    "paddle shifters": "pédol shifters",
    "dual-clutch": "dúo clátch",
    "dual clutch": "dúo clátch",
    "clutch": "clátch",
    "flywheel": "flái-uíl",
    "crankshaft": "crênk-xáft",
    "camshaft": "kém-xáft",
    "camshafts": "kém-xáfts",
    "manifold": "mêni-fôuld",
    "throttle body": "tró-tol bódi",
    "throttle": "tró-tol",
    "flat-plane": "flét plêin",
    "flat plane": "flét plêin",
    "flat-plane crank": "virabrequim flét plêin",
    "cross-plane": "cróss plêin",
    "cross plane": "cróss plêin",
    "dry sump": "drái sâmp",
    "dry-sump": "drái sâmp",
    "wet sump": "uét sâmp",
    "short shifter": "xórt shifter",
    "straight pipe": "strêit páip",
    "downpipe": "dáun-páip",
    "catback": "quét-béc",
    "header": "rédêr",
    "valvetrain": "válvi-trêin",
    "wankel": "Ván-quel",
    "rotary": "Rô-tari",
    "rotativo": "ro-ta-tívo",

    # -------------------------------------------------------------------------
    # Aerodinâmica, Dinâmica Veicular e Chassi
    # -------------------------------------------------------------------------
    "downforce": "dáun-fórce",
    "drag": "drég",
    "drag coefficient": "coeficiente de arrasto",
    "ground effect": "gráund iféct",
    "ground-effect": "gráund iféct",
    "active aero": "éctiv éro",
    "active aerodynamics": "aerodinâmica ativa",
    "rear wing": "ríar uíng",
    "spoiler": "spôiler",
    "splitter": "splíter",
    "diffuser": "di-fúzer",
    "canards": "ca-nárds",
    "venturi": "ven-túri",
    "undertray": "ânder-trêi",
    "air intake": "êir in-têik",
    "airbox": "êir-bóks",
    "side pods": "sáid póds",
    "sidepods": "sáid póds",
    "drs": "Dê-Erre-Ésse",
    "drag reduction system": "sistema de redução de arrasto Dê-Erre-Ésse",
    "torsional rigidity": "rigidez torcional",
    "camber": "kêm-ber",
    "caster": "kás-ter",
    "toe-in": "tôu-ín",
    "toe-out": "tôu-áut",
    "anti-roll bar": "barra estabilizadora",
    "sway bar": "suêi bár",
    "coilovers": "côil-ôuvers",
    "torque vectoring": "vetorização de torque",
    "limited-slip differential": "diferencial de deslizamento limitado",
    "limited slip": "límited slíp",
    "lsd": "Éle-Ésse-Dê",

    # -------------------------------------------------------------------------
    # Performance, Pilotagem e Métricas
    # -------------------------------------------------------------------------
    "launch control": "lônch con-trôul",
    "launch-control": "lônch con-trôul",
    "horsepower": "rórce-páuer",
    "horse power": "rórce-páuer",
    "hp": "cavalos",
    "bhp": "cavalos de potência",
    "whp": "cavalos na roda",
    "torque": "tórque",
    "redline": "réd-láin",
    "rev limiter": "rév límiter",
    "rev-limiter": "rév límiter",
    "rpm": "érre-pê-êmi",
    "dyno": "dáino",
    "dyno pull": "puxada no dáino",
    "dynamometer": "dinamômetro",
    "quarter mile": "quórter máil",
    "quarter-mile": "quarto de milha",
    "0-100": "zero a cem",
    "0-100 km/h": "zero a cem quilômetros por hora",
    "0-200": "zero a duzentos",
    "0-60": "zero a sessenta milhas",
    "0-60 mph": "zero a sessenta milhas por hora",
    "top speed": "tóp spídi",
    "lap time": "lép táim",
    "oversteer": "ôver-stíer",
    "understeer": "ânder-stíer",
    "drift": "drífti",
    "drifting": "drífting",
    "grip": "grípi",
    "apex": "éipeks",
    "trail braking": "trêil brêiking",
    "downshift": "dáun-shift",
    "upshift": "âp-shift",
    "heel and toe": "ríel éndi tôu",
    "heel-and-toe": "ríel éndi tôu",
    "burnout": "bârn-áut",
    "wheelspin": "uíl-spín",
    "powerslide": "páuer-sláid",
    "g-force": "fórça djí",
    "lateral g": "djí lateral",

    # -------------------------------------------------------------------------
    # Motores Icônicos & Modelos Famosos
    # -------------------------------------------------------------------------
    "2jz": "Tu-Djei-Zí",
    "2jz-gte": "Tu-Djei-Zí Guê-Tê-Ê",
    "1jz": "Uan-Djei-Zí",
    "rb26": "Erre-Bê vinte e seis",
    "rb26dett": "Erre-Bê vinte e seis Dê-Ê-Tê-Tê",
    "sr20": "Ésse-Erre vinte",
    "sr20det": "Ésse-Erre vinte Dê-Ê-Tê",
    "1lr-gue": "Um-Éle-Erre Guê-U-Ê",
    "ej20": "E-Jota vinte",
    "ej25": "E-Jota vinte e cinco",
    "4g63": "Quatro-Guê sessenta e três",
    "b58": "Bê cinquenta e oito",
    "s58": "Ésse cinquenta e oito",
    "s85": "Ésse oitenta e cinco",
    "vr38": "Vê-Erre trinta e oito",
    "vr38dett": "Vê-Erre trinta e oito Dê-Ê-Tê-Tê",
    "ls7": "Éle-Ésse sete",
    "ls3": "Éle-Ésse três",
    "lt6": "Éle-Tê seis",
    "hemi": "Rêmi",
    "coyote": "Coióti",
    "predator": "Predatôr",
    "voodoo": "Vúdú",

    # Nomes de Modelos Icônicos
    "gt3 rs": "Guê-Tê-Três Erre-Ésse",
    "gt3rs": "Guê-Tê-Três Erre-Ésse",
    "gt3": "Guê-Tê-Três",
    "gt2 rs": "Guê-Tê-Dois Erre-Ésse",
    "gt2": "Guê-Tê-Dois",
    "gt-r": "Guê-Tê-Erre",
    "gtr": "Guê-Tê-Erre",
    "r34": "Erre trinta e quatro",
    "r35": "Erre trinta e cinco",
    "r33": "Erre trinta e três",
    "r32": "Erre trinta e dois",
    "c63": "Cê sessenta e três",
    "m3": "Eme três",
    "m5": "Eme cinco",
    "m4": "Eme quatro",
    "m2": "Eme dois",
    "rs6": "Erre-Ésse seis",
    "rs3": "Erre-Ésse três",
    "rs7": "Erre-Ésse sete",
    "r8": "Erre oito",
    "zr1": "Zê-Erre-Um",
    "z06": "Zê-Zero-Seis",
    "z28": "Zê vinte e oito",
    "svj": "Ésse-Vê-Jota",
    "sto": "Ésse-Tê-Ó",
    "evo": "Évo",
    "sti": "Ésse-Tê-Í",
    "wrx": "Dáblio-Erre-Xís",
    "csl": "Cê-Ésse-Éle",
    "gts": "Guê-Tê-Ésse",
    "amg gt": "A-Eme-Guê Guê-Tê",
    "f40": "Éfe quarenta",
    "f50": "Éfe cinquenta",
    "enzo": "Ên-zo",
    "laferrari": "Lá-Ferrári",
    "sf90": "Ésse-Éfe noventa",
    "stradale": "Stra-dáli",
    "purosangue": "Puro-sángue",
    "chiron": "Xi-rôn",
    "veyron": "Vêi-rôn",
    "tourbillon": "Tur-bi-iôn",
    "jesko": "Iés-co",
    "agera": "A-guêra",
    "regera": "Re-guêra",
    "huayra": "Uái-ra",
    "zonda": "Zôn-da",
    "utopia": "U-tô-pia",
    "valkyrie": "Val-quíri",
    "valhalla": "Val-rála",
    "senna": "Sénna",
    "speedtail": "Spídi-têil",
    "720s": "Setecentos e vinte Ésse",
    "765lt": "Setecentos e sessenta e cinco Éle-Tê",
    "artura": "Ar-túra",
    "p1": "Pê-Um",

    # -------------------------------------------------------------------------
    # Aviação, Caças, Turbinas a Jato e Pós-Combustores
    # -------------------------------------------------------------------------
    "sr-71": "Ésse-Erre setenta e um",
    "blackbird": "Blék-bârd",
    "pratt & whitney": "Prét end Uít-ni",
    "pratt and whitney": "Prét end Uít-ni",
    "j58": "Jota cinquenta e oito",
    "rolls-royce merlin": "Rôuls Róis Mér-lin",
    "merlin": "Mér-lin",
    "spitfire": "Spit-fáier",
    "p-51": "Pê cinquenta e um",
    "concorde": "Con-córde",
    "olympus 593": "Olímpus quinhentos e noventa e três",
    "olympus": "Olímpus",
    "afterburner": "Éfter-bârner",
    "turbofan": "Târbo-fén",
    "turbojet": "Târbo-djét",
    "turboélice": "Tûrbo-élice",
    "turboprop": "Târbo-próp",
    "ramjet": "Rém-djét",
    "scramjet": "Screm-djét",
    "mach": "Mák",
    "ge90": "Guê-Ê noventa",
    "tf34": "Tê-Éfe trinta e quatro",
    "gau-8": "Guê-A-U oito",
    "warthog": "Uórt-hóg",

    # -------------------------------------------------------------------------
    # Tanques de Guerra, Blindados e Propulsão Militar Pesada
    # -------------------------------------------------------------------------
    "m1 abrams": "Êi-brans",
    "abrams": "Êi-brans",
    "leopard 2": "Léopard dois",
    "leopard": "Léopard",
    "honeywell": "Râni-uél",
    "agt1500": "A-Guê-Tê mil e quinhentos",
    "mtu": "Eme-Tê-U",
    "maybach": "Mái-bák",
    "panzer": "Pânzer",
    "tiger i": "Tái-guer um",
    "tiger": "Tái-guer",
    "t-90": "Tê noventa",
    "t-72": "Tê setenta e dois",
    "t-80": "Tê oitenta",
    "t-34": "Tê trinta e quatro",

    # -------------------------------------------------------------------------
    # Supermotos e Motores de Alta Rotação de 2 Rodas
    # -------------------------------------------------------------------------
    "kawasaki": "Kaua-záki",
    "ninja h2r": "Ninja Agá dois Érre",
    "ninja h2": "Ninja Agá dois",
    "h2r": "Agá dois Érre",
    "h2": "Agá dois",
    "panigale": "Pani-gáli",
    "panigale v4r": "Pani-gáli Vê quatro Érre",
    "v4r": "Vê quatro Érre",
    "v4": "Vê quatro",
    "desmodromic": "desmodrômico",
    "desmodrômico": "desmodrômico",
    "crossplane": "Cróss-plêin",
    "hayabusa": "Raia-búza",
    "cbx 1000": "Cê-Bê-Xis mil",
    "s1000rr": "Ésse mil Erre-Erre",

    # -------------------------------------------------------------------------
    # Wankel, Diesel de Competição e Powertrains Elétricos / Náuticos
    # -------------------------------------------------------------------------
    "13b-rew": "Treze Bê Rê-E-Dáblio",
    "13b": "Treze Bê",
    "20b": "Vinte Bê",
    "r26b": "Erre vinte e seis Bê",
    "787b": "Setecentos e oitenta e sete Bê",
    "apex seals": "Éipex síuls",
    "apex seal": "Éipex síul",
    "cummins": "Câ-mins",
    "duramax": "Dura-méx",
    "powerstroke": "Páuer-strôuc",
    "common-rail": "cómon rêil",
    "common rail": "cómon rêil",
    "r10 tdi": "Erre dez Tê-Dê-Í",
    "r18 tdi": "Erre dezoito Tê-Dê-Í",
    "tdi": "Tê-Dê-Í",
    "wartsila": "Vart-zíla",
    "rimac nevera": "Rímac Nevêra",
    "nevera": "Nevêra",
    "mcmurtry": "Mec-Mártri",
    "mcmurtry spéirling": "Mec-Mártri Spér-ling",
    "spéirling": "Spér-ling",
    "plaid": "Pléd",
    "taycan": "Tái-can",
    "mercury racing": "Mércuri Rêissing",
    "cigarette": "Cigarét",

    # Circuitos e Provas
    "nürburgring": "Niur-burg-ring",
    "nordschleife": "Nórdi-xláifi",
    "spa-francorchamps": "Spá Fran-cor-xamps",
    "monza": "Môn-za",
    "silverstone": "Sílver-stoun",
    "le mans": "Lê Mâns",
    "daytona": "Dei-tôna",
    "laguna seca": "Lagúna Séca",
    "bathurst": "Bá-târst",
    "mount panorama": "Máunt Pano-râma",
    "suzuka": "Su-zúka",
    "tsukuba": "Tsu-cúba",
    "pikes peak": "Páiks Píki"
}

class AutomotivePronunciationEngine:
    """
    Motor de processamento fonético automotivo.
    Converte texto com termos técnicos e marcas estrangeiras em representação fonética
    otimizada para sintetizadores TTS pt-BR, preservando mapeamento exato para legendas.
    """

    def __init__(self, custom_lexicon: Optional[Dict[str, str]] = None):
        self.lexicon = dict(AUTOMOTIVE_PHONETIC_LEXICON)
        if custom_lexicon:
            self.lexicon.update(custom_lexicon)
            
        # Compilar padrões ordenados por tamanho decrescente (termos compostos primeiro)
        sorted_keys = sorted(self.lexicon.keys(), key=lambda k: len(k), reverse=True)
        # Escapar caracteres regex especiais
        escaped_keys = [re.escape(k) for k in sorted_keys]
        self._pattern = re.compile(r'\b(' + '|'.join(escaped_keys) + r')\b', flags=re.IGNORECASE)

    def phoneticize(self, text: str) -> str:
        """
        Converte termos automotivos no texto para a grafia fonética pt-BR para narração.
        """
        if not text:
            return ""

        def _replace_match(match: re.Match) -> str:
            word = match.group(0).lower()
            return self.lexicon.get(word, match.group(0))

        phonetic_text = self._pattern.sub(_replace_match, text)
        
        # Ajustes fonéticos de numerais técnicos frequentes
        # ex: "9000 rpm" -> "nove mil érre-pê-êmi"
        phonetic_text = re.sub(r'(\d+)\s*rpm\b', r'\1 érre-pê-êmi', phonetic_text, flags=re.IGNORECASE)
        # ex: "800 hp" -> "oitocentos cavalos"
        phonetic_text = re.sub(r'(\d+)\s*(?:hp|cv)\b', r'\1 cavalos', phonetic_text, flags=re.IGNORECASE)
        # ex: "1.25x" -> "um ponto vinte e cinco vezes"
        phonetic_text = re.sub(r'1\.25x\b', 'um ponto vinte e cinco xis', phonetic_text, flags=re.IGNORECASE)
        # ex: "4k" -> "quatro cá"
        phonetic_text = re.sub(r'\b4k\b', 'quatro cá', phonetic_text, flags=re.IGNORECASE)
        # ex: "v10" / "v12" / "v8" isolados
        phonetic_text = re.sub(r'\bv12\b', 'Vê doze', phonetic_text, flags=re.IGNORECASE)
        phonetic_text = re.sub(r'\bv10\b', 'Vê dez', phonetic_text, flags=re.IGNORECASE)
        phonetic_text = re.sub(r'\bv8\b', 'Vê oito', phonetic_text, flags=re.IGNORECASE)
        phonetic_text = re.sub(r'\bv6\b', 'Vê seis', phonetic_text, flags=re.IGNORECASE)
        phonetic_text = re.sub(r'\bi6\b', 'seis em linha', phonetic_text, flags=re.IGNORECASE)
        phonetic_text = re.sub(r'\bw16\b', 'Dáblio dezesseis', phonetic_text, flags=re.IGNORECASE)

        return phonetic_text

    def align_phonetic_timing_to_original(
        self,
        original_text: str,
        phonetic_words_timing: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Mapeia os timestamps de áudio (gerados pelo TTS com o texto fonético)
        de volta para as palavras limpas e bem formatadas do texto original.
        Isso garante que a legenda na tela exiba "TWIN TURBO" ou "PORSCHE 911 GT3 RS",
        enquanto a narração fala com pronúncia perfeita!
        """
        original_words = [w.strip() for w in original_text.split() if w.strip()]
        if not original_words:
            return phonetic_words_timing

        if not phonetic_words_timing:
            # Fallback proporcional caso o TTS não retorne word boundaries
            curr = 0.0
            aligned = []
            for w in original_words:
                dur = max(len(w) * 0.045, 0.20)
                aligned.append({
                    "word": w,
                    "start": round(curr, 3),
                    "end": round(curr + dur, 3)
                })
                curr += dur
            return aligned

        # Se contagem de palavras for idêntica (caso mais comum de substituição 1-para-1)
        if len(original_words) == len(phonetic_words_timing):
            aligned = []
            for orig_w, timing in zip(original_words, phonetic_words_timing):
                aligned.append({
                    "word": orig_w,
                    "start": timing.get("start", 0.0),
                    "end": timing.get("end", 0.0)
                })
            return aligned

        # Interpolação ponderada quando a substituição fonética mudou o número de tokens
        # (ex: "GT3 RS" -> 2 palavras no original virou "Guê Tê Três Erre Ésse" -> 5 tokens no TTS)
        total_audio_start = phonetic_words_timing[0].get("start", 0.0)
        total_audio_end = phonetic_words_timing[-1].get("end", 1.0)
        total_duration = max(0.1, total_audio_end - total_audio_start)

        orig_weights = []
        for w in original_words:
            w_len = len(w)
            if w.endswith((".", "!", "?", ",", ";", ":")):
                w_len += 2
            orig_weights.append(max(w_len, 1))

        total_weight = sum(orig_weights)
        aligned = []
        curr_t = total_audio_start

        for w, weight in zip(original_words, orig_weights):
            dur = (weight / total_weight) * total_duration
            w_start = curr_t
            w_end = min(curr_t + dur, total_audio_end)
            aligned.append({
                "word": w,
                "start": round(w_start, 3),
                "end": round(w_end, 3)
            })
            curr_t = w_end

        return aligned

# Instância singleton padrão do motor de pronúncia
DEFAULT_PRONUNCIATION_ENGINE = AutomotivePronunciationEngine()

def phoneticize_automotive_text(text: str) -> str:
    """Função utilitária rápida para converter texto em fonética automotiva."""
    return DEFAULT_PRONUNCIATION_ENGINE.phoneticize(text)
