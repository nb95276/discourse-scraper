#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discourse Forum Scraper & Exporter
Robustly fetches complete topics from Discourse-based forums (like linux.do)
with Cloudflare TLS bypass (curl_cffi), cookie session support, and rate-limit handling.
"""

import os
import re
import sys
import time
import json
import argparse
import http.cookiejar
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from curl_cffi import requests

class DiscourseScraper:
    def __init__(self, base_url: str = "https://linux.do", cookie_file: str = None, delay: float = 1.0):
        self.base_url = base_url.rstrip('/')
        self.delay = max(0.5, delay)
        self.session = requests.Session(impersonate="chrome124")
        
        if cookie_file and os.path.exists(cookie_file):
            try:
                cj = http.cookiejar.MozillaCookieJar(cookie_file)
                cj.load(ignore_discard=True, ignore_expires=True)
                self.session.cookies.update(cj)
                print(f"[*] Loaded cookies from {cookie_file}")
            except Exception as e:
                print(f"[!] Warning: Failed to parse cookie file: {e}")

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': f"{self.base_url}/",
            'X-Requested-With': 'XMLHttpRequest',
        }

    def _safe_get(self, url: str, params=None, max_retries: int = 5):
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, headers=self.headers, timeout=25)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    wait_time = 10 * (attempt + 1)
                    print(f"[!] 429 Rate limited. Cooling down for {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                elif resp.status_code == 404:
                    print(f"[!] Topic not found (404): {url}")
                    return None
                elif resp.status_code == 403:
                    print(f"[!] 403 Forbidden on {url}. Ensure cookies (cf_clearance, _t) are valid.")
                    return None
                else:
                    print(f"[!] Unexpected status code {resp.status_code} for {url}")
                    time.sleep(2)
            except Exception as e:
                print(f"[!] Network error on attempt {attempt + 1}: {e}")
                time.sleep(3)
        return None

    def fetch_topic(self, topic_id: int):
        print(f"\n[+] Fetching topic {topic_id} from {self.base_url}...")
        all_posts = []
        seen_post_ids = set()
        topic_meta = {}
        page = 1

        while True:
            url = f"{self.base_url}/t/topic/{topic_id}.json?page={page}"
            data = self._safe_get(url)
            if not data:
                break

            if not topic_meta:
                topic_meta = {
                    "id": data.get("id", topic_id),
                    "title": data.get("title", f"Topic {topic_id}"),
                    "slug": data.get("slug", ""),
                    "created_at": data.get("created_at", ""),
                    "category_id": data.get("category_id"),
                    "tags": data.get("tags", []),
                    "views": data.get("views", 0),
                    "posts_count": data.get("posts_count", 0),
                    "like_count": data.get("like_count", 0),
                    "url": f"{self.base_url}/t/topic/{topic_id}"
                }

            posts = data.get("post_stream", {}).get("posts", [])
            if not posts:
                break

            new_in_page = 0
            for p in posts:
                pid = p.get("id")
                if pid and pid not in seen_post_ids:
                    seen_post_ids.add(pid)
                    
                    cooked = p.get("cooked", "")
                    soup = BeautifulSoup(cooked, "html.parser")
                    text_content = soup.get_text(separator="\n", strip=True)

                    post_obj = {
                        "id": pid,
                        "post_number": p.get("post_number"),
                        "username": p.get("username", "Unknown"),
                        "name": p.get("name", ""),
                        "reply_to": p.get("reply_to_post_number"),
                        "like_count": p.get("like_count", 0),
                        "created_at": p.get("created_at", ""),
                        "raw_html": cooked,
                        "text": text_content
                    }
                    all_posts.append(post_obj)
                    new_in_page += 1

            print(f"  - Page {page}: added {new_in_page} posts (accumulated: {len(all_posts)})")

            if new_in_page == 0:
                break

            page += 1
            time.sleep(self.delay)

        all_posts.sort(key=lambda x: x["post_number"])
        topic_meta["posts"] = all_posts
        return topic_meta

    @staticmethod
    def to_markdown(topic_meta: dict) -> str:
        lines = [
            f"# {topic_meta.get('title', 'Discourse Topic')}\n\n",
            f"- **原帖链接**: {topic_meta.get('url')}\n",
            f"- **发布时间**: {topic_meta.get('created_at')}\n",
            f"- **总楼层数**: {len(topic_meta.get('posts', []))}\n",
        ]
        tags = topic_meta.get("tags")
        if tags:
            lines.append(f"- **标签**: {', '.join(tags)}\n")
        lines.append("\n---\n\n")

        for post in topic_meta.get("posts", []):
            pnum = post.get("post_number")
            uname = post.get("username")
            name = post.get("name")
            display_user = f"{name} (@{uname})" if name else f"@{uname}"
            reply_to = post.get("reply_to")
            reply_str = f" (回复 #{reply_to} 楼)" if reply_to else ""
            likes = post.get("like_count", 0)
            created = post.get("created_at")

            lines.append(f"### 第 {pnum} 楼: {display_user}{reply_str} | 赞数: {likes} | 时间: {created}\n\n")
            lines.append(f"{post.get('text', '')}\n\n---\n\n")

        return "".join(lines)


def parse_topic_target(target: str):
    """Extract base_url and topic_id from target string (URL or number)"""
    target = target.strip()
    if target.isdigit():
        return "https://linux.do", int(target)
    
    parsed = urlparse(target)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Match /t/{slug}/{id} or /t/topic/{id} or /t/{id}
    match = re.search(r'/t/(?:[^/]+/)?(\d+)', parsed.path)
    if match:
        return base_url, int(match.group(1))
    
    raise ValueError(f"Could not extract topic ID from: {target}")


def main():
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Discourse Forum Topic Scraper")
    parser.add_argument("topics", nargs="+", help="Topic URLs or IDs to scrape")
    parser.add_argument("--cookie", "-c", default=None, help="Path to Netscape cookies.txt file")
    parser.add_argument("--output", "-o", default="output", help="Directory to save output files")
    parser.add_argument("--format", "-f", choices=["md", "json", "both"], default="both", help="Export format")
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Delay between page requests in seconds")
    
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)

    for target in args.topics:
        try:
            base_url, tid = parse_topic_target(target)
            scraper = DiscourseScraper(base_url=base_url, cookie_file=args.cookie, delay=args.delay)
            topic_data = scraper.fetch_topic(tid)

            if not topic_data or not topic_data.get("posts"):
                print(f"[!] No content retrieved for topic {tid}")
                continue

            raw_title = topic_data.get('title', '')
            clean_title = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', raw_title)[:30]
            base_name = f"topic_{tid}_{clean_title}"
            
            if args.format in ["json", "both"]:
                json_path = os.path.join(args.output, f"{base_name}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(topic_data, f, ensure_ascii=False, indent=2)
                print(f"[OK] Saved JSON: {json_path}")

            if args.format in ["md", "both"]:
                md_path = os.path.join(args.output, f"{base_name}.md")
                md_content = DiscourseScraper.to_markdown(topic_data)
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                print(f"[OK] Saved Markdown: {md_path}")

        except Exception as e:
            print(f"[!] Error processing {target}: {e}")

if __name__ == "__main__":
    main()
