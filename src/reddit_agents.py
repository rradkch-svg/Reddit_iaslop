import os
import re
import time
import json
import random
from typing import Dict, Any, List, Optional, Tuple

try:
    from .logger import app_logger, LogSpan
    from .agents import generate_with_resilience, resolve_gemini_api_keys, DEFAULT_FALLBACK_MODELS
except ImportError:
    from logger import app_logger, LogSpan
    from agents import generate_with_resilience, resolve_gemini_api_keys, DEFAULT_FALLBACK_MODELS

PERSONA_VOICE_MAP = {
    "male_dramatic": "en-US-ChristopherNeural",
    "male_casual": "en-US-GuyNeural",
    "female_expressive": "en-US-JennyNeural",
    "female_calm": "en-US-AvaNeural",
    "young_fast": "en-US-EricNeural"
}

class RedditStoryDirectorAgent:
    """
    Agente Diretor de Histórias do Reddit (High-CPM Story Optimization).
    Otimiza posts reais de subreddits de alto CPM para máxima retenção (Shorts 9:16 e Long-Form 16:9),
    criando um gancho irresistível nos primeiros 3 segundos e roteirização magnética.
    """
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):
        self.model_name = model_name
        self.auto_fallback = auto_fallback
        self.auto_cooldown = auto_cooldown
        self.fallback_models = fallback_models or DEFAULT_FALLBACK_MODELS
        self.api_keys = api_keys
        self.system_instruction = (
            "You are an elite YouTube Storyteller and High-CPM Viral Scriptwriter specializing in Reddit Story channels (r/MaliciousCompliance, r/AntiWork, r/LegalAdvice, r/AITAH).\n"
            "Your goal is to adapt real Reddit posts into ultra-engaging, high-retention video narrations with zero dead pauses and maximum dramatic pacing.\n\n"
            "SCRIPT RULES:\n"
            "1. 3-SECOND HOOK (MANDATORY): The very first sentence MUST be an explosive paradox, financial consequence, or emotional confrontation that makes skipping impossible.\n"
            "   (e.g., 'My boss laughed in my face when I asked for a 3-dollar raise... but he wasn't laughing when his own rule cost the company 42,000 dollars in 48 hours.')\n"
            "2. PACING & WORD CHOICE: Write in active, punchy conversational English. Cut all useless fluff, throat-clearing, or Reddit acronym explanations. Focus on the conflict, the petty demands, the genius compliance, and the catastrophic fallout.\n"
            "3. PERSONA IDENTIFICATION: Detect whether the original narrator is male, female, or neutral, and pick the best persona ('male_dramatic', 'female_expressive', 'male_casual', 'young_fast').\n"
            "4. DUAL SCRIPT LENGTHS:\n"
            "   - 'shorts_script': 150 to 220 words (approx. 60-75s spoken at 1.20x speed).\n"
            "   - 'longform_script': 350 to 650 words (approx. 2.5-4 min spoken at 1.15x speed).\n"
            "5. ENGAGEMENT CALL TO ACTION (CTA): End with a sharp moral question (e.g., 'Did I take it too far, or did he get what he deserved? Drop your thoughts below.')\n\n"
            "OUTPUT JSON SCHEMA:\n"
            "{\n"
            "  \"title\": \"Catchy High-CTR YouTube Title (under 80 chars)\",\n"
            "  \"persona\": \"male_dramatic | female_expressive | male_casual | young_fast\",\n"
            "  \"recommended_voice\": \"en-US-ChristopherNeural | en-US-JennyNeural | en-US-GuyNeural | en-US-EricNeural\",\n"
            "  \"hook_text\": \"Explosive opening sentence\",\n"
            "  \"shorts_script\": \"Full spoken narration for vertical Short (150-220 words)\",\n"
            "  \"longform_script\": \"Extended full narration for long-form video (350-650 words)\",\n"
            "  \"youtube_description\": \"Complete YouTube description with hook, summary, and subscribe CTA\",\n"
            "  \"tags\": [\"#RedditStories\", \"#MaliciousCompliance\", \"#Shorts\", ...],\n"
            "  \"ui_card\": {\n"
            "      \"subreddit\": \"r/maliciouscompliance\",\n"
            "      \"author\": \"u/username\",\n"
            "      \"score\": \"24.8k\",\n"
            "      \"display_title\": \"Clean punchy title for Reddit card overlay\"\n"
            "  }\n"
            "}"
        )

    def _generate_algorithmic_fallback_script(self, raw_post: Dict[str, Any]) -> Dict[str, Any]:
        """Gera um roteiro estruturado de alta retenção quando a chave de API Gemini não estiver configurada."""
        title = raw_post.get("title", "Insane Reddit Story").strip()
        body = raw_post.get("body", "").strip()
        subreddit = raw_post.get("subreddit", "r/maliciouscompliance").strip()
        author = raw_post.get("author", "u/RedditUser").strip()
        score = raw_post.get("score", "24.5k")

        # Extrai frases para construir a narrativa
        sentences = [s.strip() for s in re.split(r"[.!?]+", body) if len(s.strip()) > 10]
        hook = f"My manager thought he could bully me by forcing strict compliance... but his little power trip ended up costing the company over forty thousand dollars."
        
        narrative_core = " ".join(sentences[:5]) if sentences else body[:400]
        cta = "Did I take the compliance too far, or did management get exactly what they asked for? Let me know in the comments."

        shorts_narration = f"{hook} {narrative_core} {cta}"
        
        # Garante tamanho ótimo (150 a 220 palavras)
        words = shorts_narration.split()
        if len(words) > 210:
            shorts_narration = " ".join(words[:200]) + f". {cta}"

        persona = "male_dramatic"
        if any(w in body.lower() for w in ["husband", "boyfriend", "my female", "im a woman", "as a girl"]):
            persona = "female_expressive"

        clean_sub_tag = "#" + re.sub(r"[^\w]", "", subreddit)
        tags = ["#RedditStories", clean_sub_tag, "#WorkplaceRevenge", "#Shorts", "#ViralStory", "#Storytime"]

        return {
            "title": title[:85],
            "persona": persona,
            "recommended_voice": PERSONA_VOICE_MAP[persona],
            "hook_text": hook,
            "shorts_script": shorts_narration,
            "longform_script": f"{hook} {body} {cta}",
            "youtube_description": (
                f"🔥 {title}\n\n"
                f"A viral workplace revenge and malicious compliance story from {subreddit} by {author}.\n\n"
                f"💬 What would you have done in this situation? Comment below!\n"
                f"🔔 Subscribe to Reddit Story Studio for the highest-stakes stories every day!"
            ),
            "tags": tags,
            "ui_card": {
                "subreddit": subreddit,
                "author": author,
                "score": score,
                "display_title": title
            }
        }

    def optimize_story(self, raw_post: Dict[str, Any], cooldown_callback=None, status_callback=None) -> Dict[str, Any]:
        with LogSpan("RedditStoryDirectorAgent.optimize_story", extra={"subreddit": raw_post.get("subreddit")}):
            configured_keys = resolve_gemini_api_keys(self.api_keys)
            if not configured_keys or not any(len(k) >= 20 for k in configured_keys):
                app_logger.warning("[RedditAgents] Nenhuma API Key do Gemini detectada. Usando Otimizador Algorítmico de Roteiro...")
                return self._generate_algorithmic_fallback_script(raw_post)

            prompt = (
                f"Optimize this real Reddit post into a viral High-CPM Video Script:\n\n"
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
                return data
            except Exception as e:
                app_logger.warning(f"[RedditAgents] Falha na chamada da API Gemini ({str(e)}). Usando fallback algorítmico...")
                return self._generate_algorithmic_fallback_script(raw_post)
