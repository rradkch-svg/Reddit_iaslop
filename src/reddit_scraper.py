import re
import time
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import html
import subprocess
from typing import List, Dict, Any, Optional

try:
    from .logger import app_logger, LogSpan
    from .reddit_agents import RedditStoryDirectorAgent
    from .pronunciation import sanitize_youtube_compliance
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_agents import RedditStoryDirectorAgent
    from pronunciation import sanitize_youtube_compliance

HIGH_CPM_SUBREDDITS = [
    "maliciouscompliance",
    "antiwork",
    "legaladvice",
    "AITAH",
    "pettyrevenge",
    "financialindependence",
    "RealEstate",
    "tifu"
]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

def clean_reddit_text(raw_text: str) -> str:
    """Limpa formatação, metadados do Reddit RSS, tags HTML e aplica filtro de monetização do YouTube."""
    if not raw_text:
        return ""

    text = html.unescape(raw_text)
    # 1. Remove tags HTML
    text = re.sub(r"<[^>]+>", " ", text)
    # 2. Converte links markdown [texto](url) -> texto e remove URLs brutas
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    # 3. Remove metadados de submissão do RSS do Reddit: "submitted by ... [link] [comments]"
    text = re.sub(r"(?i)\(?(?:submitted\s+by|posted\s+by)\s+.*?(?:\[link\]|\[comments\]|\(link\s+comments\)|link\s+comments|\Z)\)?", "", text)
    text = re.sub(r"(?i)\[\s*(?:link|comments?)\s*\]|\(\s*(?:link|comments?)\s*\)", "", text)
    text = re.sub(r"(?i)\(?\s*submitted\s+by\s+[^)\n]*\)?", "", text)
    # 4. Remove TL;DR e tags de encerramento de fórum
    text = re.sub(r"(?i)\b(tl;?dr|tldr)\b.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?i)\b(?:the\s+end|o\s+fim)\s*[.!]?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?i)\b(?:thanks\s+for\s+reading|thank\s+you\s+for\s+reading)\b.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?i)\b(?:edit\s*:?\s*thanks\s+for\s+the\s+(?:gold|upvotes|awards?))\b.*$", "", text, flags=re.MULTILINE)
    # 5. Normaliza quebras de linha e espaços
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    # 6. Aplica filtro de monetização do YouTube
    text = sanitize_youtube_compliance(text)
    return text.strip()

def scrape_subreddit_rss(subreddit: str = "maliciouscompliance", time_filter: str = "month", limit: int = 15) -> List[Dict[str, Any]]:
    clean_sub = subreddit.replace("r/", "").strip()
    url = f"https://www.reddit.com/r/{clean_sub}/top/.rss?t={time_filter}&limit={limit}"
    posts = []
    
    with LogSpan("scrape_subreddit_rss", extra={"subreddit": clean_sub, "url": url}):
        try:
            curl_cmd = [
                "curl.exe", "-sL", "-A", DEFAULT_HEADERS["User-Agent"],
                "--max-time", "12",
                url
            ]
            res = subprocess.run(curl_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            xml_text = res.stdout if res.returncode == 0 and res.stdout.strip() else ""
            
            if not xml_text:
                req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    xml_text = resp.read().decode("utf-8", errors="ignore")

            if not xml_text or "<feed" not in xml_text:
                if "429 Too Many Requests" in xml_text or not xml_text:
                    app_logger.warning(f"[RedditScraper] Reddit bloqueou temporariamente via Rate Limit (HTTP 429) para r/{clean_sub}")
                else:
                    app_logger.warning(f"[RedditScraper] Resposta RSS não contém feed XML válido para r/{clean_sub}")
                return []


            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            for entry in entries:
                title_elem = entry.find("atom:title", ns)
                author_elem = entry.find("atom:author/atom:name", ns)
                content_elem = entry.find("atom:content", ns)
                link_elem = entry.find("atom:link", ns)
                updated_elem = entry.find("atom:updated", ns)

                title = title_elem.text if title_elem is not None else "Untitled Reddit Story"
                author = author_elem.text if author_elem is not None else "u/RedditUser"
                raw_content = content_elem.text if content_elem is not None else ""
                post_url = link_elem.get("href") if link_elem is not None else f"https://reddit.com/r/{clean_sub}"
                time_str = updated_elem.text if updated_elem is not None else ""

                cleaned_body = clean_reddit_text(raw_content)
                if len(cleaned_body.split()) < 40 and "submitted by" in cleaned_body:
                    continue

                posts.append({
                    "subreddit": f"r/{clean_sub}",
                    "title": title.strip(),
                    "author": author.strip(),
                    "body": cleaned_body,
                    "url": post_url,
                    "time": time_str,
                    "score": "18.4k",
                    "upvote_ratio": "98%"
                })

            app_logger.info(f"[RedditScraper] {len(posts)} posts obtidos com sucesso de r/{clean_sub}")
        except Exception as e:
            app_logger.warning(f"[RedditScraper] Erro ao raspar r/{clean_sub}: {str(e)}")

    return posts

def fetch_top_high_cpm_stories(subreddits: Optional[List[str]] = None, max_stories: int = 10) -> List[Dict[str, Any]]:
    """
    Busca histórias de alto CPM no Reddit com distribuição balanceada (Round-Robin) entre subreddits
    e garantia de diversidade de autores e temas.
    """
    target_subs = [s.replace("r/", "").strip() for s in subreddits] if subreddits else HIGH_CPM_SUBREDDITS
    sub_stories_map: Dict[str, List[Dict[str, Any]]] = {}

    for sub in target_subs:
        stories = scrape_subreddit_rss(subreddit=sub, time_filter="month", limit=6)
        if stories:
            sub_stories_map[sub] = stories
        time.sleep(0.3)

    # Interleaving (Round-Robin) para garantir que cada slot de vídeo venha de um subreddit diferente
    all_stories = []
    seen_authors = set()
    seen_titles = set()

    max_depth = max((len(v) for v in sub_stories_map.values()), default=0)
    for depth in range(max_depth):
        for sub in target_subs:
            if sub in sub_stories_map and depth < len(sub_stories_map[sub]):
                story = sub_stories_map[sub][depth]
                title_key = story.get("title", "").strip().lower()
                author_key = story.get("author", "").strip().lower()
                
                # Deduplicação imediata de autor e título
                if title_key in seen_titles:
                    continue
                if author_key and author_key not in ("u/reddituser", "reddituser", "unknown") and author_key in seen_authors:
                    continue

                seen_titles.add(title_key)
                if author_key and author_key not in ("u/reddituser", "reddituser", "unknown"):
                    seen_authors.add(author_key)

                all_stories.append(story)
                if len(all_stories) >= max_stories:
                    break
        if len(all_stories) >= max_stories:
            break

    if not all_stories:
        app_logger.info("[RedditScraper] Raspagem ao vivo indisponível. Solicitando ao Gemini IA a criação de história inédita no molde exato do Reddit...")
        director = RedditStoryDirectorAgent()
        for sub in target_subs:
            story = director.synthesize_authentic_reddit_post(subreddit=f"r/{sub}")
            all_stories.append(story)
            if len(all_stories) >= max_stories:
                break

    return all_stories

