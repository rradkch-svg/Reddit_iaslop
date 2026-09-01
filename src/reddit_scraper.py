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
except ImportError:
    from logger import app_logger, LogSpan
    from reddit_agents import RedditStoryDirectorAgent

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


    text = html.unescape(raw_text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(?i)\b(tl;?dr|tldr)\b.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def scrape_subreddit_rss(subreddit: str = "maliciouscompliance", time_filter: str = "month", limit: int = 15) -> List[Dict[str, Any]]:
    clean_sub = subreddit.replace("r/", "").strip()
    url = f"https://old.reddit.com/r/{clean_sub}/top/.rss?t={time_filter}&limit={limit}"
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
                app_logger.warning(f"[RedditScraper] Resposta RSS vazia ou inválida para r/{clean_sub}")
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
    target_subs = [s.replace("r/", "").strip() for s in subreddits] if subreddits else HIGH_CPM_SUBREDDITS
    all_stories = []

    for sub in target_subs:
        stories = scrape_subreddit_rss(subreddit=sub, time_filter="month", limit=10)
        for s in stories:
            if s not in all_stories:
                all_stories.append(s)
            if len(all_stories) >= max_stories:
                break
        if len(all_stories) >= max_stories:
            break
        time.sleep(0.4)

    if not all_stories:
        app_logger.info("[RedditScraper] Raspagem ao vivo indisponível. Solicitando ao Gemini IA a criação de história inédita no molde exato do Reddit...")
        director = RedditStoryDirectorAgent()
        for sub in target_subs:
            story = director.synthesize_authentic_reddit_post(subreddit=f"r/{sub}")
            all_stories.append(story)
            if len(all_stories) >= max_stories:
                break

    return all_stories

