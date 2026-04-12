import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Config from environment variables ────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "30"))
SITE_URL = "https://www.massimodutti.com/sg/"
SGT = pytz.timezone("Asia/Singapore")

SALE_KEYWORDS = [
    "sale", "% off", "discount", "promotion", "offer",
    "reduced", "clearance", "special price", "end of season",
    "up to", "save", "promo",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-SG,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Track whether we already sent a sale alert (avoid spamming)
last_sale_state = False


def fetch_page():
    """Fetch the Massimo Dutti SG homepage."""
    resp = requests.get(SITE_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def detect_sale(html: str):
    """Return (on_sale, keywords_found, snippets)."""
    soup = BeautifulSoup(html, "html.parser")
    text_lower = soup.get_text(" ", strip=True).lower()

    found_keywords = [kw for kw in SALE_KEYWORDS if kw in text_lower]

    # Try to pull meaningful snippets from banner/hero elements
    snippets = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "span", "div"]):
        tag_text = tag.get_text(" ", strip=True)
        if len(tag_text) < 5 or len(tag_text) > 200:
            continue
        if any(kw in tag_text.lower() for kw in SALE_KEYWORDS):
            clean = " ".join(tag_text.split())
            if clean and clean not in snippets:
                snippets.append(clean)
        if len(snippets) >= 5:
            break

    return bool(found_keywords), found_keywords, snippets


def send_discord(keywords, snippets):
    """Send a Discord webhook message."""
    if not DISCORD_WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL not set — skipping Discord alert")
        return

    now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")
    snippet_line = f'\n> *"{snippets[0]}"*' if snippets else ""
    kw_line = ", ".join(f"`{k}`" for k in keywords[:8])

    payload = {
        "username": "Massimo Dutti SG Monitor",
        "embeds": [
            {
                "title": "🛍️  Sale Alert — Massimo Dutti Singapore",
                "description": (
                    f"**A sale has been detected on the Singapore site!**\n\n"
                    f"**Keywords found:** {kw_line}"
                    f"{snippet_line}\n\n"
                    f"🔗 [Shop Now]({SITE_URL})"
                ),
                "color": 0x22C55E,
                "url": SITE_URL,
                "footer": {"text": f"Detected at {now_sgt}"},
            }
        ],
    }

    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    if resp.ok:
        log.info("Discord alert sent successfully ✓")
    else:
        log.error("Discord alert failed: %s %s", resp.status_code, resp.text[:200])


def send_discord_startup():
    """Send a startup message so you know the bot is live."""
    if not DISCORD_WEBHOOK_URL:
        return
    now_sgt = datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")
    payload = {
        "username": "Massimo Dutti SG Monitor",
        "embeds": [
            {
                "title": "✅  Monitor is live!",
                "description": (
                    f"Massimo Dutti SG sale monitor has started.\n"
                    f"Checking every **{CHECK_INTERVAL_MINUTES} minutes**.\n\n"
                    f"You'll be pinged here the moment a sale is detected."
                ),
                "color": 0x5865F2,
                "footer": {"text": f"Started at {now_sgt}"},
            }
        ],
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    log.info("Startup Discord message sent")


def run():
    global last_sale_state
    log.info("=" * 50)
    log.info("Massimo Dutti SG Sale Monitor starting up")
    log.info("Site: %s", SITE_URL)
    log.info("Interval: %d minutes", CHECK_INTERVAL_MINUTES)
    log.info("Discord: %s", "configured ✓" if DISCORD_WEBHOOK_URL else "NOT SET ✗")
    log.info("=" * 50)

    send_discord_startup()

    while True:
        now = datetime.now(SGT).strftime("%d %b %Y %H:%M SGT")
        log.info("Checking website... [%s]", now)

        try:
            html = fetch_page()
            on_sale, keywords, snippets = detect_sale(html)

            if on_sale:
                log.info("🛍  SALE DETECTED! Keywords: %s", ", ".join(keywords))
                if snippets:
                    log.info("   Snippet: %s", snippets[0])
                # Only alert on state change (sale just started) OR every check while sale is on
                send_discord(keywords, snippets)
                last_sale_state = True
            else:
                log.info("✓  No sale detected")
                if last_sale_state:
                    log.info("   (Sale appears to have ended)")
                last_sale_state = False

        except requests.RequestException as e:
            log.error("Network error: %s", e)
        except Exception as e:
            log.error("Unexpected error: %s", e)

        log.info("Sleeping for %d minutes...", CHECK_INTERVAL_MINUTES)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    run()
