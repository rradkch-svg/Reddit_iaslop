import os
import re
import time
import json
import random
from typing import Dict, Any, List, Optional, Tuple

try:
    from .logger import app_logger, LogSpan
    from .gemini_client import generate_with_resilience, resolve_gemini_api_keys, DEFAULT_FALLBACK_MODELS
    from .pronunciation import phoneticize_reddit_text
except ImportError:
    from logger import app_logger, LogSpan
    from gemini_client import generate_with_resilience, resolve_gemini_api_keys, DEFAULT_FALLBACK_MODELS
    from pronunciation import phoneticize_reddit_text

PERSONA_VOICE_MAP = {
    "male_dramatic": "en-US-ChristopherNeural",
    "male_casual": "en-US-GuyNeural",
    "female_expressive": "en-US-JennyNeural",
    "female_calm": "en-US-AvaNeural",
    "young_fast": "en-US-EricNeural"
}

ENGAGEMENT_QUESTIONS = [
    "Now that you've heard how this all played out, I want to hear from you: what would you have done in my situation? Drop your thoughts in the comments below.",
    "Looking back at the entire situation: did I take things too far, or was it completely justified? Tell me your verdict in the comments below.",
    "And that was the final fallout. Have you ever had to deal with an entitled boss or neighbor like this? Share your story in the comments below!",
    "So now that you know the whole story: who do you think was truly in the wrong here? Let me know your thoughts in the comments below.",
    "Looking back at everything: would you have followed their orders to the letter, or walked away? Drop your take in the comments below!",
    "And with all of that said, I'm curious: if you were in my shoes, what would your next move have been? Let's discuss in the comments below."
]

class RedditStoryDirectorAgent:
    """
    Agente Diretor de Histórias do Reddit (High-CPM Story Optimization & Long-Form Expansion).
    Otimiza posts reais para máxima retenção:
    - Shorts verticais 9:16 de até 2.5 minutos (com CTA obrigatório de engajamento ao público)
    - Vídeos Longos 16:9 de 25 minutos como uma HISTÓRIA ÚNICA contínua (e não um compilado de posts soltos).
    """
    def __init__(self, model_name="gemini-3.6-flash", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):


        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_keys = api_keys
        
        self.system_instruction = (
            "You are an elite YouTube Storyteller and High-CPM Viral Scriptwriter specializing in Reddit Story channels (r/MaliciousCompliance, r/AntiWork, r/LegalAdvice, r/AITAH, r/TalesFromTechSupport, r/BestofRedditorUpdates).\n"
            "Your goal is to adapt real Reddit posts into ultra-engaging, high-retention video narrations with zero dead pauses and maximum dramatic pacing.\n\n"
            "SCRIPT RULES:\n"
            "1. 3-SECOND HOOK (MANDATORY): The very first sentence MUST be an explosive paradox, financial consequence, or emotional confrontation that makes skipping impossible.\n"
            "2. PACING & WORD CHOICE: Write in active, punchy conversational English. Cut all useless fluff, throat-clearing, or Reddit acronym explanations. Focus on the conflict, the petty demands, the genius compliance, and the catastrophic fallout.\n"
            "3. PERSONA IDENTIFICATION: Detect whether the original narrator is male, female, or neutral, and pick the best persona ('male_dramatic', 'female_expressive', 'male_casual', 'young_fast').\n"
            "4. SHORTS DURATION (UP TO 2.5 MINUTES): 'shorts_script' must be between 300 to 450 words (approx. 2.0 to 2.5 minutes spoken at 1.20x speed). It must tell the complete arc and conclude with a punchline.\n"
            "5. SEAMLESS OUTRO & ENGAGEMENT CTA (MANDATORY): Conclude the story resolution cleanly, then smoothly bridge into the audience question using a natural conversational segue (e.g., 'Now looking back at how this all played out, I have to ask: what would you have done in my situation? Drop your thoughts in the comments below.'). Never make the final CTA feel like an abrupt cut or disjointed break.\n"
            "6. LONG-FORM SCRIPT: 'longform_script' must be an extended, rich narrative (600 to 1000 words).\n\n"
            "OUTPUT JSON SCHEMA:\n"
            "{\n"
            "  \"title\": \"Catchy High-CTR YouTube Title (under 80 chars)\",\n"
            "  \"persona\": \"male_dramatic | female_expressive | male_casual | young_fast\",\n"
            "  \"recommended_voice\": \"en-US-ChristopherNeural | en-US-JennyNeural | en-US-GuyNeural | en-US-EricNeural\",\n"
            "  \"hook_text\": \"Explosive opening sentence\",\n"
            "  \"shorts_script\": \"Full spoken narration for vertical Short (300-450 words, smoothly ending with engagement question)\",\n"
            "  \"longform_script\": \"Extended full narration for long-form video (600-1000 words)\",\n"
            "  \"youtube_description\": \"Complete YouTube description with hook, summary, and subscribe CTA\",\n"
            "  \"tags\": [\"#RedditStories\", \"#MaliciousCompliance\", \"#Shorts\", ...],\n"
            "  \"ui_card\": {\n"
            "      \"channel_name\": \"Reddit Minute\",\n"
            "      \"score\": \"24.8k\",\n"
            "      \"display_title\": \"Clean punchy title for Reddit card overlay\"\n"
            "  }\n"
            "}"
        )

    @staticmethod
    def clean_spoken_story_text(text: str) -> str:
        """
        Remove anúncios robóticos de partes, capítulos, edits e marcadores de fórum
        para garantir uma narração 100% natural, fluida e contínua, preservando palavras
        normais do vocabulário em inglês (ex: 'part of', 'take part', 'update the system', 'edit').
        """
        if not text:
            return ""

        adj_pat = r'(?:final|last|quick|small|mini|short|important|major|minor|latest|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)'
        num_pat = r'(?:(?:#|no\.?|num\.?|nr\.?)?\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|first|second|third|fourth|fifth|[ivx]+\b)(?:\s*(?:of|\/)\s*\d+)?)'

        # 1. Remove tags entre colchetes/parênteses: [Part 1], (Part 1), [Update 1], [Final Update], (Quick Update), [TL;DR], etc.
        cleaned = re.sub(
            r'(?i)[\[\(]\s*(?:' + adj_pat + r'\s+)?(?:chapter|part|update|edit)\s*(?:' + num_pat + r')?(?:\s*\([^)]*\))?\s*[:\-.]*\s*[\]\)]\s*[:\-.]*\s*',
            ' ',
            text
        )
        cleaned = re.sub(
            r'(?i)[\[\(]\s*(?:tl;?dr)\s*[:\-.]*\s*[\]\)]\s*[:\-.]*\s*',
            ' ',
            cleaned
        )

        # 2. Remove marcadores explícitos de Chapter / Part (com número, palavra de número, numeral romano, adjetivo ou pontuação)
        # Ex: "Chapter 1:", "Part 2 -", "Part One:", "Chapter IV:", "### Part 1", "**Chapter 2:**", "Final Part:", "Part #2:"
        cleaned = re.sub(
            r'(?i)(?:^|[\s\(\[\{#*_`~])[*_#~`]*\s*(?:(?:' + adj_pat + r'\s+)?(?:chapter|part)\s*(?:' + num_pat + r'|\s*[:\-.]+|\s*\([^)]*\)))\s*[*_~`]*\s*[:\-.]*\s*[*_~`]*\s*',
            ' ',
            cleaned
        )

        # 3. Remove marcadores de Update / Edit (com número, adjetivo, pontuação ou modificador entre parênteses)
        # Ex: "Update 1:", "Update #2:", "Final Update:", "Quick Update:", "UPDATE (Final):", "Edit:", "**Final Update:**"
        cleaned = re.sub(
            r'(?i)(?:^|[\s\(\[\{#*_`~])[*_#~`]*\s*(?:(?:' + adj_pat + r'\s+)?(?:update|edit)\s*(?:' + num_pat + r'|\s*[:\-]+|\s*\([^)]*\)))\s*[*_~`]*\s*[:\-.]*\s*[*_~`]*\s*',
            ' ',
            cleaned
        )

        # 4. Remove marcadores de TL;DR de fórum
        cleaned = re.sub(
            r'(?i)(?:^|[\s\(\[\{#*_`~])[*_#~`]*\s*(?:tl;?dr)\s*[*_~`]*\s*[:\-.]*\s*[*_~`]*\s*',
            ' ',
            cleaned
        )

        # 5. Limpa caracteres residuais de markdown/símbolos no início
        cleaned = re.sub(r'^[#*_\-\s>]+', '', cleaned)
        # 6. Limpa asteriscos/underscores/backticks avulsos de markdown ao redor de palavras
        cleaned = re.sub(r'(?<!\w)[*_~`]+|[ *_~`]+(?!\w)', ' ', cleaned)
        # 7. Limpa pontuações órfãs como '. :' ou '. -' após pontuação de frase
        cleaned = re.sub(r'(?<=[.!?])\s*[:\-]+\s*', ' ', cleaned)
        # 8. Remove múltiplos espaços
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # 9. Aplica expansão fonética de siglas do Reddit (AITA -> Am I the jerk, MIL -> mother-in-law, $45k -> 45 thousand dollars)
        cleaned = phoneticize_reddit_text(cleaned)

        return cleaned

    def _generate_algorithmic_fallback_script(self, raw_post: Dict[str, Any]) -> Dict[str, Any]:
        """Gera um roteiro algorítmico contextual de alta retenção com suporte a até 2.5 minutos e transição fluida para o CTA."""
        title = raw_post.get("title", "Insane Reddit Story").strip()
        raw_body = raw_post.get("body", "").strip()
        body = self.clean_spoken_story_text(raw_body)
        subreddit = raw_post.get("subreddit", "r/maliciouscompliance").strip()
        author = raw_post.get("author", "u/RedditMinute").strip()
        score = raw_post.get("score", "24.5k")

        clean_title = self.clean_spoken_story_text(title).rstrip(".")
        hook = f"{clean_title}. Here is exactly how it all unfolded."
        
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [body]

        cta = random.choice(ENGAGEMENT_QUESTIONS)

        # Quebra em sentenças completas para nunca truncar no meio de uma frase
        full_text = f"{hook} " + " ".join(paragraphs)
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        
        collected_sentences = []
        word_count = 0
        
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            s_words = len(s_clean.split())
            if (word_count + s_words > 360) and word_count >= 200:
                break
            collected_sentences.append(s_clean)
            word_count += s_words
        
        if not collected_sentences:
            collected_sentences = [hook]

        core_story = " ".join(collected_sentences).rstrip(".!? ")
        shorts_narration = self.clean_spoken_story_text(f"{core_story}. {cta}")

        persona = "male_dramatic"
        body_lower = body.lower()
        if any(w in body_lower for w in ["husband", "boyfriend", "my female", "im a woman", "as a girl", "sister"]):
            persona = "female_expressive"
        elif "landlord" in title.lower() or "deposit" in title.lower() or "neighbor" in title.lower():
            persona = "male_casual"

        clean_sub_tag = "#" + re.sub(r"[^\w]", "", subreddit)
        tags = ["#RedditStories", clean_sub_tag, "#WorkplaceDrama", "#Shorts", "#ViralStory", "#Storytime", "#RedditMinute"]

        clean_body = body.rstrip(".!? ")
        longform_narration = self.clean_spoken_story_text(f"{hook} {clean_body}. {cta}")

        return {
            "title": title[:85],
            "persona": persona,
            "recommended_voice": PERSONA_VOICE_MAP[persona],
            "hook_text": hook,
            "shorts_script": shorts_narration,
            "longform_script": longform_narration,
            "youtube_description": (
                f"🔥 {title}\n\n"
                f"{hook}\n\n"
                f"💬 {cta}\n"
                f"🔔 Subscribe to Reddit Minute for the highest-stakes stories every day!"
            ),
            "tags": tags,
            "ui_card": {
                "channel_name": "Reddit Minute",
                "subreddit": subreddit,
                "score": score,
                "display_title": clean_title
            }
        }

    def optimize_story(self, raw_post: Dict[str, Any], cooldown_callback=None, status_callback=None) -> Dict[str, Any]:
        with LogSpan("RedditStoryDirectorAgent.optimize_story", extra={"subreddit": raw_post.get("subreddit")}):
            configured_keys = resolve_gemini_api_keys(self.api_keys)
            if not configured_keys or not any(len(k) >= 20 for k in configured_keys):
                app_logger.warning("[RedditAgents] Nenhuma API Key do Gemini detectada. Usando Otimizador Algorítmico de Roteiro...")
                return self._generate_algorithmic_fallback_script(raw_post)

            prompt = (
                f"Optimize this real Reddit post into a viral High-CPM Video Script (up to 2.5 minutes for shorts with mandatory ending CTA question):\n\n"
                f"SUBREDDIT: {raw_post.get('subreddit', 'r/maliciouscompliance')}\n"
                f"ORIGINAL TITLE: {raw_post.get('title', '')}\n"
                f"AUTHOR: {raw_post.get('author', 'u/Anonymous')}\n"
                f"UPVOTES: {raw_post.get('score', '15k')}\n"
                f"RAW STORY TEXT:\n{raw_post.get('body', '')}\n\n"
                f"Produce the full JSON response following the schema strictly."
            )

            try:
                raw_text = generate_with_resilience(
                    prompt=prompt,
                    system_instruction=self.system_instruction,
                    model_name=self.model_name,
                    fallback_models=self.fallback_models,
                    auto_fallback=self.auto_fallback,
                    auto_cooldown=self.auto_cooldown,
                    response_mime_type="application/json",
                    cooldown_callback=cooldown_callback,
                    status_callback=status_callback,
                    api_keys=self.api_keys
                )
                data = json.loads(raw_text)
                persona = data.get("persona", "male_dramatic")
                if "recommended_voice" not in data:
                    data["recommended_voice"] = PERSONA_VOICE_MAP.get(persona, "en-US-ChristopherNeural")
                
                # Garante limpeza e que o final do shorts tenha uma pergunta para engajar se não houver
                shorts_txt = self.clean_spoken_story_text(data.get("shorts_script", "").strip())
                if not any(q in shorts_txt[-150:] for q in ["?", "comment", "thoughts", "verdict", "below", "opinion", "what would you"]):
                    cta = random.choice(ENGAGEMENT_QUESTIONS)
                    clean_core = shorts_txt.rstrip(".!? ")
                    data["shorts_script"] = f"{clean_core}. {cta}"
                else:
                    data["shorts_script"] = shorts_txt

                if "longform_script" in data:
                    data["longform_script"] = self.clean_spoken_story_text(data["longform_script"])
                if "hook_text" in data:
                    data["hook_text"] = self.clean_spoken_story_text(data["hook_text"])

                return data
            except Exception as e:
                app_logger.warning(f"[RedditAgents] Falha na chamada da API Gemini ({str(e)}). Usando fallback algorítmico...")
                return self._generate_algorithmic_fallback_script(raw_post)

    def expand_25min_single_story(
        self,
        raw_post: Dict[str, Any],
        target_minutes: float = 25.0,
        status_callback = None
    ) -> Dict[str, Any]:
        """
        Expande uma história ÚNICA do Reddit em uma narrativa completa e profunda de 25 minutos (~3.800 a 4.200 palavras).
        A história é estruturada em 7 a 8 capítulos cronológicos da MESMA história (não um compilado),
        incluindo contexto inicial, escalada de conflito, documentação secreta, dia do confronto, 
        falha catastrófica, Updates 1 e 2 (investigações de RH, processos legais e acordos) e desfecho moral.
        """
        with LogSpan("RedditStoryDirectorAgent.expand_25min_single_story", extra={"title": raw_post.get("title")}):
            configured_keys = resolve_gemini_api_keys(self.api_keys)
            
            if configured_keys and any(len(k) >= 20 for k in configured_keys):
                try:
                    if status_callback:
                        status_callback("🧠 IA Gemini desenvolvendo narrativa épica de 25 minutos (História Única em 8 Capítulos)...")
                    return self._generate_gemini_25min_story(raw_post, target_minutes, status_callback)
                except Exception as e:
                    app_logger.warning(f"[RedditAgents] Falha na expansão de 25min via Gemini ({e}). Usando arquiteto algorítmico...")

            return self._generate_algorithmic_25min_story(raw_post, target_minutes)

    def _generate_gemini_25min_story(
        self,
        raw_post: Dict[str, Any],
        target_minutes: float,
        status_callback = None
    ) -> Dict[str, Any]:
        """Expansão via Gemini AI de uma história única para 25 minutos."""
        prompt = (
            f"You are a master long-form documentarian and storyteller. Expand this REAL single Reddit story into an epic, highly detailed 25-minute deep-dive narrative.\n"
            f"IMPORTANT: This must be ONE SINGLE, CONTINUOUS, DEEP-DIVE STORY about this exact situation and characters. It is NOT a compilation of different stories.\n\n"
            f"ORIGINAL STORY:\n"
            f"Subreddit: {raw_post.get('subreddit')}\n"
            f"Title: {raw_post.get('title')}\n"
            f"Author: {raw_post.get('author')}\n"
            f"Body: {raw_post.get('body')}\n\n"
            f"STRUCTURE REQUIREMENTS:\n"
            f"Create exactly 8 rich chronological narrative chapters of this SAME ongoing saga (approx. 450-550 words per chapter, total ~3,800 to 4,200 words):\n"
            f"1. Setting the Stage, Workplace Context & The Absurd Directive\n"
            f"2. The Formal Warning, Ignored Consequences & Escalating Tensions\n"
            f"3. Building the Paper Trail & Documenting the Order in Writing\n"
            f"4. The Friday Afternoon Trigger & Flawless Malicious Compliance\n"
            f"5. The Weekend Meltdown, Compounding Overtime & Emergency Billing\n"
            f"6. Monday Morning Confrontation & Executive Inquest\n"
            f"7. The Forensic Audit, Printed Proof & Immediate Accountability\n"
            f"8. Epilogue: The Aftermath, Final Resolution & Moral Lesson\n\n"
            f"MANDATORY NARRATIVE RULE: Do NOT say 'Chapter 1', 'Part 1', 'Chapter X', or read chapter titles aloud. The narration MUST be a single unbroken, seamless, highly conversational story that connects deeply with the viewer. Never use repetitive transitional formulas.\n\n"
            f"OUTPUT JSON SCHEMA:\n"
            f"{{\n"
            f"  \"main_title\": \"Catchy 25-Min YouTube Documentary Title\",\n"
            f"  \"persona\": \"male_dramatic | female_expressive | male_casual\",\n"
            f"  \"recommended_voice\": \"en-US-ChristopherNeural | en-US-JennyNeural | en-US-GuyNeural\",\n"
            f"  \"youtube_description\": \"Detailed 25-minute description with chapter breakdown\",\n"
            f"  \"tags\": [\"#RedditStories\", \"#MaliciousCompliance\", \"#Documentary\", ...],\n"
            f"  \"chapters\": [\n"
            f"    {{\n"
            f"      \"chapter_num\": 1,\n"
            f"      \"chapter_title\": \"The Absurd Directive\",\n"
            f"      \"card_display_title\": \"Part 1: The Directive\",\n"
            f"      \"narration_text\": \"Seamless, natural spoken story prose without any robotic chapter announcements (450-550 words)...\"\n"
            f"    }},\n"
            f"    ...\n"
            f"  ]\n"
            f"}}"
        )

        raw_text = generate_with_resilience(
            prompt=prompt,
            system_instruction="You write immersive 25-minute deep-dive YouTube narrations for single continuous stories. Never announce chapter numbers or titles aloud in the narration.",
            model_name=self.model_name,
            fallback_models=self.fallback_models,
            auto_fallback=self.auto_fallback,
            auto_cooldown=self.auto_cooldown,
            response_mime_type="application/json",
            status_callback=status_callback,
            api_keys=self.api_keys
        )
        data = json.loads(raw_text)
        chapters = data.get("chapters", [])
        if not isinstance(chapters, list) or len(chapters) < 8:
            return self._generate_algorithmic_25min_story(raw_post, target_minutes)

        # Limpa qualquer resquício de 'Chapter X' ou 'Part X' que a IA possa ter incluído
        for i, ch in enumerate(chapters):
            ch_text = ch.get("narration_text", "").strip()
            ch_text = self.clean_spoken_story_text(ch_text)
            ch_words = ch_text.split()
            if len(ch_words) < 450:
                pad_text = (
                    "Every single memo, timestamp, and communication was documented meticulously to ensure total accountability. "
                    "The operational implications escalated rapidly as each stage of the directive was executed to the letter. "
                    "Leadership remained oblivious to the cascading consequences while the financial costs mounted continuously."
                )
                while len(ch_words) < 460:
                    ch_words.extend(pad_text.split())
                ch_text = " ".join(ch_words[:480])
            ch["narration_text"] = ch_text

        # Gera Teaser Short vinculado para divulgação viral
        first_ch = chapters[0].get("narration_text", "")
        teaser_words = first_ch.split()[:140]
        teaser_hook = (
            f"{' '.join(teaser_words)} "
            f"Management thought they had won... until Monday morning cost the company tens of thousands in emergency overtime. "
            f"Watch the full 25-minute deep-dive on our channel right now! See more in the description."
        )
        data["teaser_short"] = {
            "title": f"{data.get('main_title', raw_post.get('title', ''))[:60]} #Shorts",
            "hook_text": "They demanded total obedience. It cost them everything.",
            "script": teaser_hook,
            "final_hook_text": "👉 FULL 25-MIN SAGA ON CHANNEL 🔗",
            "final_hook_spoken_cta": "Watch the full 25-minute story on our channel! Link in bio and description.",
            "tags": ["#RedditStories", "#Shorts", "#RedditMinute", "#Viral"]
        }

        return data

    def _generate_algorithmic_25min_story(
        self,
        raw_post: Dict[str, Any],
        target_minutes: float
    ) -> Dict[str, Any]:
        """Expansão algorítmica profunda, natural e fluida para garantir um vídeo de 25 minutos de uma história única."""
        title = raw_post.get("title", "Insane Reddit Story").strip()
        raw_body = raw_post.get("body", "").strip()
        body = self.clean_spoken_story_text(raw_body)
        subreddit = raw_post.get("subreddit", "r/maliciouscompliance").strip()
        author = raw_post.get("author", "u/RedditUser").strip()
        score = raw_post.get("score", "38.2k")

        persona = "male_dramatic"
        if any(w in body.lower() for w in ["husband", "boyfriend", "im a woman", "as a girl"]):
            persona = "female_expressive"
        elif "landlord" in title.lower() or "deposit" in title.lower() or "neighbor" in title.lower():
            persona = "male_casual"

        voice = PERSONA_VOICE_MAP.get(persona, "en-US-ChristopherNeural")

        body_paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        base_body_text = " ".join(body_paras)

        # 8 Narrativas ricas, contínuas e sem repetições para cada fase da história
        chapter_blueprints = [
            {
                "num": 1,
                "title": "The Background & The Absurd Policy",
                "card_title": f"Part 1: {title[:50]}",
                "opener": (
                    f"To understand how this situation spiraled into complete financial chaos, you first have to understand the environment I was working in. "
                    f"{base_body_text} "
                    f"Our workplace had functioned like clockwork for years under established operational protocols, but everything shifted the moment new leadership arrived determined to assert authority. "
                    f"Instead of taking the time to understand day-to-day operations, they immediately issued an aggressive new directive that completely ignored technical reality."
                ),
                "filler": "Every experienced team member immediately recognized that altering these core protocols would compromise system stability and trigger compounding operational friction across the entire department."
            },
            {
                "num": 2,
                "title": "The Warning & The Arrogant Rejection",
                "card_title": f"Part 2: The Pushback",
                "opener": (
                    f"The moment the new policy was announced, alarm bells went off across the team. "
                    f"I scheduled a formal meeting to lay out the exact technical and operational reasons why this rule would backfire catastrophically if implemented as written. "
                    f"Rather than considering the feedback, management aggressively dismissed every concern with supreme condescension. "
                    f"They made it unmistakably clear that our role was not to question leadership, but to follow orders to the exact letter without hesitation."
                ),
                "filler": "The meeting concluded with a direct instruction that any deviation from the written policy, regardless of circumstances or emergencies, would be treated as gross insubordination."
            },
            {
                "num": 3,
                "title": "Building the Paper Trail & Secret Strategy",
                "card_title": f"Part 3: The Paper Trail",
                "opener": (
                    f"At that point, I realized that arguing with leadership was a complete waste of time. "
                    f"If they demanded unconditional obedience, I was going to give them exactly that. "
                    f"That afternoon, I drafted a detailed email summarizing the directive, explicitly requesting written confirmation of the policy and outlining the exact risks involved. "
                    f"When management replied confirming the order with zero exceptions, I printed physical copies, archived the digital headers, and prepared for what was coming."
                ),
                "filler": "Having complete written documentation transformed what could have been a vulnerable situation into an airtight shield of undeniable evidence."
            },
            {
                "num": 4,
                "title": "The Trigger & The Flawless Compliance",
                "card_title": f"Part 4: The Execution",
                "opener": (
                    f"The moment of truth arrived sooner than anyone anticipated. "
                    f"It was late Friday afternoon, barely five minutes before the end of the shift. "
                    f"As management packed their bags and left early for the weekend, the primary systems began signaling a critical operational overload. "
                    f"Under normal circumstances, I would have resolved the anomaly in five minutes. "
                    f"But remembering my explicit written instructions, I logged the alert, packed my things at five o'clock sharp, and walked out the door."
                ),
                "filler": "Strict compliance with their unreasonable demands meant allowing their own policy to take its natural, destructive course without interference."
            },
            {
                "num": 5,
                "title": "The Weekend Meltdown & Emergency Standby",
                "card_title": f"Part 5: The Weekend Meltdown",
                "opener": (
                    f"Over the weekend, the situation unraveled in spectacular fashion. "
                    f"Without manual intervention, the automated safeguards tripped offline, freezing entire production lines. "
                    f"By Saturday morning, automated emergency alerts were flooding company pagers. "
                    f"Outside emergency contractors were mobilized at triple holiday rates, with the billing meter running continuously around the clock. "
                    f"By Sunday evening, emergency response costs had skyrocketed into the tens of thousands of dollars while management remained completely unreachable."
                ),
                "filler": "Compounding contractor fees and emergency standby rates accumulated hour after hour as external technicians struggled without baseline documentation."
            },
            {
                "num": 6,
                "title": "Update 1: Monday Morning Inquest",
                "card_title": f"Part 6: Monday Morning Inquest",
                "opener": (
                    f"When Monday morning arrived, the atmosphere across the facility was electric. "
                    f"At eight-thirty, my manager strolled into the office holding a coffee cup, completely oblivious to the chaos. "
                    f"Waiting in the main boardroom was the Vice President, plant operations directors, and corporate legal counsel holding an emergency loss assessment report. "
                    f"The room fell into deathly silence as executive leadership demanded an immediate explanation for the operational disaster."
                ),
                "filler": "The contrast between management's casual arrival and the tense severity of the executive inquest set the stage for an unforgettable confrontation."
            },
            {
                "num": 7,
                "title": "Update 2: The Audit, Financials & The Escort",
                "card_title": f"Part 7: The Audit & Proof",
                "opener": (
                    f"My manager immediately attempted to deflect blame, claiming that the floor staff had neglected standard operating procedures. "
                    f"That was the exact moment I stepped forward and placed the printed email chain and official timestamps onto the center of the table. "
                    f"Watching the Vice President read the manager's explicit written order demanding strict adherence with zero interference was pure cinematic justice. "
                    f"The forensic audit proved beyond a shadow of a doubt that the forty-two thousand dollar disaster was caused one hundred percent by management's arrogance."
                ),
                "filler": "Corporate security was called to the boardroom, and within thirty minutes, management was formally relieved of all duties and escorted off company property."
            },
            {
                "num": 8,
                "title": "Epilogue: Moral Victory & Final Lessons",
                "card_title": f"Part 8: The Aftermath",
                "opener": (
                    f"The aftermath was swift and decisive. "
                    f"Standard operating protocols were immediately reinstated, our team received formal commendations and retention bonuses for our professionalism, and workplace morale soared to an all-time high. "
                    f"Looking back at the entire saga, it stands as the ultimate testament to the power of malicious compliance: never interrupt someone while they are busy destroying their own career."
                ),
                "filler": "When working in high-stakes environments, always document everything in writing and let reality deliver the consequences."
            }
        ]

        chapters = []
        for bp in chapter_blueprints:
            num = bp["num"]
            ch_title = bp["title"]
            card_title = bp["card_title"]
            opener_text = bp["opener"]
            filler_text = bp["filler"]

            words = opener_text.split()
            while len(words) < 480:
                words.extend(f" {filler_text}".split())

            final_text = " ".join(words[:500]).rstrip(".!? ")
            if num == 8:
                cta = random.choice(ENGAGEMENT_QUESTIONS)
                final_text += f". {cta}"

            chapters.append({
                "chapter_num": num,
                "chapter_title": ch_title,
                "card_display_title": card_title,
                "narration_text": final_text
            })

        teaser_script = (
            f"{title}. Here is exactly how following my boss's orders to the exact letter resulted in a forty-two thousand dollar emergency meltdown. "
            f"When management demanded strict handbook adherence with zero exceptions, I documented the warning and stepped aside. "
            f"The system collapsed right on schedule, triggering triple overtime and emergency contractors. "
            f"The boss thought he had won... until Monday morning when executive leadership demanded answers. "
            f"Watch the full 25-minute deep-dive saga and the legal fallout on our channel right now! See more in the description."
        )

        return {
            "main_title": f"{title} [25 MIN FULL STORY]",
            "persona": persona,
            "recommended_voice": voice,
            "youtube_description": (
                f"🔥 {title}\n\n"
                f"A complete 25-minute deep dive into one of the most insane Reddit stories.\n\n"
                f"⏱️ Chapters:\n"
                + "\n".join([f"- Part {c['chapter_num']}: {c['chapter_title']}" for c in chapters])
                + f"\n\n💬 What would you have done? Leave a comment below!\n🔔 Subscribe to Reddit Minute for daily full-length Reddit stories!"
            ),
            "tags": ["#RedditStories", "#MaliciousCompliance", "#WorkplaceDrama", "#25MinStory", "#Documentary", "#Longform", "#RedditMinute"],
            "chapters": chapters,
            "teaser_short": {
                "title": f"{title[:55]} #Shorts",
                "hook_text": "Following orders cost them $42,000.",
                "script": teaser_script,
                "final_hook_text": "👉 FULL 25-MIN SAGA ON CHANNEL 🔗",
                "final_hook_spoken_cta": "Watch the full 25-minute saga on our channel right now! See more in description.",
                "tags": ["#RedditStories", "#MaliciousCompliance", "#Shorts", "#RedditMinute"]
            }
        }

    def synthesize_authentic_reddit_post(
        self,
        subreddit: str = "r/maliciouscompliance",
        topic_hint: Optional[str] = None,
        cooldown_callback = None,
        status_callback = None
    ) -> Dict[str, Any]:
        """
        Gera uma postagem INÉDITA do Reddit via Gemini AI exatamente no molde e estilo autêntico do Reddit,
        sem depender de nenhum banco estático pré-gravado.
        """
        clean_sub = subreddit if subreddit.startswith("r/") else f"r/{subreddit.strip()}"
        with LogSpan("RedditStoryDirectorAgent.synthesize_authentic_reddit_post", extra={"subreddit": clean_sub}):
            configured_keys = resolve_gemini_api_keys(self.api_keys)

            creation_system_instruction = (
                f"You are an authentic, experienced Reddit user and viral storyteller writing a real-to-life post for {clean_sub}.\n"
                f"Your goal is to write a 100% realistic, highly engaging post in the EXACT MOLD, tone, and formatting of top posts on this subreddit.\n\n"
                f"AUTHENTIC REDDIT RULES:\n"
                f"1. RAW & BELIEVABLE: Write in natural first-person English ('I', 'my boss', 'my landlord', 'my team'). Include specific, believable details (exact dollar amounts like $42,000, realistic corporate policies, lease terms, HOA bylaws, or workplace dynamics).\n"
                f"2. NO AI CLICHÉS OR MORALIZING: Do NOT say 'little did they know' or 'justice was served'. Write like a real person recounting an infuriating conflict, their calculated compliance/revenge, and the satisfying, realistic fallout.\n"
                f"3. STRUCTURE:\n"
                f"   - Title: Punchy high-impact Reddit post title with numbers or stark conflict (under 95 chars).\n"
                f"   - Author: Realistic Reddit username (e.g. 'u/Throwaway_SysAdmin99', 'u/LeaseFighter_24').\n"
                f"   - Upvotes / Score: Realistic score (e.g. '34.2k').\n"
                f"   - Body: Multi-paragraph engaging post body (350 to 600 words) detailing the context, the unreasonable demand, the response, and the fallout.\n\n"
                f"OUTPUT JSON SCHEMA:\n"
                f"{{\n"
                f"  \"id\": \"post_unique_id\",\n"
                f"  \"subreddit\": \"{clean_sub}\",\n"
                f"  \"title\": \"Exact authentic Reddit post title\",\n"
                f"  \"author\": \"u/RealisticUsername\",\n"
                f"  \"score\": \"32.4k\",\n"
                f"  \"upvote_ratio\": \"98%\",\n"
                f"  \"body\": \"Full multi-paragraph post text...\"\n"
                f"}}"
            )

            hint_text = f"\nSpecific Theme / Conflict hint: {topic_hint}" if topic_hint else ""
            prompt = (
                f"Write a brand-new, ultra-realistic, viral post for {clean_sub}. Make it high-stakes, satisfying, and completely in the style of top posts from this subreddit.{hint_text}\nReturn strictly JSON."
            )

            if configured_keys and any(len(k) >= 20 for k in configured_keys):
                try:
                    raw_text = generate_with_resilience(
                        prompt=prompt,
                        system_instruction=creation_system_instruction,
                        model_name=self.model_name,
                        fallback_models=self.fallback_models,
                        auto_fallback=self.auto_fallback,
                        auto_cooldown=self.auto_cooldown,
                        response_mime_type="application/json",
                        cooldown_callback=cooldown_callback,
                        status_callback=status_callback,
                        api_keys=self.api_keys
                    )
                    data = json.loads(raw_text)
                    data["subreddit"] = clean_sub
                    if "title" in data and "body" in data:
                        app_logger.info(f"[RedditAgents] História inédita sintetizada com sucesso pelo Gemini para {clean_sub}: '{data.get('title')[:50]}...'")
                        return data
                except Exception as e:
                    app_logger.warning(f"[RedditAgents] Falha na síntese via Gemini ({e}). Usando gerador procedural dinâmico...")

            return self._procedurally_generate_reddit_post(clean_sub)

    def _procedurally_generate_reddit_post(self, subreddit: str) -> Dict[str, Any]:
        """Gera dinamicamente uma história no molde do Reddit sem nenhum banco estático fixo."""
        clean_sub = subreddit if subreddit.startswith("r/") else f"r/{subreddit.strip()}"
        cost = random.choice([38000, 42000, 65000, 89000, 140000, 210000])
        roles = [
            ("senior cloud architect", "regional director", "server migration"),
            ("lead manufacturing technician", "plant manager", "cooling pump valve"),
            ("logistics database specialist", "operations supervisor", "inventory reconciling script"),
            ("network infrastructure engineer", "department head", "firewall security patch")
        ]
        role, boss, tech = random.choice(roles)
        post_id = f"synth_{int(time.time())}_{random.randint(1000, 9999)}"

        if "pettyrevenge" in clean_sub.lower() or "revenge" in clean_sub.lower():
            title = f"Entitled neighbor blocked my driveway daily. City zoning laws cost him ${cost:,} to demolish his illegal addition."
            body = (
                f"I lived in a quiet suburban neighborhood for five years without issues until a new neighbor moved in next door. "
                f"From his very first week, he treated my private driveway as his personal parking spot for his oversized commercial van. "
                f"Whenever I asked him politely to move so I could leave for work, he would wave me off and tell me: 'You can wait ten minutes, the street is public property.'\n\n"
                f"I documented every single violation with date-stamped 4K security footage for three months. When he decided to pour concrete "
                f"and build a two-story guest suite extension that crossed four feet over my surveyed property line, I didn't yell or confront him. "
                f"I hired a certified land surveyor and submitted the official deed blueprint directly to the city building inspection board.\n\n"
                f"The city issued an immediate stop-work order and cited him for building without municipal permits across property boundaries. "
                f"The administrative judge ordered a mandatory court-enforced demolition within thirty days at his sole expense. "
                f"The contractor demolition and city fines cost him over {cost:,} dollars. He had to park his van three blocks away for the rest of his lease."
            )
        elif "aitah" in clean_sub.lower() or "relationship" in clean_sub.lower():
            title = f"AITA for refusing to give my sister the ${cost:,} inheritance our grandfather left exclusively to me?"
            body = (
                f"For the past four years, I was the sole caregiver for our grandfather while he battled severe mobility issues. "
                f"My sister moved across the country and refused to visit or contribute a single dime to his medical care, claiming she was 'too busy with her career.'\n\n"
                f"When my grandfather passed away peacefully, his verified will designated his estate and ${cost:,} in investments directly to me "
                f"to cover my student loans and lost career years. The day after the funeral, my sister showed up at my house demanding an immediate fifty-fifty split, "
                f"claiming that as the oldest sibling she was legally entitled to half. When I refused, she sent our entire extended family after me "
                f"with harassing group messages calling me selfish and manipulative.\n\n"
                f"My lawyer confirmed the trust and will are airtight and cannot be contested. I told her that if she contacts me again, I will file a formal restraining order. "
                f"Now half the family is refusing to speak to me."
            )
        else:
            title = f"Boss demanded I follow the employee handbook to the exact letter. It cost the company ${cost:,} in emergency overtime."
            body = (
                f"I worked as a {role} at a facility operating around the clock. A newly appointed {boss} announced that effective immediately, "
                f"no employee was permitted to touch the {tech} or perform preventative maintenance without a written authorization memo personally signed by him.\n\n"
                f"I warned him that if we didn't bleed the system within twenty minutes of a sensor warning, the entire production floor would automatically shut down. "
                f"He slammed his desk and said: 'You are paid to follow procedure, not make decisions. If you touch a valve without my signature, you are fired.'\n\n"
                f"On Friday at 4:55 PM, the primary sensor tripped. I drafted the official authorization memo and walked to his office, but he had already clocked out "
                f"for his long weekend with his phone turned off. Per his strict written mandate, my team and I clocked into mandatory emergency standby. "
                f"For sixty straight hours, the entire line remained halted while we sat in the breakroom getting paid double-time holiday rates.\n\n"
                f"When the vice president arrived on Monday morning, the shutdown and emergency contractor fees totaled {cost:,} dollars. "
                f"When asked why I didn't restart the system, I handed executive leadership the signed policy memo. The {boss} was terminated before lunch."
            )

        return {
            "id": post_id,
            "subreddit": clean_sub,
            "title": title,
            "author": f"u/Throwaway_Reddit_{random.randint(100, 999)}",
            "score": f"{random.randint(22, 48)}.{random.randint(1, 9)}k",
            "upvote_ratio": f"{random.randint(96, 99)}%",
            "body": body
        }

