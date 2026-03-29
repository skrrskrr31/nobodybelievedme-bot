"""
NobodyBelievedMe — YouTube Shorts Generator
moviepy 2.x | edge-tts | anthropic
Random engaging Reddit-style stories
"""

import anthropic
import asyncio
import base64
import edge_tts
import json
import os
import random
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip, AudioFileClip, ImageClip,
    CompositeVideoClip, ColorClip, concatenate_videoclips
)
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ──────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BACKGROUND_VIDEOS = [
    r"C:\Users\pc\OneDrive\Desktop\reddit video1.mp4",
    r"C:\Users\pc\OneDrive\Desktop\reddit video2.mp4",
    r"C:\Users\pc\OneDrive\Desktop\reddit video3.mp4",
    r"C:\Users\pc\OneDrive\Desktop\reddit video 4.mp4",
]
OUTPUT_DIR       = Path(__file__).parent / "output"
USED_FILE        = Path(__file__).parent / "kullanilan_hikayeler.json"
VOICE            = "en-US-JennyNeural"
SPEED            = "+50%"
FONT_PATH        = r"C:\Windows\Fonts\arialbd.ttf"
ICON_PATH        = r"C:\Users\pc\OneDrive\Desktop\reddit.png"
MAX_USED         = 50
_BASE            = Path(__file__).parent
TOKEN_FILE       = _BASE / "token_nobody.json"
CLIENT_SECRET    = _BASE / "client_secret.json"
# ──────────────────────────────────────────

STORY_CATEGORIES = [
    {
        "subreddit": "r/tifu",
        "theme": "Today I F***ed Up",
        "prompt": """Write a first-person "TIFU" story for a YouTube Short.

Return EXACTLY this format:
TITLE: [shocking Reddit-style title, max 12 words, no quotes]
HOOK: [the single most cringe/shocking moment from the story, 6-8 words, present tense]
STORY: [the full story]

Story requirements:
- Exactly 90-110 words
- A hilariously embarrassing situation caused by the narrator's own mistake
- Must have a clear moment of realization ("that's when I knew")
- Funny but relatable
- Raw, conversational Reddit tone — like posting at 2am

Example themes:
- Accidentally texting the wrong person something private
- A misunderstanding that spiraled into chaos at work
- Embarrassing yourself in front of someone important
- A small lie that snowballed into disaster"""
    },
    {
        "subreddit": "r/relationship_advice",
        "theme": "Relationship Story",
        "prompt": """Write a first-person relationship betrayal story for a YouTube Short.

Return EXACTLY this format:
TITLE: [shocking Reddit-style title, max 12 words, no quotes]
HOOK: [the single most shocking reveal from the story, 6-8 words, present tense]
STORY: [the full story]

Story requirements:
- Exactly 90-110 words
- A shocking relationship discovery or betrayal
- Hook in the first sentence
- A twist or reveal mid-story
- Raw, conversational tone — like venting at 2am

Example themes:
- Discovered my partner had a whole secret life
- My best friend was sabotaging my relationship
- Found out my family hid something huge for years"""
    },
    {
        "subreddit": "r/AskReddit",
        "theme": "Unbelievable True Story",
        "prompt": """Write a first-person "nobody believed me but it happened" story for a YouTube Short.

Return EXACTLY this format:
TITLE: [shocking Reddit-style title, max 12 words, no quotes]
HOOK: [the most unbelievable moment from the story, 6-8 words, present tense]
STORY: [the full story]

Story requirements:
- Exactly 90-110 words
- Something so strange people didn't believe the narrator
- Specific details that make it feel 100% real
- A moment where the narrator was vindicated
- Raw, conversational tone

Example themes:
- Predicted something impossible before it happened
- Witnessed something bizarre that was later confirmed true
- A crazy coincidence that changed everything"""
    },
    {
        "subreddit": "r/pettyrevenge",
        "theme": "Revenge Story",
        "prompt": """Write a first-person petty revenge story for a YouTube Short.

Return EXACTLY this format:
TITLE: [shocking Reddit-style title, max 12 words, no quotes]
HOOK: [the most satisfying revenge moment, 6-8 words, present tense]
STORY: [the full story]

Story requirements:
- Exactly 90-110 words
- Someone wronged the narrator, they got satisfying revenge
- Clever and proportional revenge
- End with the satisfying moment + reaction
- Tone: smug satisfaction

Example themes:
- A coworker stole credit for my work
- Neighbor kept parking in my spot
- A terrible boss got what they deserved"""
    },
    {
        "subreddit": "r/confessions",
        "theme": "Confession",
        "prompt": """Write a first-person confession story for a YouTube Short.

Return EXACTLY this format:
TITLE: [shocking Reddit-style title, max 12 words, no quotes]
HOOK: [the most shocking confession moment, 6-8 words, present tense]
STORY: [the full story]

Story requirements:
- Exactly 90-110 words
- A secret kept for years, finally shared
- Build to a reveal that recontextualizes everything
- Emotional and raw
- End with how they feel now

Example themes:
- I accidentally caused a big event and never admitted it
- I found out something about my family I wasn't supposed to know
- I did something years ago that still haunts me"""
    },
]


# ── GitHub Actions ortamı için secret dosyalarını yaz ──

def setup_credentials():
    """Env var'dan base64 decode edip dosyaya yaz (CI ortamı)"""
    token_b64  = os.environ.get("TOKEN_JSON")
    secret_b64 = os.environ.get("SECRET_JSON")
    if token_b64:
        TOKEN_FILE.write_bytes(base64.b64decode(token_b64))
        print("[CREDS] token_nobody.json written from env")
    if secret_b64:
        CLIENT_SECRET.write_bytes(base64.b64decode(secret_b64))
        print("[CREDS] client_secret.json written from env")


# ── Tekrar önleme ──────────────────────────────────────

def load_used_titles() -> list:
    if USED_FILE.exists():
        with open(USED_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_used_title(title: str):
    titles = load_used_titles()
    titles.append(title.lower().strip())
    if len(titles) > MAX_USED:
        titles = titles[-MAX_USED:]
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(titles, f, ensure_ascii=False, indent=2)


# ── Hikaye üretimi ─────────────────────────────────────

def generate_story(client: anthropic.Anthropic) -> tuple:
    """Rastgele kategori, tekrar yok — (story, hook, title, subreddit) döner"""
    used_titles = load_used_titles()
    category    = random.choice(STORY_CATEGORIES)

    for attempt in range(3):
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": category["prompt"]}]
        )
        raw = msg.content[0].text.strip()

        title, hook, story = "", "", ""
        for line in raw.splitlines():
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("HOOK:"):
                hook = line.replace("HOOK:", "").strip()
            elif line.startswith("STORY:"):
                story = line.replace("STORY:", "").strip()
            elif story:
                story += " " + line.strip()

        title = title.strip()
        hook  = hook.strip()
        story = story.strip()

        if title.lower() not in used_titles:
            break
        print(f"[SKIP] Duplicate title (attempt {attempt+1}): {title}")

    print(f"\n[CATEGORY] {category['subreddit']} — {category['theme']}")
    print(f"[TITLE] {title}")
    print(f"[HOOK]  {hook}")
    print(f"[STORY]\n{story}\n")
    return story, hook, title, category["subreddit"]


# ── TTS + Whisper ──────────────────────────────────────

async def text_to_speech(text: str, audio_path: str, timing_path: str):
    communicate = edge_tts.Communicate(text, VOICE, rate=SPEED)

    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])

    print("[TTS] Done — running Whisper for word timing...")

    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True, language="en")

    word_timings = []
    for seg in segments:
        for w in seg.words:
            word_timings.append({
                "word":  w.word.strip(),
                "start": w.start,
                "dur":   w.end - w.start
            })

    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(word_timings, f, ensure_ascii=False, indent=2)

    print(f"[WHISPER] {len(word_timings)} words timed")


# ── Görsel yardımcılar ─────────────────────────────────

def make_hook_overlay(hook: str, video_w: int, video_h: int) -> np.ndarray:
    """Videonun başında 2 sn gösterilecek büyük hook metni"""
    try:
        font = ImageFont.truetype(FONT_PATH, 72)
    except Exception:
        font = ImageFont.load_default()

    max_w  = video_w - 100
    words  = hook.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        dummy = Image.new("RGBA", (1, 1))
        bb = ImageDraw.Draw(dummy).textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    dummy    = Image.new("RGBA", (1, 1))
    draw_d   = ImageDraw.Draw(dummy)
    line_h   = draw_d.textbbox((0, 0), "Ag", font=font)[3] + 14
    total_h  = len(lines) * line_h
    pad      = 36
    block_h  = total_h + pad * 2

    img  = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Yarı saydam arka plan bloğu
    box_y0 = video_h // 2 - block_h // 2
    box_y1 = box_y0 + block_h
    draw.rectangle([0, box_y0, video_w, box_y1], fill=(0, 0, 0, 160))

    # Her satır: siyah outline + beyaz yazı
    y = box_y0 + pad
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x  = (video_w - (bb[2] - bb[0])) // 2
        for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,-2),(-2,2),(2,2)]:
            draw.text((x+dx, y+dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    return np.array(img)


def make_word_image(text: str, video_w: int) -> np.ndarray:
    """Sarı altyazı kelimesi"""
    font_size = 85
    max_w     = video_w - 80
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        font = ImageFont.load_default()

    dummy = Image.new("RGBA", (1, 1))
    bbox  = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    tw    = bbox[2] - bbox[0]
    if tw > max_w:
        font_size = int(font_size * max_w / tw) - 4
        font = ImageFont.truetype(FONT_PATH, max(40, font_size))
        bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
        tw   = bbox[2] - bbox[0]

    th  = bbox[3] - bbox[1]
    pad = 16
    img  = Image.new("RGBA", (video_w, th + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x    = (video_w - tw) // 2
    y    = pad

    for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,-2),(-2,2),(2,2)]:
        draw.text((x+dx, y+dy), text, font=font, fill=(0, 0, 0, 255))
    draw.text((x, y), text, font=font, fill=(255, 220, 0, 255))

    return np.array(img)


def split_sentence_into_chunks(words: list) -> list:
    n = len(words)
    if n == 0:
        return []
    num_chunks = max(1, -(-n // 3))
    base  = n // num_chunks
    extra = n % num_chunks
    chunks, idx = [], 0
    for i in range(num_chunks):
        size = base + (1 if i < extra else 0)
        chunks.append(words[idx:idx+size])
        idx += size
    return chunks


def make_subtitle_clips(word_timings: list, video_w: int, video_h: int, audio_dur: float) -> list:
    import re
    sub_y = int(video_h * 0.58)

    merged = []
    for wt in word_timings:
        word = wt["word"].strip()
        if not word:
            continue
        if word.startswith(",") and merged:
            merged[-1] = {
                "word":  merged[-1]["word"] + word,
                "start": merged[-1]["start"],
                "dur":   merged[-1]["dur"] + wt["dur"]
            }
        else:
            merged.append(wt)
    word_timings = merged

    groups, current = [], []
    for wt in word_timings:
        word = wt["word"].strip()
        if not word:
            continue
        current.append(wt)
        if re.search(r'[,\.\!\?]$', word):
            if current:
                groups.append(current)
                current = []
    if current:
        groups.append(current)

    all_chunks = []
    for group in groups:
        words  = [w["word"] for w in group]
        chunks = split_sentence_into_chunks(words)
        idx    = 0
        for chunk in chunks:
            chunk_words = group[idx:idx+len(chunk)]
            all_chunks.append({
                "text":  " ".join(w["word"].strip() for w in chunk_words),
                "start": chunk_words[0]["start"],
                "end":   chunk_words[-1]["start"] + chunk_words[-1]["dur"]
            })
            idx += len(chunk)

    clips = []
    for j, ch in enumerate(all_chunks):
        end = all_chunks[j+1]["start"] if j + 1 < len(all_chunks) else audio_dur
        dur = max(end - ch["start"], 0.1)
        img_arr = make_word_image(ch["text"], video_w)
        img_h   = img_arr.shape[0]
        safe_y  = min(sub_y, video_h - img_h - 20)
        clips.append(
            ImageClip(img_arr, duration=dur)
            .with_start(ch["start"])
            .with_position(("center", safe_y))
        )

    return clips


def fit_video_to_frame(bg: VideoFileClip, W: int, H: int) -> VideoFileClip:
    bw, bh = bg.size
    scale  = H / bh
    nw     = int(bw * scale)
    if nw >= W:
        bg = bg.resized(height=H)
        cw = bg.size[0]
        bg = bg.cropped(x1=(cw-W)//2, y1=0, x2=(cw-W)//2+W, y2=H)
    else:
        bg = bg.resized(width=W)
        ch = bg.size[1]
        bg = bg.cropped(x1=0, y1=(ch-H)//2, x2=W, y2=(ch-H)//2+H)
    return bg.with_position((0, 0))


def make_reddit_card(title: str, subreddit: str, video_w: int) -> np.ndarray:
    try:
        font_title = ImageFont.truetype(FONT_PATH, 46)
        font_user  = ImageFont.truetype(FONT_PATH, 34)
        font_small = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 28)
    except Exception:
        font_title = font_user = font_small = ImageFont.load_default()

    card_w    = video_w - 60
    padding   = 28
    icon_size = 52

    dummy = Image.new("RGBA", (1, 1))
    draw  = ImageDraw.Draw(dummy)

    max_text_w = card_w - padding * 2
    words, lines, cur_line = title.split(), [], ""
    for w in words:
        test = (cur_line + " " + w).strip()
        bb   = draw.textbbox((0, 0), test, font=font_title)
        if bb[2] - bb[0] > max_text_w and cur_line:
            lines.append(cur_line)
            cur_line = w
        else:
            cur_line = test
    if cur_line:
        lines.append(cur_line)

    line_h  = draw.textbbox((0,0),"Ag",font=font_title)[3] + 10
    title_h = len(lines) * line_h
    stats_h = 38
    card_h  = padding + icon_size + 14 + title_h + 16 + stats_h + padding

    img  = Image.new("RGBA", (video_w, card_h + 20), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x0, y0 = (video_w - card_w) // 2, 10
    x1, y1 = x0 + card_w, y0 + card_h
    draw.rounded_rectangle([x0, y0, x1, y1], radius=20, fill=(18, 18, 18, 235))

    try:
        icon = Image.open(ICON_PATH).convert("RGBA").resize((icon_size, icon_size))
        img.paste(icon, (x0 + padding, y0 + padding), icon)
    except Exception:
        draw.ellipse([x0+padding, y0+padding,
                      x0+padding+icon_size, y0+padding+icon_size],
                     fill=(255, 69, 0, 255))

    ux = x0 + padding + icon_size + 14
    uy = y0 + padding + (icon_size - 34) // 2
    draw.text((ux, uy), subreddit, font=font_user, fill=(255, 255, 255, 255))

    ub = draw.textbbox((0,0), subreddit, font=font_user)
    tx, ty0, tr = ux + ub[2] + 10, uy + 4, 13
    draw.ellipse([tx, ty0, tx+tr*2, ty0+tr*2], fill=(29, 155, 240, 255))
    mx, my = tx + tr, ty0 + tr
    draw.line([(mx-6, my), (mx-2, my+5)],   fill=(255,255,255,255), width=3)
    draw.line([(mx-2, my+5), (mx+6, my-4)], fill=(255,255,255,255), width=3)

    title_y = y0 + padding + icon_size + 14
    for line in lines:
        draw.text((x0 + padding, title_y), line, font=font_title, fill=(255,255,255,255))
        title_y += line_h

    try:
        font_icon = ImageFont.truetype(r"C:\Windows\Fonts\seguisym.ttf", 38)
    except Exception:
        font_icon = font_small

    sy  = title_y + 10
    ax  = x0 + padding
    sh  = draw.textbbox((0,0), "A", font=font_small)[3]
    ih  = draw.textbbox((0,0), "\u2665", font=font_icon)[3]
    iy  = sy + (sh - ih) // 2

    draw.text((ax,      iy),  "\u2665", font=font_icon,  fill=(255, 69, 0, 255))
    draw.text((ax + 42, sy),  "99k",    font=font_small, fill=(255, 69, 0, 255))

    bx = ax + 115
    br = sh // 2 - 1
    draw.ellipse([bx, sy+2, bx+br*2, sy+br*2+2], outline=(180,180,180,255), width=2)
    draw.polygon([(bx+4, sy+br*2), (bx+2, sy+br*2+8), (bx+12, sy+br*2)],
                 fill=(180,180,180,255))
    draw.text((bx + br*2 + 8, sy), "99+", font=font_small, fill=(180,180,180,255))

    return np.array(img)


# ── Video montaj ───────────────────────────────────────

def create_video(story: str, hook: str, title: str, subreddit: str,
                 audio_path: str, bg_path: str, output_path: str):
    W, H       = 1080, 1920
    HOOK_DUR   = 2.0   # hook overlay süresi (saniye)
    CARD_START = 2.0   # Reddit kartı ne zaman çıksın
    CARD_DUR   = 2.0   # Reddit kartı kaç saniye görünsün

    audio = AudioFileClip(audio_path)
    dur   = audio.duration
    print(f"[TIME] {dur:.1f}s")

    # Arka plan
    bg = VideoFileClip(bg_path, audio=False)
    if bg.duration < dur:
        bg = concatenate_videoclips([bg] * (int(dur / bg.duration) + 1))
    bg = bg.subclipped(0, dur)
    bg = fit_video_to_frame(bg, W, H)

    # Karartma
    dark = ColorClip(size=(W, H), color=(0, 0, 0), duration=dur).with_opacity(0.55)

    # Hook overlay — ilk HOOK_DUR saniye, ortada büyük beyaz yazı
    hook_arr = make_hook_overlay(hook, W, H)
    hook_clip = (ImageClip(hook_arr, duration=HOOK_DUR)
                 .with_start(0)
                 .with_position((0, 0)))

    # Reddit kartı — CARD_START saniyesinde çıkar, CARD_DUR saniye görünür
    card_arr = make_reddit_card(title, subreddit, W)
    card_h   = card_arr.shape[0]
    card_y   = H // 2 - card_h // 2
    card     = (ImageClip(card_arr, duration=CARD_DUR)
                .with_start(CARD_START)
                .with_position(("center", card_y)))

    # Altyazılar
    with open(str(Path(audio_path).parent / "timings.json"), encoding="utf-8") as f:
        word_timings = json.load(f)
    subs = make_subtitle_clips(word_timings, W, H, dur)

    final = CompositeVideoClip(
        [bg, dark, hook_clip, card] + subs,
        size=(W, H)
    ).with_audio(audio)

    print("[VIDEO] Rendering...")
    final.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="fast",
        ffmpeg_params=["-crf", "23"],
        logger="bar"
    )
    print(f"[DONE] {output_path}")


# ── YouTube Upload ─────────────────────────────────────

def upload_to_youtube(video_path: str, title: str, subreddit: str) -> str:
    """Video upload eder, video URL döner"""
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": f"#{subreddit.replace('r/', '')} #reddit #stories #shorts",
            "tags": ["reddit", "stories", "shorts", subreddit.replace("r/", "")],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print("[UPLOAD] Uploading to YouTube...")
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id  = response["id"]
    video_url = f"https://youtu.be/{video_id}"
    print(f"[UPLOAD] Done: {video_url}")
    return video_url


# ── Ana akış ───────────────────────────────────────────

async def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    audio_path  = str(OUTPUT_DIR / "narration.mp3")
    output_path = str(OUTPUT_DIR / "nobody_believed_me.mp4")
    bg_path     = random.choice(BACKGROUND_VIDEOS)

    setup_credentials()
    print("[AI] Generating story...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    story, hook, title, subreddit = generate_story(client)

    # Başlığı kullanılanlar listesine kaydet
    save_used_title(title)

    with open(OUTPUT_DIR / "story.txt", "w", encoding="utf-8") as f:
        f.write(f"SUBREDDIT: {subreddit}\nTITLE: {title}\nHOOK: {hook}\n\n{story}")

    print("[TTS] Generating audio...")
    timing_path = str(OUTPUT_DIR / "timings.json")
    await text_to_speech(story, audio_path, timing_path)

    print(f"[VIDEO] Background: {Path(bg_path).name}")
    create_video(story, hook, title, subreddit, audio_path, bg_path, output_path)

    url = upload_to_youtube(output_path, title, subreddit)
    print(f"[DONE] {url}")


if __name__ == "__main__":
    asyncio.run(main())
