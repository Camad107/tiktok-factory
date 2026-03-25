"""Agent 1 — Choisit le concept satisfying du jour et génère le prompt image"""
import json
import subprocess
import random
from datetime import date

CATEGORIES = [
    {"id": "kinetic_sand",   "name": "Kinetic Sand",     "style": "colored kinetic sand being cut, pressed and crumbled, close-up macro, vivid colors, satisfying texture"},
    {"id": "fluid_art",      "name": "Fluid Art",        "style": "acrylic paint pouring and swirling in slow motion, marble-like patterns, rich jewel colors, mesmerizing flow"},
    {"id": "soap_cutting",   "name": "Soap Cutting",     "style": "bar of handmade soap being sliced with a blade, crunchy crumbles, pastel colors, close-up macro shot"},
    {"id": "honey_drip",     "name": "Honey Drip",       "style": "thick golden honey dripping slowly onto a surface, macro photography, warm amber light, ultra glossy"},
    {"id": "crystal_growth", "name": "Crystal Growth",   "style": "colorful crystals forming and growing, macro close-up, iridescent reflections, deep black background"},
    {"id": "ink_water",      "name": "Ink in Water",     "style": "colored ink slowly dissolving and swirling in clear water, macro shot, ethereal and dreamy, black background"},
    {"id": "slime",          "name": "Slime ASMR",       "style": "glossy slime being stretched and poked, close-up macro, vibrant neon colors, satisfying texture detail"},
    {"id": "sand_art",       "name": "Sand Art",         "style": "colored sand falling and forming patterns, top-down view, geometric shapes, zen-like composition"},
    {"id": "chocolate",      "name": "Chocolate Pour",   "style": "melted dark chocolate being poured and drizzled, macro close-up, rich brown tones, glossy surface"},
    {"id": "bubble_wrap",    "name": "Bubble Wrap",      "style": "bubble wrap being popped in slow motion, close-up macro, satisfying compression, clear bubbles"},
    {"id": "geode",          "name": "Geode Crystal",    "style": "cracking open a geode revealing sparkling crystals inside, dramatic lighting, macro shot, gemstone colors"},
    {"id": "resin_art",      "name": "Resin Art",        "style": "epoxy resin swirling with alcohol ink, top-down macro, galaxy-like patterns, deep jewel tones, glossy finish"},
]

PROMPT_TEMPLATE = """You are a TikTok satisfying content specialist.

Today's visual concept: {concept_name}
Base style: {concept_style}

Generate a detailed image generation prompt for a single ultra-satisfying, photorealistic, macro close-up shot.
The image will be animated into a short video loop.

Rules:
- Ultra photorealistic, 8K macro photography
- Extremely satisfying and visually hypnotic
- Rich colors, perfect lighting
- No people, no hands, no faces
- No text, no watermarks
- Square or portrait composition

Return ONLY a JSON:
{{
  "image_prompt": "detailed photorealistic prompt (max 120 words)",
  "video_motion_prompt": "describe the subtle motion to animate this image (max 40 words, focus on the satisfying movement)",
  "hashtags": "#satisfying #asmr #oddlysatisfying #fyp #relaxing"
}}"""


def pick_concept_for_day() -> dict:
    today = date.today()
    rng = random.Random(today.toordinal())
    return rng.choice(CATEGORIES)


def run(params: dict = None) -> dict:
    concept = pick_concept_for_day()

    prompt = PROMPT_TEMPLATE.format(
        concept_name=concept["name"],
        concept_style=concept["style"],
    )

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    raw = result.stdout.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())
    data = parsed[0] if isinstance(parsed, list) else parsed

    return {
        "concept_id": concept["id"],
        "concept_name": concept["name"],
        "image_prompt": data.get("image_prompt", concept["style"]),
        "video_motion_prompt": data.get("video_motion_prompt", "slow smooth satisfying motion"),
        "hashtags": data.get("hashtags", "#satisfying #asmr #oddlysatisfying #fyp"),
    }
