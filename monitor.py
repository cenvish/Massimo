import os
import time
import json
import asyncio
import logging
import re
import threading
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config from environment ───────────────────────────────────────────────────
BOT_TOKEN            = os.environ["DISCORD_BOT_TOKEN"]
WEBHOOK_URL          = os.environ.get("DISCORD_WEBHOOK_URL", "")
ALERT_CHANNEL_ID     = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))
CHECK_INTERVAL_MIN   = int(os.environ.get("CHECK_INTERVAL_MINUTES", "30"))
SGT                  = pytz.timezone("Asia/Singapore")

BASKET_FILE = "/data/basket.json"   # persisted via Railway volume
STATE_FILE  = "/data/state.json"

SALE_KEYWORDS = [
    "sale", "% off", "discount", "promotion", "offer",
    "reduced", "clearance", "special price", "end of season",
    "up to", "save", "promo",
]
OUT_OF_STOCK_PHRASES = [
    "out of stock", "sold out", "unavailable",
    "currently unavailable", "notify me",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-SG,en;q=0.9",
}

# ── Basket persistence ────────────────────────────────────────────────────────
os.makedirs("/data", exist_ok=True)

def load_basket():
    try:
        with open(BASKET_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_basket(basket):
    with open(BASKET_FILE, "w") as f:
        json.dump(basket, f, indent=2)

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ── Scraping ──────────────────────────────────────────────────────────────────
def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

def parse_price(soup):
    prices = []
    for sel in ["[class*='price']", "[itemprop='price']", "[data-price]", ".product-price"]:
        for el in soup.select(sel):
            for p in re.findall(r"S?\$?\s*(\d+(?:\.\d{2})?)", el.get_text(" ", strip=True)):
                prices.append(float(p))
    prices = sorted(set(prices))
    if len(prices) >= 2:
        return {"current": prices[0], "original": prices[-1], "on_sale": prices[0] < prices[-1]}
    elif len(prices) == 1:
        return {"current": prices[0], "original": None, "on_sale": False}
    return None

def parse_product(url, name):
    html  = fetch(url)
    soup  = BeautifulSoup(html, "html.parser")
    text  = soup.get_text(" ", strip=True)
    lower = text.lower()

    on_sale   = any(kw in lower for kw in SALE_KEYWORDS)
    sale_kws  = [kw for kw in SALE_KEYWORDS if kw in lower]
    price     = parse_price(soup)
    if price and price["on_sale"]:
        on_sale = True

    out = any(p in lower for p in OUT_OF_STOCK_PHRASES)

    snippets = []
    for tag in soup.find_all(["h1","h2","h3","p","span"]):
        t = tag.get_text(" ", strip=True)
        if 4 < len(t) < 150 and any(kw in t.lower() for kw in SALE_KEYWORDS):
            c = " ".join(t.split())
            if c not in snippets:
                snippets.append(c)
        if len(snippets) >= 3:
            break

    title_tag  = soup.find("h1") or soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else name

    return {
        "on_sale": on_sale, "sale_keywords": sale_kws,
        "snippets": snippets, "in_stock": not out,
        "price": price, "page_title": page_title,
    }

# ── Discord embeds ────────────────────────────────────────────────────────────
def now_sgt():
    return datetime.now(SGT).strftime("%d %b %Y, %I:%M %p SGT")

def make_sale_embed(item, result):
    p = result["price"]
    desc = [f"**{result['page_title']}** is on sale!\n"]
    if p:
        if p["original"]:
            desc.append(f"~~S${p['original']:.2f}~~ → **S${p['current']:.2f}**\n")
        else:
            desc.append(f"Price: **S${p['current']:.2f}**\n")
    if result["snippets"]:
        desc.append(f'\n> *"{result["snippets"][0]}"*')
    kws = ", ".join(f"`{k}`" for k in result["sale_keywords"][:6])
    desc.append(f"\n\n**Keywords:** {kws}\n🔗 [View Product]({item['url']})")
    e = discord.Embed(title=f"🏷️  Price Drop — {item['name']}", description="".join(desc), color=0x22C55E, url=item["url"])
    e.set_footer(text=f"Detected at {now_sgt()}")
    return e

def make_restock_embed(item, result):
    p = result["price"]
    desc = [f"**{result['page_title']}** is back in stock!"]
    if p:
        desc.append(f"\nPrice: **S${p['current']:.2f}**")
    if result["on_sale"]:
        desc.append("\n🏷️ *And it's currently on sale!*")
    desc.append(f"\n\n🔗 [View Product]({item['url']})")
    e = discord.Embed(title=f"✅  Back in Stock — {item['name']}", description="".join(desc), color=0x3B82F6, url=item["url"])
    e.set_footer(text=f"Detected at {now_sgt()}")
    return e

# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="!", intents=intents)

# ── Slash commands ────────────────────────────────────────────────────────────
@bot.tree.command(name="add", description="Add a Massimo Dutti product to your watchlist")
@app_commands.describe(
    url="Full product URL from massimodutti.com/sg",
    name="A short label for this item",
    sale="Alert when price drops (default: yes)",
    stock="Alert when back in stock (default: yes)",
)
async def cmd_add(interaction: discord.Interaction, url: str, name: str,
                  sale: bool = True, stock: bool = True):
    await interaction.response.defer(thinking=True)

    if "massimodutti.com" not in url:
        await interaction.followup.send("❌ URL must be from **massimodutti.com**.", ephemeral=True)
        return

    basket = load_basket()
    if any(i["url"] == url for i in basket):
        await interaction.followup.send(f"⚠️ That URL is already in your watchlist.", ephemeral=True)
        return

    # Try fetching so we confirm the page is valid
    try:
        result = parse_product(url, name)
    except Exception as ex:
        await interaction.followup.send(f"❌ Couldn't fetch that URL: `{ex}`", ephemeral=True)
        return

    item = {"name": name, "url": url, "alert_on_sale": sale, "alert_on_stock": stock}
    basket.append(item)
    save_basket(basket)

    p     = result["price"]
    price = f"S${p['current']:.2f}" if p else "unknown"
    stock_status = "✅ In stock" if result["in_stock"] else "❌ Out of stock"
    sale_status  = "🏷️ On sale now!" if result["on_sale"] else "No active sale"

    e = discord.Embed(
        title=f"➕  Added to Watchlist",
        description=(
            f"**{name}**\n"
            f"{result['page_title']}\n\n"
            f"💰 Price: **{price}**\n"
            f"📦 Stock: {stock_status}\n"
            f"🏷️ Sale: {sale_status}\n\n"
            f"🔔 Alerts: {'Sale ' if sale else ''}{'Stock' if stock else ''}\n"
            f"🔗 [View Product]({url})"
        ),
        color=0x5865F2,
    )
    e.set_footer(text=f"Watchlist now has {len(basket)} item(s)")
    await interaction.followup.send(embed=e)


@bot.tree.command(name="remove", description="Remove an item from your watchlist")
@app_commands.describe(name="The name of the item to remove")
async def cmd_remove(interaction: discord.Interaction, name: str):
    basket = load_basket()
    new    = [i for i in basket if i["name"].lower() != name.lower()]
    if len(new) == len(basket):
        await interaction.response.send_message(f"❌ No item named **{name}** found. Use `/list` to see your watchlist.", ephemeral=True)
        return
    save_basket(new)
    await interaction.response.send_message(f"✅ **{name}** removed from your watchlist. ({len(new)} item(s) remaining)", ephemeral=True)


@bot.tree.command(name="list", description="Show all items in your watchlist")
async def cmd_list(interaction: discord.Interaction):
    basket = load_basket()
    if not basket:
        await interaction.response.send_message("Your watchlist is empty. Use `/add` to add items!", ephemeral=True)
        return

    lines = []
    for i, item in enumerate(basket, 1):
        alerts = []
        if item.get("alert_on_sale"):  alerts.append("💰 sale")
        if item.get("alert_on_stock"): alerts.append("📦 stock")
        lines.append(f"**{i}. {item['name']}**\n{', '.join(alerts)}\n[Link]({item['url']})")

    e = discord.Embed(
        title=f"📋  Watchlist ({len(basket)} item{'s' if len(basket)!=1 else ''})",
        description="\n\n".join(lines),
        color=0xC8A96E,
    )
    e.set_footer(text=f"Checking every {CHECK_INTERVAL_MIN} minutes")
    await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="check", description="Run an immediate check on all watchlist items right now")
async def cmd_check(interaction: discord.Interaction):
    basket = load_basket()
    if not basket:
        await interaction.response.send_message("Your watchlist is empty.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    lines  = []
    for item in basket:
        try:
            r     = parse_product(item["url"], item["name"])
            p     = r["price"]
            price = f"S${p['current']:.2f}" if p else "—"
            sale  = "🏷️ On sale" if r["on_sale"] else "No sale"
            stk   = "✅ In stock" if r["in_stock"] else "❌ Out of stock"
            lines.append(f"**{item['name']}**\n{stk} · {sale} · {price}")
        except Exception as ex:
            lines.append(f"**{item['name']}**\n⚠️ Error: {ex}")
        time.sleep(1)

    e = discord.Embed(
        title="🔍  Instant Check Results",
        description="\n\n".join(lines),
        color=0x60A5FA,
    )
    e.set_footer(text=f"Checked at {now_sgt()}")
    await interaction.followup.send(embed=e)


@bot.tree.command(name="help", description="Show how to use this bot")
async def cmd_help(interaction: discord.Interaction):
    e = discord.Embed(
        title="🛍️  Massimo Dutti SG Monitor — Help",
        description=(
            "I watch products on massimodutti.com/sg and alert you to sales and restocks.\n\n"
            "**Commands:**\n\n"
            "`/add [url] [name]` — Add a product to your watchlist\n"
            "> Example: `/add https://massimodutti.com/sg/... Navy Trousers`\n\n"
            "`/remove [name]` — Remove a product by name\n\n"
            "`/list` — Show all watched items\n\n"
            "`/check` — Run an instant check right now\n\n"
            "`/help` — Show this message\n\n"
            "**How to get a product URL:**\n"
            "Go to massimodutti.com/sg → click a product → copy the URL from your browser bar."
        ),
        color=0xC8A96E,
    )
    e.set_footer(text=f"Checking every {CHECK_INTERVAL_MIN} minutes automatically")
    await interaction.response.send_message(embed=e, ephemeral=True)


# ── Background monitor task ───────────────────────────────────────────────────
@tasks.loop(minutes=CHECK_INTERVAL_MIN)
async def monitor_task():
    basket = load_basket()
    state  = load_state()

    if not basket:
        log.info("Watchlist is empty, skipping check")
        return

    channel = bot.get_channel(ALERT_CHANNEL_ID)
    log.info("─── Scheduled check (%d items) ───", len(basket))

    for item in basket:
        key  = item["url"]
        prev = state.get(key, {"on_sale": False, "in_stock": True})
        try:
            result = parse_product(item["url"], item["name"])
            log.info("[%s] sale=%s in_stock=%s", item["name"], result["on_sale"], result["in_stock"])

            if channel:
                if item.get("alert_on_sale") and result["on_sale"] and not prev["on_sale"]:
                    await channel.send(embed=make_sale_embed(item, result))

                if item.get("alert_on_stock") and result["in_stock"] and not prev["in_stock"]:
                    await channel.send(embed=make_restock_embed(item, result))

            state[key] = {"on_sale": result["on_sale"], "in_stock": result["in_stock"]}
        except Exception as ex:
            log.error("[%s] %s", item["name"], ex)
        await asyncio.sleep(2)

    save_state(state)


@monitor_task.before_loop
async def before_monitor():
    await bot.wait_until_ready()


# ── Bot events ────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash command(s)", len(synced))
    except Exception as e:
        log.error("Slash command sync failed: %s", e)

    monitor_task.start()
    log.info("Monitor task started — interval: %d min", CHECK_INTERVAL_MIN)

    channel = bot.get_channel(ALERT_CHANNEL_ID)
    if channel:
        e = discord.Embed(
            title="✅  Massimo Dutti Monitor is Live!",
            description=(
                f"Watching your basket every **{CHECK_INTERVAL_MIN} minutes**.\n\n"
                f"Use `/add [url] [name]` to add items\n"
                f"Use `/list` to see your watchlist\n"
                f"Use `/help` for all commands"
            ),
            color=0x5865F2,
        )
        e.set_footer(text=f"Started at {now_sgt()}")
        await channel.send(embed=e)


bot.run(BOT_TOKEN)
