# -*- coding: utf-8 -*-
"""
기존 글 페이지 일괄 재조립 (템플릿 수정 반영용)
================================================
snap.html / scenery.html / abstract.html 을 고친 뒤, 이미 만들어 둔 글 페이지
(snap/snap_*.html, scenery/scenery_*.html, abstract/abstract_*.html)에 그 수정을 반영한다.

generate_post.html(.py)이 글 페이지를 만드는 방식 그대로 조립한다.
  1. 카테고리 템플릿을 읽어, 글 페이지 위치(category/ 폴더 안)에 맞게 상대경로(href/src/폰트 url)를 보정
  2. 그 틀에 각 글 페이지 "고유의 것"만 원래 글에서 가져와 끼운다
       - 본문 블록 <main class="entry ...">...</main>   (글, 사진, 키워드, 사진 info)
       - 라이트박스 사진 <img id="lightbox-img" ...>
       - 첫 번째 <title>
       - 검색 노출(SEO) 태그: description / og:* / article:* / canonical / JSON-LD
         (이 글이 SEO 태그를 가지고 있을 때만 = article:modified_time 이 있을 때만 가져온다.
          없는 글은 템플릿의 공통 태그를 그대로 쓴다)
  나머지(CSS, 상단/하단 메뉴, 소개 영역, 문의 폼, 스크립트 등)는 모두 새 템플릿 내용이 된다.

사용 (jun-home 폴더 안에서):
  python rebuild_posts.py            미리보기 (파일을 바꾸지 않음)
  python rebuild_posts.py --apply    실제 적용 (바뀌는 파일은 _backup_rebuild_날짜시간 폴더에 먼저 복사)

건드리지 않는 것: 템플릿 파일 자체, thumbs.js, index.html, gallery-a.html, sitemap.xml, 이미지
"""
import os
import re
import sys
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CATEGORY_FILES = {
    "snap": "snap.html",
    "scenery": "scenery.html",
    "abstract": "abstract.html",
}

# ------------------------------------------------------------------
# generate_post.html / generate_post.py 와 같은 규칙
# ------------------------------------------------------------------
PATH_ATTR_RE = re.compile(r'(href|src)="([^"]+)"')
FONT_URL_RE = re.compile(r"url\('([^']+)'\)")
ENTRY_BLOCK_RE = re.compile(r'<main class="entry.*?</main>', re.DOTALL)
LIGHTBOX_IMG_RE = re.compile(r'<img id="lightbox-img" src="[^"]*"[^>]*alt="[^"]*"[^>]*>')
ENTRY_IMG_RE = re.compile(r'<img src="([^"]*)" alt="([^"]*)"')
TITLE_TAG_RE = re.compile(r"<title>.*?</title>", re.DOTALL)

# 카테고리 템플릿 맨 위의 숨김 h1(sr-only cat-h1)은 글 페이지에 넣지 않는다 (글 페이지에는 글 제목 h1이 따로 있다)
CAT_H1_RE = re.compile(r'[ \t]*<h1 class="sr-only cat-h1">.*?</h1>[ \t]*\n?', re.DOTALL)

# generate_post 의 apply_seo_head 가 글 페이지 <head> 에 쓰는 태그들 (쓰는 순서대로)
SEO_HEAD_RES = [
    re.compile(r'<meta name="description"[^>]*>'),
    re.compile(r'<meta property="og:type"[^>]*>'),
    re.compile(r'<meta property="og:title"[^>]*>'),
    re.compile(r'<meta property="og:description"[^>]*>'),
    re.compile(r'<meta property="article:published_time"[^>]*>'),
    re.compile(r'<meta property="article:modified_time"[^>]*>'),
    re.compile(r'<link rel="canonical"[^>]*>'),
    re.compile(r'<meta property="og:url"[^>]*>'),
    re.compile(r'<meta property="og:image"[^>]*>'),
    re.compile(r'<meta property="og:image:alt"[^>]*>'),
    re.compile(r'<script type="application/ld\+json">.*?</script>', re.DOTALL),
]


def fix_one_path(path, category):
    if not path or path.startswith(("http://", "https://", "//", "mailto:", "#")):
        return path
    if path.startswith(category + "/"):
        return path[len(category) + 1:]
    return "../" + path


def rewrite_relative_paths(html, category):
    """카테고리 루트 페이지(snap.html 등)를 category/ 폴더 안으로 옮길 때 상대경로를 보정한다."""
    html = PATH_ATTR_RE.sub(lambda m: '{}="{}"'.format(m.group(1), fix_one_path(m.group(2), category)), html)
    html = FONT_URL_RE.sub(lambda m: "url('{}')".format(fix_one_path(m.group(1), category)), html)
    return html


def set_head_tag(html, regex, tag):
    """이미 있으면 교체하고, 없으면 </head> 앞에 넣는다."""
    if regex.search(html):
        return regex.sub(lambda m: tag, html, count=1)
    return html.replace("</head>", tag + "\n</head>", 1)


# ------------------------------------------------------------------
# 글 한 편 재조립
# ------------------------------------------------------------------
def rebuild_page(old_html, shell):
    """shell(새 템플릿을 보정한 것)에 old_html 고유의 것을 끼워 넣는다.
    돌려주는 값: (새 html, SEO 태그를 가져왔는지) / 만들 수 없으면 (None, 사유)"""
    m_old = ENTRY_BLOCK_RE.search(old_html)
    if not m_old:
        return None, '본문 블록(<main class="entry">)이 없음'
    entry = m_old.group(0)
    m_shell = ENTRY_BLOCK_RE.search(shell)
    new = shell[:m_shell.start()] + entry + shell[m_shell.end():]   # 본문은 문자열 그대로 삽입

    # 라이트박스 사진: 원래 글의 것, 없으면 본문 사진으로
    m_lb = LIGHTBOX_IMG_RE.search(old_html)
    if m_lb:
        lightbox = m_lb.group(0)
    else:
        m_img = ENTRY_IMG_RE.search(entry)
        if not m_img:
            return None, "라이트박스/본문 사진을 찾지 못함"
        lightbox = '<img id="lightbox-img" src="{}" alt="{}">'.format(m_img.group(1), m_img.group(2))
    new = LIGHTBOX_IMG_RE.sub(lambda m: lightbox, new, count=1)

    # 첫 번째 <title>
    m_title = TITLE_TAG_RE.search(old_html)
    if m_title:
        new = TITLE_TAG_RE.sub(lambda m: m_title.group(0), new, count=1)

    # 이 글 고유의 SEO 태그
    old_head = old_html.split("</head>", 1)[0]
    has_seo = 'property="article:modified_time"' in old_head
    if has_seo:
        for regex in SEO_HEAD_RES:
            m = regex.search(old_head)
            if m:
                new = set_head_tag(new, regex, m.group(0))
    return new, has_seo


# ------------------------------------------------------------------
# 파일 입출력 (줄바꿈은 원래 글 파일의 것을 그대로 유지)
# ------------------------------------------------------------------
def read_raw(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def to_lf(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def main():
    apply = "--apply" in sys.argv[1:]
    backup_root = os.path.join(BASE_DIR, "_backup_rebuild_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    total = 0

    print("[적용]" if apply else "[미리보기 - 파일은 바뀌지 않았습니다]")
    for category, tpl_name in CATEGORY_FILES.items():
        tag = "[{}]".format(category)
        tpl_path = os.path.join(BASE_DIR, tpl_name)
        if not os.path.exists(tpl_path):
            print(tag, "{} 을(를) 찾지 못해 건너뜀".format(tpl_name))
            continue
        tpl = to_lf(read_raw(tpl_path))
        if 'src="{}/thumbs.js"'.format(category) not in tpl:
            print(tag, "{} 이(가) 썸네일 데이터(thumbs.js) 방식이 아니라서 건너뜀 (먼저 python migrate_thumbs.py)".format(tpl_name))
            continue
        if not ENTRY_BLOCK_RE.search(tpl):
            print(tag, '{} 에서 <main class="entry"> 블록을 찾지 못해 건너뜀'.format(tpl_name))
            continue
        shell = rewrite_relative_paths(tpl, category)
        shell = CAT_H1_RE.sub("", shell)   # 카테고리 템플릿의 숨김 h1 은 글 페이지에 넣지 않는다

        folder = os.path.join(BASE_DIR, category)
        names = sorted(fn for fn in os.listdir(folder)
                       if fn.startswith(category + "_") and fn.endswith(".html")) if os.path.isdir(folder) else []

        changed, same, skipped = [], 0, []
        for fn in names:
            rel = "{}/{}".format(category, fn)
            path = os.path.join(folder, fn)
            old_raw = read_raw(path)
            eol = "\r\n" if "\r\n" in old_raw else "\n"
            new_html, info = rebuild_page(to_lf(old_raw), shell)
            if new_html is None:
                skipped.append("{} ({})".format(rel, info))
                continue
            new_raw = new_html.replace("\n", eol)
            if new_raw == old_raw:
                same += 1
                continue
            changed.append((rel, path, new_raw, info))

        print(tag, "글 페이지 {}개: 갱신 {}{}개 / 이미 최신 {}개 / 건너뜀 {}개".format(
            len(names), "" if apply else "예정 ", len(changed), same, len(skipped)))
        for rel, path, new_raw, has_seo in changed:
            print("   ", rel, "(SEO 태그 유지)" if has_seo else "")
            if apply:
                dst = os.path.join(backup_root, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(path, dst)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(new_raw)
        for s in skipped:
            print("    건너뜀:", s)
        total += len(changed)

    print("바뀐 파일: {}개".format(total) if apply else "바뀔 파일: {}개".format(total))
    if apply and total:
        print("원본 백업:", backup_root)
    elif not apply and total:
        print("문제가 없으면 --apply 를 붙여 다시 실행하세요.")


if __name__ == "__main__":
    main()
