import os
import re
import shutil
import urllib.parse
import urllib.request
from collections import deque

BASE = "https://eruldin.pages.dev"
OUT = "_site"
UA = "Mozilla/5.0 (compatible; MirrorBot/1.0)"
TEXT_EXTS = {
    ".html", ".htm", ".js", ".mjs", ".css", ".json", ".geojson",
    ".topojson", ".svg", ".webmanifest", ".xml", ".txt", ".csv", ".md"
}
ASSET_DIRS = (
    "assets|images?|img|audio|music|sounds?|maps?|data|json|fonts?|icons?|"
    "media|static|files|locales|tiles|markers|sprites|videos?|docs?|pdfs?|"
    "chapters?|books?|comics?|art|gallery"
)
EXT_RE = (
    "js|mjs|css|json|geojson|topojson|png|jpe?g|webp|avif|gif|svg|ico|"
    "woff2?|ttf|eot|otf|mp3|ogg|wav|m4a|flac|aac|mp4|webm|pdf|txt|xml|"
    "webmanifest|csv|md|wasm"
)

def clean_path(raw, cur_path="/"):
    if not raw:
        return None
    raw = raw.strip().split("#")[0]
    if not raw or raw.startswith(("data:", "blob:", "mailto:", "tel:", "javascript:")):
        return None
    if raw.startswith("//"):
        raw = "https:" + raw
    joined = urllib.parse.urljoin(BASE + cur_path, raw)
    u = urllib.parse.urlparse(joined)
    if u.netloc != "eruldin.pages.dev":
        return None
    p = urllib.parse.unquote(u.path)
    if not p.startswith("/"):
        p = "/" + p
    return p

def extract_refs(text, cur_path):
    refs = set()
    for m in re.findall(rf"""["'`(](/+(?:{ASSET_DIRS})/[^"'`\s<>()\\]+)""", text):
        p = clean_path(re.sub(r"^/+", "/", m), cur_path)
        if p:
            refs.add(p)
    for m in re.findall(rf"""["'`(](/[a-zA-Z0-9_.\-/]+\.(?:{EXT_RE}))""", text):
        p = clean_path(m, cur_path)
        if p:
            refs.add(p)
    for m in re.findall(rf"""["'`]((?:{ASSET_DIRS})/[^"'`\s<>()\\]+)""", text):
        for cand in ("/" + m, m):
            p = clean_path(cand, cur_path)
            if p:
                refs.add(p)
    for m in re.findall(r"""["'`(](\.\.?/[^"'`\s<>()\\]+)""", text):
        p = clean_path(m, cur_path)
        if p:
            refs.add(p)
    for m in re.findall(r"""url\(\s*["']?([^)"'\s]+)["']?\s*\)""", text):
        p = clean_path(m, cur_path)
        if p:
            refs.add(p)
    for m in re.findall(r"""(?:src|href|poster|data-src)=["']([^"']+)["']""", text):
        p = clean_path(m, cur_path)
        if p:
            refs.add(p)
    for m in re.findall(rf"""["'`]([a-zA-Z0-9_.\-]+\.(?:{EXT_RE}))["'`]""", text):
        for cand in ("/" + m, m):
            p = clean_path(cand, cur_path)
            if p:
                refs.add(p)
    return refs

def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    seeds = [
        "/index.html", "/404.html", "/favicon.ico", "/favicon.svg",
        "/favicon.png", "/manifest.json", "/site.webmanifest",
        "/robots.txt", "/sitemap.xml"
    ]
    queue = deque(seeds)
    seen = set(seeds)
    saved = 0
    total_bytes = 0

    while queue:
        p = queue.popleft()
        if p == "/":
            p = "/index.html"
        local_rel = p.lstrip("/")
        if not local_rel or local_rel.endswith("/"):
            continue
        url = BASE + urllib.parse.quote(p, safe="/:@!$&'()*+,;=-._~")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                ct = (resp.headers.get("Content-Type") or "").lower()
                data = resp.read()
        except Exception:
            continue

        ext = os.path.splitext(local_rel)[1].lower()
        if ext not in (".html", ".htm", "") and "text/html" in ct:
            continue

        dest = os.path.join(OUT, local_rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        saved += 1
        total_bytes += len(data)
        print(f"Saved {p} ({len(data)} bytes)")

        if ext in TEXT_EXTS or any(t in ct for t in ("text/", "javascript", "json", "xml", "svg")):
            text = data.decode("utf-8", errors="ignore")
            for ref in extract_refs(text, p):
                if ref not in seen:
                    seen.add(ref)
                    queue.append(ref)

    idx = os.path.join(OUT, "index.html")
    f404 = os.path.join(OUT, "404.html")
    if os.path.exists(idx) and not os.path.exists(f404):
        shutil.copyfile(idx, f404)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(f"Done: {saved} files, {total_bytes} bytes")

if __name__ == "__main__":
    main()
