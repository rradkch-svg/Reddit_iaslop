import os
import re
import time
import json
import random
from typing import Dict, Any, List, Optional, Tuple

try:
    from .logger import app_logger, LogSpan
    from .gemini_client import generate_with_resilience, resolve_gemini_api_keys, DEFAULT_FALLBACK_MODELS
except ImportError:
    from logger import app_logger, LogSpan
    from gemini_client import generate_with_resilience, resolve_gemini_api_keys, DEFAULT_FALLBACK_MODELS

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
    def __init__(self, model_name="gemini-flash-lite-latest", auto_fallback=True, auto_cooldown=True, fallback_models=None, api_keys=None):
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

    def _generate_algorithmic_fallback_script(self, raw_post: Dict[str, Any]) -> Dict[str, Any]:
        """Gera um roteiro algorítmico contextual de alta retenção com suporte a até 2.5 minutos e transição fluida para o CTA."""
        title = raw_post.get("title", "Insane Reddit Story").strip()
        body = raw_post.get("body", "").strip()
        subreddit = raw_post.get("subreddit", "r/maliciouscompliance").strip()
        author = raw_post.get("author", "u/RedditUser").strip()
        score = raw_post.get("score", "24.5k")

        clean_title = title.rstrip(".")
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
        shorts_narration = f"{core_story}. {cta}"

        persona = "male_dramatic"
        body_lower = body.lower()
        if any(w in body_lower for w in ["husband", "boyfriend", "my female", "im a woman", "as a girl", "sister"]):
            persona = "female_expressive"
        elif "landlord" in title.lower() or "deposit" in title.lower() or "neighbor" in title.lower():
            persona = "male_casual"

        clean_sub_tag = "#" + re.sub(r"[^\w]", "", subreddit)
        tags = ["#RedditStories", clean_sub_tag, "#WorkplaceDrama", "#Shorts", "#ViralStory", "#Storytime", "#RedditMinute"]

        clean_body = body.rstrip(".!? ")
        longform_narration = f"{hook} {clean_body}. {cta}"

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
                
                # Garante que o final do shorts tenha uma pergunta para engajar se não houver
                shorts_txt = data.get("shorts_script", "").strip()
                if not any(q in shorts_txt[-150:] for q in ["?", "comment", "thoughts", "verdict", "below", "opinion", "what would you"]):
                    cta = random.choice(ENGAGEMENT_QUESTIONS)
                    clean_core = shorts_txt.rstrip(".!? ")
                    data["shorts_script"] = f"{clean_core}. {cta}"

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
            f"Create exactly 8 rich chronological chapters of this SAME ongoing saga (approx. 450-550 words per chapter, total ~3,800 to 4,200 words):\n"
            f"1. Chapter 1: The Background, Setting the Stage & The Absurd Directive\n"
            f"2. Chapter 2: The Pushback, Ignored Warnings & Escalating Tensions\n"
            f"3. Chapter 3: The Secret Plan & Documenting Every Detail in Writing\n"
            f"4. Chapter 4: The Execution & The Flawless Malicious Compliance\n"
            f"5. Chapter 5: The Catastrophe Unfolds & The Panic Over the Weekend\n"
            f"6. Chapter 6: Update 1 - The Monday Morning Confrontation & Executive Inquest\n"
            f"7. Chapter 7: Update 2 - HR Audits, Legal Ramifications & The $42k/Cost Assessment\n"
            f"8. Chapter 8: Epilogue - The Fallout, Where Are They Now & Final Moral Justice\n\n"
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
            f"      \"chapter_title\": \"The Directive\",\n"
            f"      \"card_display_title\": \"Part 1: The Directive\",\n"
            f"      \"narration_text\": \"Full rich chapter script (450-550 words)...\"\n"
            f"    }},\n"
            f"    ...\n"
            f"  ]\n"
            f"}}"
        )

        raw_text = generate_with_resilience(
            prompt=prompt,
            system_instruction="You write immersive 25-minute deep-dive YouTube narrations for single continuous stories.",
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

        # Garante que cada capítulo cumpra o rigor de duração para 25 minutos (total >= 3500 palavras)
        for i, ch in enumerate(chapters):
            ch_text = ch.get("narration_text", "").strip()
            ch_words = ch_text.split()
            if len(ch_words) < 450:
                pad_text = (
                    "Every single memo, timestamp, and communication was documented meticulously to ensure total accountability. "
                    "The operational implications escalated rapidly as each stage of the directive was executed to the letter. "
                    "Leadership remained oblivious to the cascading consequences while the financial costs mounted continuously."
                )
                while len(ch_words) < 460:
                    ch_words.extend(pad_text.split())
                ch["narration_text"] = " ".join(ch_words[:480])

        return data

    def _generate_algorithmic_25min_story(
        self,
        raw_post: Dict[str, Any],
        target_minutes: float
    ) -> Dict[str, Any]:
        """Expansão algorítmica profunda para garantir um vídeo de 25 minutos de uma história única."""
        title = raw_post.get("title", "Insane Reddit Story").strip()
        body = raw_post.get("body", "").strip()
        subreddit = raw_post.get("subreddit", "r/maliciouscompliance").strip()
        author = raw_post.get("author", "u/RedditUser").strip()
        score = raw_post.get("score", "38.2k")

        persona = "male_dramatic"
        if any(w in body.lower() for w in ["husband", "boyfriend", "im a woman", "as a girl"]):
            persona = "female_expressive"
        elif "landlord" in title.lower() or "deposit" in title.lower() or "neighbor" in title.lower():
            persona = "male_casual"

        voice = PERSONA_VOICE_MAP.get(persona, "en-US-ChristopherNeural")

        # 8 Capítulos profundos da mesma história única
        chapter_blueprints = [
            {
                "num": 1,
                "title": "The Background & The Absurd Policy",
                "card_title": f"Part 1: {title[:50]}",
                "focus": "Establish the workplace environment, company culture, role of narrator, and the arrival of the antagonist who introduces an unreasonable rule."
            },
            {
                "num": 2,
                "title": "The Warning & The Arrogant Rejection",
                "focus": "The narrator formally explains why the policy will cause disaster. The antagonist aggressively rejects the warning, demanding unquestioning obedience."
            },
            {
                "num": 3,
                "title": "Building the Paper Trail & Secret Strategy",
                "focus": "The narrator documents everything in writing, confirms the explicit written order via email, and prepares for the inevitable breakdown."
            },
            {
                "num": 4,
                "title": "The Trigger & The Flawless Compliance",
                "focus": "The exact moment the crisis occurs on Friday afternoon. The antagonist clocks out. The narrator follows orders to the exact letter without interfering."
            },
            {
                "num": 5,
                "title": "The Weekend Meltdown & Emergency Standby",
                "focus": "The system goes down. Production freezes. The emergency overtime clock begins running around the clock at double and triple holiday pay."
            },
            {
                "num": 6,
                "title": "Update 1: Monday Morning Inquest",
                "focus": "Monday 8:30 AM. The antagonist arrives with coffee to find the Vice President and plant leadership waiting with the financial fallout report."
            },
            {
                "num": 7,
                "title": "Update 2: The Audit, Financials & The Escort",
                "focus": "The printed proof is handed over. The forensic audit proves the loss was 100% caused by the policy. The antagonist faces immediate termination."
            },
            {
                "num": 8,
                "title": "Epilogue: Moral Victory & Final Lessons",
                "focus": "The workplace recovery, the bonus/settlement awarded, where everyone is now, and a concluding message to the audience."
            }
        ]

        chapters = []
        body_paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        base_body_text = " ".join(body_paras)

        for bp in chapter_blueprints:
            num = bp["num"]
            ch_title = bp["title"]
            card_title = bp.get("card_title", f"Part {num}: {ch_title}")
            
            # Gera texto rico e extenso para cada capítulo (~480 a 520 palavras)
            ch_script = (
                f"Chapter {num}: {ch_title}. "
                f"When dealing with high-stakes corporate bureaucracy, one golden rule reigns supreme: never interrupt an adversary while they are in the process of destroying themselves. "
                f"{base_body_text} "
                f"In this stage of the situation, the dynamics reached a critical boiling point. Every communication was logged, timestamped, and archived. "
                f"The protocols were crystal clear, yet the arrogance of leadership blinded them to the impending financial catastrophe. "
                f"As events progressed into the weekend, the operational consequences began compounding hour by hour. "
                f"Emergency standby teams were mobilized, and the cost meter was running continuously. "
                f"When Monday morning arrived, reality collided with corporate hubris in the most spectacular fashion imaginable."
            )
            
            words = ch_script.split()
            # Garante que cada capítulo tenha em torno de 480 a 500 palavras
            while len(words) < 480:
                words.extend("Every single memo, signature, and timestamp proved beyond a shadow of a doubt that following their orders to the exact letter was the catalyst for the entire forty-two thousand dollar disaster.".split())
            
            final_chapter_text = " ".join(words[:500]).rstrip(".!? ")
            if num == 8:
                cta = random.choice(ENGAGEMENT_QUESTIONS)
                final_chapter_text += f". {cta}"

            chapters.append({
                "chapter_num": num,
                "chapter_title": ch_title,
                "card_display_title": card_title,
                "narration_text": final_chapter_text
            })

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
            "chapters": chapters
        }
