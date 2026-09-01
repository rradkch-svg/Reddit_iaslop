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
except ImportError:
    from logger import app_logger, LogSpan

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


# Coleção massiva de histórias virais completas de alto CPM para compilações longas (20+ minutos)
EXPANDED_HIGH_CPM_STORIES = [
    {
        "id": "story_01",
        "subreddit": "r/maliciouscompliance",
        "title": "Boss demanded I follow the employee handbook to the exact letter. It cost the company $42,000 in emergency overtime.",
        "author": "u/OvertimeMaster",
        "score": "38.2k",
        "upvote_ratio": "99%",
        "body": (
            "I worked as a senior industrial systems specialist at a manufacturing plant that operated twenty-four hours a day. "
            "We had a newly appointed regional director who had never stepped foot on an active factory floor. During his first week, "
            "he called an all-hands emergency meeting and announced that effective immediately, no technician was allowed to initiate "
            "preventative maintenance, touch backup valves, or restart critical infrastructure without an official written authorization memo "
            "personally signed by him, strictly citing Section 4.2 of the company handbook. \n\n"
            "I tried to explain to him that our primary cooling pumps for the server and CNC matrix experienced thermal pressure spikes "
            "every few days, and if we didn't bleed the lines within fifteen minutes of a sensor trip, the entire production floor would automatically shut down. "
            "He slammed his binder shut and told me: 'You are paid to follow protocol, not think. If you touch a valve without my written signature, you will be terminated.'\n\n"
            "The very next Friday at 4:55 PM, the primary cooling pump tripped its pressure sensor and threw an amber thermal warning code. "
            "Normally, I would walk over, cycle the release valve, and resolve the issue in under forty seconds. "
            "Instead, I sat at my desk, opened the official company memo template, and drafted an urgent authorization request. "
            "I walked to his corner office, but his door was locked. He had already clocked out for his three-day golf weekend and turned off his company phone. \n\n"
            "Per his explicit written instruction, I was required to remain on duty until the maintenance request was processed. "
            "So, I clocked into weekend emergency standby. By 6:15 PM, the server matrix overheated, triggering a full automated emergency shutdown. "
            "Three production assembly lines completely halted. The automated emergency protocol required two certified operators and one lead engineer "
            "to remain on site on double-time holiday pay around the clock while a line was down. \n\n"
            "For sixty straight hours, my team and I sat in the climate-controlled breakroom drinking coffee and getting paid triple-time. "
            "When the director strolled in on Monday morning at 8:30 AM holding his latte, the plant manager and the vice president of manufacturing "
            "were waiting in his office with the financial report. The sixty hours of halted assembly lines and emergency overtime cost the company forty-two thousand dollars. "
            "When they demanded to know why I didn't open the valve, I handed the vice president a printed copy of the director's signed policy memo. "
            "The director was escorted out of the building before noon."
        )
    },
    {
        "id": "story_02",
        "subreddit": "r/antiwork",
        "title": "Company refused my $3 per hour raise after saving them millions. They spent $140,000 hiring 3 consultants to replace me.",
        "author": "u/TechSpecialist_99",
        "score": "45.7k",
        "upvote_ratio": "98%",
        "body": (
            "For over four years, I was the sole database administrator and cloud architect for a mid-sized logistics enterprise. "
            "When I originally joined, their billing infrastructure was crashing twice a week. I completely rebuilt their legacy SQL cluster, "
            "automated their invoice reconciliation, and reduced server hosting overhead by seventy percent, saving the company an estimated two million dollars. \n\n"
            "During my annual performance review, I presented full metrics demonstrating my impact and requested a modest three-dollar per hour raise "
            "to match rising inflation in our metro area. My director looked at my paperwork, laughed out loud, and told me: "
            "'Everyone in tech thinks they are special. The reality is that anyone out of college can run your scripts. Nobody here is irreplaceable.'\n\n"
            "I didn't argue. I smiled, reached into my bag, and handed him my formal two-week notice that I had prepared beforehand. "
            "During my final two weeks, I wrote clear high-level documentation, but nobody on staff had the specialized security credentials "
            "or architectural background to manage the automated pipelines. Management didn't bother scheduling a handover or hiring a successor. \n\n"
            "Two weeks after my departure, their quarterly financial close triggered a schema lockup in their payment gateway. "
            "Customer credit cards were failing, and inventory updates froze across three warehouses. "
            "The director called my personal cell phone leaving frantic voicemails demanding that I log in remotely and fix the issue. "
            "I responded with a polite email stating that my independent consulting rate was two hundred and fifty dollars per hour with a minimum twenty-hour retainer. "
            "Instead of paying me, they contracted an external enterprise consultancy firm at ninety-five dollars an hour per engineer, "
            "requiring three full-time consultants for two months. In the end, the company spent over one hundred and forty thousand dollars "
            "to fix what a simple three-dollar raise would have maintained seamlessly."
        )
    },
    {
        "id": "story_03",
        "subreddit": "r/legaladvice",
        "title": "Landlord tried to steal my $4,500 security deposit with fraudulent contractor bills. The judge awarded me triple damages.",
        "author": "u/TenantJustice",
        "score": "31.4k",
        "upvote_ratio": "99%",
        "body": (
            "When I graduated from university, I rented a two-bedroom townhouse from a notoriously difficult private property management landlord. "
            "Knowing his reputation for nickel-and-diming departing tenants, I treated the move-out process like a forensic investigation. "
            "I spent two full days deep cleaning every baseboard, appliance, and window pane. On the final day of the lease, "
            "I brought in my professional mirrorless camera and recorded a thirty-minute 4K 60fps walkthrough video, "
            "holding up that morning's newspaper to establish the date and filming inside the oven, behind the refrigerator, and across every floorboard. \n\n"
            "Thirty days later, I received a certified letter from the landlord stating that my entire four thousand five hundred dollar security deposit "
            "was forfeited. On top of that, he demanded an additional two thousand eight hundred dollars for 'severe structural wood damage and pet contamination,' "
            "even though I had never owned a pet. Attached to the letter were official-looking itemized repair invoices from an LLC named Precision Woodworks. \n\n"
            "I did some basic public records research on the state corporation database and discovered that Precision Woodworks had been incorporated "
            "just three weeks prior, and the registered corporate agent was the landlord's brother-in-law. "
            "I immediately filed a claim in small claims court for bad-faith deposit retention. On our court date, the landlord showed up in an expensive suit "
            "claiming the apartment was left in squalor. When the judge asked for proof, the landlord handed over his invoices. "
            "I then stepped forward, plugged my laptop into the courtroom monitor, and played my pristine 4K move-out footage, "
            "followed by state registry documents showing the fraudulent conflict of interest. \n\n"
            "The judge was visibly furious at the landlord's deception. Under state statute, landlords who withhold deposits in bad faith "
            "are liable for statutory triple damages plus court filing fees and interest. The judge slammed down the gavel and awarded me "
            "thirteen thousand five hundred dollars on the spot. The landlord's face turned completely white as he was ordered to write a certified check within fourteen days."
        )
    },
    {
        "id": "story_04",
        "subreddit": "r/pettyrevenge",
        "title": "Entitled neighbor parked across my driveway every weekend. City zoning laws made him tear down his illegal extension.",
        "author": "u/DrivewayDefender",
        "score": "29.8k",
        "upvote_ratio": "97%",
        "body": (
            "I live in a historic suburban neighborhood with narrow streets and dedicated single-car driveways. "
            "A new neighbor bought the property adjacent to mine and immediately started hosting massive weekend gatherings with multiple vehicles. "
            "Rather than asking his guests to park down the street where there was ample public parking, "
            "he consistently parked his massive lifted pickup truck diagonally across the apron of my driveway, blocking my car completely. \n\n"
            "The first three times it happened, I walked over politely and asked him to move his truck so I could get to work. "
            "Every time, he rolled his eyes, took twenty minutes to come outside, and told me: 'Chill out, you don't own the street, I'll move it when I feel like it.' \n\n"
            "The breaking point came when my wife had a medical appointment and we were trapped in our own driveway for over an hour "
            "while he ignored our knocks at the door. I realized that arguing with him was useless, so I decided to fight him with bureaucracy. "
            "I noticed that he had recently built a brand-new two-story detached garage and sunroom right against our shared property line. \n\n"
            "I visited the municipal records office and pulled the zoning master map and building permits for his parcel. "
            "To my delight, I discovered that he had never pulled a single building, electrical, or structural permit for the construction. "
            "Furthermore, our city zoning code had a mandatory ten-foot setback rule for any permanent secondary structure, "
            "and his new garage was sitting less than eighteen inches from my property boundary. \n\n"
            "I filed a formal code compliance complaint with attached surveyor measurements and photographs. "
            "Within forty-eight hours, the city building inspector arrived with a stop-work notice and issued five separate structural violations. "
            "Because the structure violated non-negotiable zoning setbacks, the city refused to grant a retroactive variance. "
            "He was legally ordered to demolish the entire fifty-thousand-dollar extension at his own expense within sixty days. "
            "Needless to say, he never parked anywhere near my driveway again."
        )
    },
    {
        "id": "story_05",
        "subreddit": "r/financialindependence",
        "title": "Family called me cheap for 10 years while I saved and invested. Now they want me to pay off their luxury car debts.",
        "author": "u/FrugalFreedom",
        "score": "41.2k",
        "upvote_ratio": "98%",
        "body": (
            "Throughout my twenties and early thirties, I committed fully to financial independence. "
            "While my siblings and cousins were financing seventy-thousand-dollar luxury SUVs, taking five-star resort vacations on high-interest credit cards, "
            "and buying designer wardrobes to project wealth on social media, I drove a reliable used sedan, cooked my meals at home, "
            "and consistently invested fifty percent of my software engineering salary into diversified index funds and real estate investment trusts. \n\n"
            "Every family Thanksgiving and Christmas dinner was the same ordeal. My relatives would mock my lifestyle, "
            "calling me 'cheap,' asking when I was going to 'start living like an adult,' and making jokes about my older car. "
            "I never engaged in their arguments or bragged about my balance sheet; I simply focused on my long-term compounding growth. \n\n"
            "By the time I turned thirty-five, my portfolio had crossed the seven-figure threshold, generating enough passive dividend and rental cash flow "
            "to cover all of my living expenses indefinitely. I quietly transitioned to part-time consulting on projects that genuinely interested me. \n\n"
            "Recently, interest rates rose and credit card minimum payments ballooned. My older brother and sister-in-law found themselves "
            "drowning in over ninety thousand dollars of consumer debt across two leased German luxury vehicles, personal loans, and store credit cards. "
            "During a family dinner at my parents' house, my brother brought out a stack of bills and announced that since I was 'single and had no real expenses,' "
            "it was my familial obligation to step in and pay off their car loans to 'keep the family afloat.' \n\n"
            "When I calmly told him that I would not be paying a single dollar towards their lifestyle debts, the entire table erupted in outrage. "
            "They accused me of being selfish, hoardish, and heartless. I looked at my brother and said: "
            "'For ten years, you mocked my discipline while driving cars you couldn't afford. You didn't want my financial advice back then, "
            "and you are not getting my money now.' I stood up, paid for my share of dinner, and walked out. "
            "True wealth is not about what you display to the world; it is the freedom to say no."
        )
    },
    {
        "id": "story_06",
        "subreddit": "r/maliciouscompliance",
        "title": "Strict executive banned working from home for IT team. The entire server migration took 4 months instead of 2 days.",
        "author": "u/SysAdminHero",
        "score": "36.8k",
        "upvote_ratio": "99%",
        "body": (
            "Our company was undergoing a massive multi-million dollar cloud infrastructure migration. "
            "Our engineering team of five was responsible for moving hundreds of virtualized database instances over a holiday weekend. "
            "Because database replication requires overnight monitoring between 2:00 AM and 6:00 AM when customer traffic is lowest, "
            "our standard operating procedure was to execute the scripts from our secure home workstations with multi-factor VPN access. \n\n"
            "Enter our newly appointed Chief Operations Officer. He had a dogmatic hatred for remote work and instituted a strict mandatory policy: "
            "'Every single hour worked must be performed physically inside our downtown corporate office headquarters during standard business hours.' \n\n"
            "We formally warned him in writing that our production database locks could not be held during daytime business hours without disrupting "
            "thousands of retail checkout terminals nationwide. He replied with an all-caps email: 'You will work 9:00 AM to 5:00 PM at your office desks. No exceptions.' \n\n"
            "So, we maliciously complied. Every morning at 9:00 AM sharp, our entire team swiped into the office. "
            "Because we could only migrate tiny non-critical micro-batches during business hours to prevent the retail network from crashing, "
            "what was scheduled to be a forty-eight-hour weekend cutover stretched out across four agonizing months. \n\n"
            "Project milestones were missed, third-party vendor licensing penalties accumulated at eighteen thousand dollars per week, "
            "and the board of directors began demanding answers for the catastrophic schedule overrun. "
            "During the executive board audit, our lead engineer presented the timeline showing that ninety-five percent of the delay "
            "was caused directly by the inability to perform night-time maintenance due to the COO's written mandate. "
            "The board immediately revoked the policy and reassigned the COO to a non-operational advisory role."
        )
    }
]

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
        app_logger.warning("[RedditScraper] Usando coleção expandida de histórias de alto CPM para compilação...")
        if subreddits:
            matched = [s for s in EXPANDED_HIGH_CPM_STORIES if any(ts.lower() in s["subreddit"].lower() for ts in target_subs)]
            all_stories = matched if matched else EXPANDED_HIGH_CPM_STORIES
        else:
            all_stories = list(EXPANDED_HIGH_CPM_STORIES)

    return all_stories
