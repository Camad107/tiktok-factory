"""Agent 2 — Generates coherent image prompts"""
import random

STYLE_BASE = (
    "top-down view of a wooden table with a dark linen cloth, "
    "soft warm candlelight from the side, elegant and minimal, "
    "shallow depth of field, muted earth tones, photorealistic, "
    "absolutely no text, no letters, no numbers, no words, no writing of any kind"
)

NO_TEXT = "absolutely no text, no letters, no numbers, no words, no writing, no inscriptions"

SYMBOL_ENGLISH = {
    "🌙": "crescent moon",
    "☀️": "radiant sun",
    "⭐": "five-pointed star",
    "🔮": "crystal ball",
    "🌊": "ocean wave",
    "🔥": "flame",
    "🌸": "cherry blossom",
    "🦋": "butterfly",
    "⚡": "lightning bolt",
    "🌿": "green leaf",
    "💎": "diamond crystal",
    "🗝️": "ornate key",
    "🌀": "spiral vortex",
    "🏔️": "mountain peak",
    "✨": "cluster of stars",
}


def sym_en(symbol: str, name: str) -> str:
    return SYMBOL_ENGLISH.get(symbol, name.lower().replace("the ", ""))


def run(params: dict) -> dict:
    content = params.get("content", {})
    symbols = content.get("symbols", [])

    s = [
        {
            "name": symbols[i]["name"] if i < len(symbols) else f"Symbol {i+1}",
            "symbol": symbols[i]["symbol"] if i < len(symbols) else "✨",
            "en": sym_en(
                symbols[i].get("symbol", "✨"),
                symbols[i].get("name", f"symbol {i+1}")
            ) if i < len(symbols) else f"symbol {i+1}"
        }
        for i in range(3)
    ]

    seed = random.randint(1, 999999)

    # Image 1 — 3 face-down cards fully visible, aged parchment back, mystical symbols
    image1_prompt = (
        f"{STYLE_BASE}, "
        f"exactly three tarot cards lying face down on the dark cloth, perfectly centered in frame, "
        f"all three cards fully visible with no cropping, wide enough shot to show all cards completely, "
        f"the three cards are side by side with a small gap, horizontally centered, "
        f"each card has an aged ivory parchment background, slightly yellowed and worn at the edges, antique feel, "
        f"left card has a single large mystical {s[0]['en']} symbol hand-drawn in dark ink with ornate esoteric details, "
        f"center card has a single large mystical {s[1]['en']} symbol hand-drawn in dark ink with ornate esoteric details, "
        f"right card has a single large mystical {s[2]['en']} symbol hand-drawn in dark ink with ornate esoteric details, "
        f"symbols look like ancient occult illustrations, intricate fine lines, slightly worn, "
        f"thin ornate gold border on each card, warm candlelight, {NO_TEXT}"
    )

    # Images 2-4 — single card face up, pure illustration only, zero text
    def reveal_prompt(sym: dict) -> str:
        return (
            f"{STYLE_BASE}, "
            f"a single tarot card face up on the dark cloth, overhead view, "
            f"the card features a large detailed mystical illustration of a {sym['en']}, "
            f"rich deep jewel colors, dark moody atmospheric background on the card, golden ornate frame border, "
            f"warm candlelight on the table around the card, "
            f"pure illustration no typography no labels no captions no title, "
            f"{NO_TEXT}"
        )

    return {
        "style_base": STYLE_BASE,
        "seed": seed,
        "image1_prompt": image1_prompt,
        "image2_prompt": reveal_prompt(s[0]),
        "image3_prompt": reveal_prompt(s[1]),
        "image4_prompt": reveal_prompt(s[2]),
    }
