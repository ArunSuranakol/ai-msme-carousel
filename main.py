# main.py
"""
Generates a 5-slide carousel (1080x1080 PNGs) from topics.json.
Optional: send images via Gmail SMTP when run with --send-email and env vars set.
Creates output/carousel_YYYY-MM-DD/ and a zip file of the folder for debugging.
"""
import os, sys, json, textwrap, datetime, shutil, argparse, logging
from PIL import Image, ImageDraw, ImageFont
import smtplib
from email.message import EmailMessage

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

OUT_BASE = "output"
SLIDE_SIZE = (1080, 1080)
PALETTE = {
    "bg": "#0F4C5C",
    "muted": "#A7D7C5",
    "cream": "#F7F6F2",
    "accent": "#F5B041",
    "dark": "#092A2F"
}

def find_font(size=40):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\Arial.ttf"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
    return ImageFont.load_default()

def render_slide(title, body, cta, slide_num, out_path):
    W, H = SLIDE_SIZE
    img = Image.new("RGB", (W, H), PALETTE["bg"])
    draw = ImageDraw.Draw(img)
    title_font = find_font(size=56)
    body_font = find_font(size=30)
    cta_font = find_font(size=26)
    small_font = find_font(size=18)

    padding = 60
    header_h = 160
    draw.rectangle([0, 0, W, header_h], fill=PALETTE["muted"])
    title_wrapped = textwrap.fill(title, width=20)
    w, h = draw.multiline_textsize(title_wrapped, font=title_font, spacing=6)
    draw.multiline_text(((W-w)/2, 28), title_wrapped, font=title_font, fill=PALETTE["dark"], align="center", spacing=6)

    body_y = header_h + 30
    body_box = [padding, body_y, W - padding, H - 160]
    draw.rectangle(body_box, fill=PALETTE["cream"])
    body_wrapped = textwrap.fill(body, width=40)
    draw.multiline_text((body_box[0] + 24, body_box[1] + 24), body_wrapped, font=body_font, fill=PALETTE["dark"], spacing=6)

    if cta:
        cta_w, cta_h = draw.textsize(cta, font=cta_font)
        cta_box = [W - padding - cta_w - 30, H - 120 - 10, W - padding, H - 120 + cta_h + 10]
        draw.rectangle(cta_box, fill=PALETTE["accent"])
        draw.text((cta_box[0] + 12, cta_box[1] + 6), cta, font=cta_font, fill=PALETTE["dark"])

    footer = f"AI for MSMEs • Slide {slide_num}"
    fw, fh = draw.textsize(footer, font=small_font)
    draw.text(((W - fw) / 2, H - 40), footer, font=small_font, fill=PALETTE["muted"])

    img.save(out_path)

def generate_carousel(topic):
    today = datetime.date.today().isoformat()
    outdir = os.path.join(OUT_BASE, f"carousel_{today}")
    os.makedirs(outdir, exist_ok=True)
    files = []
    slides = topic.get("slides", [])
    for i, s in enumerate(slides, start=1):
        title = topic.get("title", "AI for MSMEs") if i == 1 else f"Slide {i}"
        body = s
        cta = "Email for template: arunksurana@gmail.com" if i == len(slides) else ""
        out_path = os.path.join(outdir, f"slide_{i}.png")
        render_slide(title, body, cta, i, out_path)
        files.append(out_path)
    # Create zip for convenience
    zip_base = os.path.join(OUT_BASE, f"carousel_{today}")
    zip_path = shutil.make_archive(zip_base, 'zip', outdir)
    return outdir, files, zip_path

def load_topics(path="topics.json"):
    if not os.path.exists(path):
        logging.error("topics.json missing in repo root. Create it and commit.")
        raise FileNotFoundError("topics.json missing.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error("topics.json is not valid JSON: %s", e)
        raise

def compose_captions(topic):
    li = f"{topic.get('title','')}\n\n{topic.get('long_caption','')}\n\n{' '.join(topic.get('hashtags',[]))}"
    insta = f"{topic.get('short_caption', topic.get('title',''))}\n\n{' '.join(topic.get('hashtags',[]))}"
    return li, insta

def send_email(user, app_password, recipient, subject, body_text, attachments):
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body_text)
    for path in attachments:
        with open(path, "rb") as f:
            data = f.read()
        msg.add_attachment(data, maintype="image", subtype="png", filename=os.path.basename(path))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, app_password)
        s.send_message(msg)

def main(send_email_flag=False):
    topics = load_topics()
    idx = (datetime.date.today().toordinal()) % len(topics)
    topic = topics[idx]
    outdir, files, zip_path = generate_carousel(topic)
    li_caption, insta_caption = compose_captions(topic)
    logging.info("Generated output: %s", outdir)
    logging.info("ZIP created: %s", zip_path)
    logging.info("LinkedIn caption:\n%s", li_caption)
    logging.info("Instagram caption:\n%s", insta_caption)
    if send_email_flag:
        user = os.environ.get("GMAIL_USER")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")
        recipient = os.environ.get("RECIPIENT")
        if not (user and app_password and recipient):
            logging.error("Missing one of GMAIL_USER / GMAIL_APP_PASSWORD / RECIPIENT (set as GitHub Secrets). Aborting email send.")
            raise EnvironmentError("Missing email env vars.")
        subject = f"Carousel: {topic.get('title','AI for MSMEs')} ({datetime.date.today().isoformat()})"
        body = insta_caption + "\n\n(Images attached)"
        send_email(user, app_password, recipient, subject, body, files)
        logging.info("Email sent to %s", recipient)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-email", action="store_true", help="Send images by email (requires env vars)")
    args = parser.parse_args()
    try:
        main(send_email_flag=args.send_email)
    except Exception as e:
        logging.error("Failed: %s", e)
        sys.exit(1)
