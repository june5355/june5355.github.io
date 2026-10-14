# -*- coding: utf-8 -*-
"""
사이트 점검 결과 일괄 수정 (fix_site_seo.py)
==============================================
메인 페이지(index / gallery-a / snap / scenery / abstract)와 글 페이지 생성 도구를 고친다.

고치는 것
  1. scenery.html : viewport 메타 추가, 중복 <title> 제거
  2. 5개 페이지 : 페이지별로 다른 <title> / description / og:title / og:description,
                   효과 없는 keywords 메타 삭제, 파비콘(favicon.ico / apple-touch-icon.png) 링크 추가,
                   화면에는 안 보이는 <h1>(sr-only) 추가
  3. index.html : canonical, og:url, og:site_name, og:locale, WebSite/Person JSON-LD 추가
  4. gallery-a.html : viewport 의 확대 금지(maximum-scale / user-scalable=no) 제거,
                   IMAGES 목록에 빠진 사진 추가 (글 페이지와 썸네일이 모두 있는 사진만)
  5. rebuild_posts.py / generate_post.html : 카테고리 템플릿 맨 위의 숨김 h1(cat-h1)을
                   글 페이지에는 넣지 않도록 한 줄씩 보강 (글 페이지에는 글 제목 h1이 따로 있기 때문)

사용 (jun-home 폴더 안에서):
  python fix_site_seo.py            미리보기 (파일을 바꾸지 않음)
  python fix_site_seo.py --apply    실제 적용 (바뀌는 파일은 _backup_sitefix_날짜시간 폴더에 먼저 복사)

적용한 뒤 이어서 (글 페이지 전체에 템플릿 수정을 반영):
  python rebuild_posts.py           미리보기
  python rebuild_posts.py --apply   실제 적용

여러 번 실행해도 결과가 같다 (이미 고친 곳은 "이미 최신"으로 건너뜀).
건드리지 않는 것: sitemap.xml, rss.xml, robots.txt, thumbs.js, 404.html, 이미지, 글 페이지 자체
"""
import os
import re
import sys
import json
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE = "https://june5355.github.io"
SITE_NAME = "JUNEssay"

PAGES = [
    {
        "file": "index.html", "kind": "home",
        "title": "사진가 장정대 | JUNEssay 사진 아카이브",
        "desc": "1990년부터 한국의 거리와 풍경, 일상을 기록해 온 사진가 장정대의 사진 아카이브. 스냅·풍경·추상 사진과 사진 에세이를 만나보세요.",
        "h1": "사진가 장정대 — JUNEssay 사진 아카이브",
    },
    {
        "file": "gallery-a.html", "kind": "gallery",
        "title": "GALLERY A_ 전체 사진 | 사진가 장정대 JUNEssay",
        "desc": "사진가 장정대의 스냅·풍경·추상 사진을 한눈에 둘러보는 인터랙티브 갤러리. 드래그로 탐색하고, 사진을 누르면 크게 볼 수 있습니다.",
        "h1": "GALLERY A_ — 사진가 장정대 전체 사진 모음",
    },
    {
        "file": "snap.html", "kind": "template", "category": "snap",
        "title": "스냅 사진 모음 | 사진가 장정대 JUNEssay",
        "desc": "거리와 골목, 일상의 순간을 담은 사진가 장정대의 스냅 사진 모음. 사진마다 짧은 글을 함께 남깁니다.",
        "h1": "스냅 사진 모음 — 사진가 장정대 JUNEssay",
    },
    {
        "file": "scenery.html", "kind": "template", "category": "scenery",
        "title": "풍경 사진 모음 | 사진가 장정대 JUNEssay",
        "desc": "산과 하늘, 노을과 길 위에서 만난 한국의 풍경을 담은 사진가 장정대의 풍경 사진 모음.",
        "h1": "풍경 사진 모음 — 사진가 장정대 JUNEssay",
    },
    {
        "file": "abstract.html", "kind": "template", "category": "abstract",
        "title": "추상 사진 모음 | 사진가 장정대 JUNEssay",
        "desc": "빛과 색, 형태를 따라가며 담은 사진가 장정대의 추상 사진 모음.",
        "h1": "추상 사진 모음 — 사진가 장정대 JUNEssay",
    },
]

SR_ONLY_CSS = ("  .sr-only{ position:absolute !important; width:1px; height:1px; padding:0; margin:-1px; "
               "overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }\n")

VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
ICON_TAGS = [
    ("rel=\"icon\"", '<link rel="icon" href="favicon.ico" sizes="any">'),
    ("rel=\"apple-touch-icon\"", '<link rel="apple-touch-icon" href="apple-touch-icon.png">'),
]

TITLE_RE = re.compile(r"(?P<ind>[ \t]*)<title>.*?</title>(?P<tail>[ \t]*\n?)", re.DOTALL)
DESC_RE = re.compile(r'<meta name="description"[^>]*>')
OGT_RE = re.compile(r'<meta property="og:title"[^>]*>')
OGD_RE = re.compile(r'<meta property="og:description"[^>]*>')
OGURL_RE = re.compile(r'<meta property="og:url"[^>]*>')
OGSITE_RE = re.compile(r'<meta property="og:site_name"[^>]*>')
OGLOC_RE = re.compile(r'<meta property="og:locale"[^>]*>')
CANON_RE = re.compile(r'<link rel="canonical"[^>]*>')
KEYWORDS_RE = re.compile(r'[ \t]*<meta name="keywords"[^>]*>[ \t]*\n?')
VIEWPORT_RE = re.compile(r'<meta name="viewport"[^>]*>')
CHARSET_RE = re.compile(r'<meta charset="[^"]*">', re.I)
H1_SR_RE = re.compile(r'<h1 class="sr-only[^"]*">.*?</h1>', re.DOTALL)
IMAGES_RE = re.compile(r"(const IMAGES = \[)(.*?)(\n\s*\];)", re.DOTALL)


# ------------------------------------------------------------------
# 파일 입출력 (줄바꿈은 원래 파일의 것을 그대로 유지)
# ------------------------------------------------------------------
def read_raw(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def to_lf(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def esc(s):
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------
# <head> 도우미 (head = </head> 앞까지의 문자열)
# ------------------------------------------------------------------
def append_to_head(head, tag):
    if not head.endswith("\n"):
        head += "\n"
    return head + "  " + tag + "\n"


def set_tag(head, regex, tag):
    """이미 있으면 교체하고, 없으면 head 끝에 추가한다."""
    if regex.search(head):
        return regex.sub(lambda m: tag, head, count=1)
    return append_to_head(head, tag)


def set_title(head, title):
    new = "<title>%s</title>" % esc(title)
    done = [False]

    def rep(m):
        if done[0]:
            return ""                       # 두 번째 이후의 <title> 은 지운다
        done[0] = True
        return m.group("ind") + new + m.group("tail")

    out = TITLE_RE.sub(rep, head)
    if not done[0]:
        out = append_to_head(out, new)
    return out


def set_viewport(head):
    if VIEWPORT_RE.search(head):
        return VIEWPORT_RE.sub(lambda m: VIEWPORT, head, count=1)
    m = CHARSET_RE.search(head)
    if m:
        return head[:m.end()] + "\n" + VIEWPORT + head[m.end():]
    return append_to_head(head, VIEWPORT)


def set_icons(head):
    for marker, tag in ICON_TAGS:
        if marker not in head:
            head = append_to_head(head, tag)
    return head


def set_sr_only_css(head):
    if ".sr-only{" in head:
        return head
    i = head.rfind("</style>")
    if i < 0:
        raise ValueError("<style> 블록을 찾지 못함")
    return head[:i] + SR_ONLY_CSS + head[i:]


def home_jsonld():
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": SITE + "/#website",
                "url": SITE + "/",
                "name": SITE_NAME,
                "alternateName": "사진가 장정대 JUNEssay",
                "inLanguage": "ko",
            },
            {
                "@type": "Person",
                "@id": SITE + "/#person",
                "name": "장정대",
                "alternateName": ["JEONGDAE JANG", "JUN"],
                "jobTitle": "사진가",
                "url": SITE + "/",
                "sameAs": ["https://blog.naver.com/jd_photographer"],
            },
        ],
    }
    return '<script type="application/ld+json">\n' + json.dumps(data, ensure_ascii=False, indent=2) + "\n</script>"


# ------------------------------------------------------------------
# <body> 도우미
# ------------------------------------------------------------------
def set_h1(rest, anchor, h1_tag):
    if H1_SR_RE.search(rest):
        return H1_SR_RE.sub(lambda m: h1_tag, rest, count=1)
    if anchor not in rest:
        raise ValueError("h1 을 넣을 위치(%s)를 찾지 못함" % anchor)
    return rest.replace(anchor, anchor + "\n  " + h1_tag, 1)


def sync_gallery_images(rest, notes, warns):
    """gallery-a.html 의 IMAGES 목록에 빠진 사진을 추가한다 (글 페이지와 썸네일이 모두 있는 것만)."""
    m = IMAGES_RE.search(rest)
    if not m:
        warns.append("IMAGES 목록을 찾지 못해 사진 추가는 건너뜀")
        return rest
    have = set(re.findall(r"'([^']+)'", m.group(2)))
    add = []
    for cat in ("snap", "scenery", "abstract"):
        img_dir = os.path.join(BASE_DIR, cat, "image")
        if not os.path.isdir(img_dir):
            continue
        for fn in sorted(os.listdir(img_dir)):
            if fn.lower() == "profile.png" or not re.search(r"\.(jpe?g|png|webp)$", fn, re.I):
                continue
            rel = "%s/image/%s" % (cat, fn)
            if rel in have:
                continue
            stem = os.path.splitext(fn)[0]
            if not os.path.exists(os.path.join(BASE_DIR, cat, stem + ".html")):
                warns.append("글 페이지가 없어 갤러리에 넣지 않음: " + rel)
                continue
            if not os.path.exists(os.path.join(BASE_DIR, cat, "thumb", stem + ".jpg")):
                warns.append("썸네일이 없어 갤러리에 넣지 않음: " + rel)
                continue
            add.append(rel)
    if not add:
        return rest
    notes.append("갤러리 사진 %d장 추가" % len(add))
    new_inner = m.group(2).rstrip() + "".join("\n      '%s'," % r for r in add)
    return rest[:m.start()] + m.group(1) + new_inner + m.group(3) + rest[m.end():]


# ------------------------------------------------------------------
# 페이지 한 개 처리
# ------------------------------------------------------------------
def process_page(spec):
    path = os.path.join(BASE_DIR, spec["file"])
    raw = read_raw(path)
    eol = "\r\n" if "\r\n" in raw else "\n"
    html = to_lf(raw)
    head, sep, rest = html.partition("</head>")
    if not sep:
        raise ValueError("</head> 를 찾지 못함")

    notes, warns = [], []

    def step(label, before, after):
        if before != after:
            notes.append(label)
        return after

    head = step("title 교체", head, set_title(head, spec["title"]))
    head = step("description 교체", head, set_tag(head, DESC_RE, '<meta name="description" content="%s">' % esc(spec["desc"])))
    head = step("og:title 교체", head, set_tag(head, OGT_RE, '<meta property="og:title" content="%s">' % esc(spec["title"])))
    head = step("og:description 교체", head, set_tag(head, OGD_RE, '<meta property="og:description" content="%s">' % esc(spec["desc"])))
    head = step("keywords 삭제", head, KEYWORDS_RE.sub("", head))
    head = step("viewport 정리", head, set_viewport(head))
    head = step("파비콘 링크 추가", head, set_icons(head))
    head = step("sr-only CSS 추가", head, set_sr_only_css(head))

    if spec["kind"] == "home":
        url = SITE + "/"
        head = step("canonical 추가", head, set_tag(head, CANON_RE, '<link rel="canonical" href="%s">' % url))
        head = step("og:url 추가", head, set_tag(head, OGURL_RE, '<meta property="og:url" content="%s">' % url))
        head = step("og:site_name 추가", head, set_tag(head, OGSITE_RE, '<meta property="og:site_name" content="%s">' % SITE_NAME))
        head = step("og:locale 추가", head, set_tag(head, OGLOC_RE, '<meta property="og:locale" content="ko_KR">'))
        if "application/ld+json" not in head:
            head = step("JSON-LD(WebSite/Person) 추가", head, append_to_head(head, home_jsonld()))
    if spec["kind"] == "gallery":
        head = step("og:site_name 추가", head, set_tag(head, OGSITE_RE, '<meta property="og:site_name" content="%s">' % SITE_NAME))
        head = step("og:locale 추가", head, set_tag(head, OGLOC_RE, '<meta property="og:locale" content="ko_KR">'))

    # ---- body ----
    if spec["kind"] == "gallery":
        rest = step("h1 추가", rest, set_h1(rest, "<body>", '<h1 class="sr-only">%s</h1>' % esc(spec["h1"])))
        rest = sync_gallery_images(rest, notes, warns)
    else:
        cls = "sr-only cat-h1" if spec["kind"] == "template" else "sr-only"
        rest = step("h1 추가", rest, set_h1(rest, '<div class="page">', '<h1 class="%s">%s</h1>' % (cls, esc(spec["h1"]))))

    # ---- 검증: 하나라도 어긋나면 이 파일은 건드리지 않는다 ----
    if head.count("<title>") != 1:
        raise ValueError("<title> 이 1개가 아님")
    if 'name="keywords"' in head:
        raise ValueError("keywords 가 남아 있음")
    if len(VIEWPORT_RE.findall(head)) != 1:
        raise ValueError("viewport 가 1개가 아님")
    if spec["kind"] == "template":
        if '<main class="entry' not in rest or ('src="%s/thumbs.js"' % spec["category"]) not in rest:
            raise ValueError("템플릿 구조(main.entry / thumbs.js)가 바뀜")
    if len(H1_SR_RE.findall(rest)) != 1:
        raise ValueError("숨김 h1 이 1개가 아님")

    new_raw = (head + sep + rest).replace("\n", eol)
    return raw, new_raw, notes, warns


# ------------------------------------------------------------------
# rebuild_posts.py / generate_post.html 보강 (카테고리 템플릿의 숨김 h1 을 글 페이지에서 빼기)
# ------------------------------------------------------------------
PY_CONST = r'''
# 카테고리 템플릿 맨 위의 숨김 h1(sr-only cat-h1)은 글 페이지에 넣지 않는다 (글 페이지에는 글 제목 h1이 따로 있다)
CAT_H1_RE = re.compile(r'[ \t]*<h1 class="sr-only cat-h1">.*?</h1>[ \t]*\n?', re.DOTALL)
'''

TOOL_PATCHES = [
    {
        "file": "rebuild_posts.py",
        "marker": "CAT_H1_RE",
        "edits": [
            ('TITLE_TAG_RE = re.compile(r"<title>.*?</title>", re.DOTALL)\n',
             'TITLE_TAG_RE = re.compile(r"<title>.*?</title>", re.DOTALL)\n' + PY_CONST),
            ("        shell = rewrite_relative_paths(tpl, category)\n",
             "        shell = rewrite_relative_paths(tpl, category)\n"
             '        shell = CAT_H1_RE.sub("", shell)   # 카테고리 템플릿의 숨김 h1 은 글 페이지에 넣지 않는다\n'),
        ],
    },
    {
        "file": "generate_post.html",
        "marker": "CAT_H1_RE",
        "edits": [
            ("const TITLE_TAG_RE = /<title>.*?<\\/title>/s;\n",
             "const TITLE_TAG_RE = /<title>.*?<\\/title>/s;\n"
             "// 카테고리 템플릿 맨 위의 숨김 h1(sr-only cat-h1)은 글 페이지에 넣지 않는다 (글 페이지에는 글 제목 h1이 따로 있다)\n"
             "const CAT_H1_RE = /[ \\t]*<h1 class=\"sr-only cat-h1\">.*?<\\/h1>[ \\t]*\\n?/s;\n"),
            ("  let shell = rewriteRelativePaths(catHtml, category);\n",
             "  let shell = rewriteRelativePaths(catHtml, category);\n"
             "  shell = shell.replace(CAT_H1_RE, '');   // 카테고리 템플릿의 숨김 h1 은 글 페이지에 넣지 않는다\n"),
        ],
    },
]


def patch_tool(spec):
    path = os.path.join(BASE_DIR, spec["file"])
    raw = read_raw(path)
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = to_lf(raw)
    if spec["marker"] in text:
        return raw, raw, []
    for old, _new in spec["edits"]:
        n = text.count(old)
        if n != 1:
            raise ValueError("고칠 위치를 찾지 못함(%d곳): %r" % (n, old.strip()[:50]))
    for old, new in spec["edits"]:
        text = text.replace(old, new, 1)
    return raw, text.replace("\n", eol), ["숨김 h1 제외 처리 추가"]


# ------------------------------------------------------------------
def main():
    apply = "--apply" in sys.argv[1:]
    backup_root = os.path.join(BASE_DIR, "_backup_sitefix_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    jobs = []   # (파일명, 원본, 새 내용, 메모, 경고) / 실패는 (파일명, None, None, [], [사유])

    for spec in PAGES:
        try:
            old, new, notes, warns = process_page(spec)
            jobs.append((spec["file"], old, new, notes, warns))
        except Exception as e:
            jobs.append((spec["file"], None, None, [], ["건너뜀: %s" % e]))
    for spec in TOOL_PATCHES:
        try:
            old, new, notes = patch_tool(spec)
            jobs.append((spec["file"], old, new, notes, []))
        except Exception as e:
            jobs.append((spec["file"], None, None, [], ["건너뜀: %s" % e]))

    print("[적용]" if apply else "[미리보기 - 파일은 바뀌지 않았습니다]")
    changed = 0
    for name, old, new, notes, warns in jobs:
        if old is None:
            print("  ", name, "-", warns[0])
            continue
        if old == new:
            print("  ", name, "- 이미 최신")
        else:
            changed += 1
            print("  ", name, "-", ", ".join(notes))
            if apply:
                dst = os.path.join(backup_root, name)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(BASE_DIR, name), dst)
                with open(os.path.join(BASE_DIR, name), "w", encoding="utf-8", newline="") as f:
                    f.write(new)
        for w in warns:
            print("      참고:", w)

    print("바뀐 파일: %d개" % changed if apply else "바뀔 파일: %d개" % changed)
    if apply and changed:
        print("원본 백업:", backup_root)
        print("다음: python rebuild_posts.py (미리보기) → python rebuild_posts.py --apply")
    elif not apply and changed:
        print("문제가 없으면 --apply 를 붙여 다시 실행하세요.")


if __name__ == "__main__":
    main()
