import urllib.request
import xml.etree.ElementTree as ET
import json
import sys
import argparse
import subprocess
from datetime import datetime

# 默认的回退配置（当无法从飞书读取配置时使用）
DEFAULT_RSS_SOURCES = [
    "https://36kr.com/feed",
    "https://www.v2ex.com/index.xml",
    "https://decohack.com/feed/",
    "https://news.ycombinator.com/rss",          # Hacker News (技术与创业)
    "https://www.solidot.org/index.rss",         # Solidot (开源与极客)
    "https://rss.aishort.top/v2ex/nodes/create", # 补充 AI 工具等社区讨论
    "https://rss.aishort.top/oschina/news",      # 替代官方 rsshub，避免 403
    "https://rss.aishort.top/github/trending/daily/any", # 替代官方 rsshub
    "https://rss.aishort.top/techcrunch/news"    # 替代官方 rsshub
]

DEFAULT_EXPANDED_KEYWORDS = [
    "ai", "人工智能", "大模型", "llm", "agent", "智能体", "gpt", "claude", "gemini",
    "具身智能", "机器人", "robot", "算力", "npu", "gpu", "芯片", "英伟达", "nvidia",
    "开源", "github", "工具", "模型", "推理", "inference", "自动化", "automation"
]

def load_config_from_feishu(sheet_token):
    """从飞书电子表格读取配置：信源、白名单、黑名单"""
    print(f"Loading config from Feishu Sheet: {sheet_token}...", file=sys.stderr)
    lark_cmd = "lark-cli.cmd" if sys.platform == "win32" else "lark-cli"
    
    # 获取所有的 sheets
    try:
        cmd = [lark_cmd, "sheets", "+info", "--url", sheet_token, "--as", "user"]
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        info_data = json.loads(result.stdout)
        sheets = info_data.get("data", {}).get("sheets", {}).get("sheets", [])
    except Exception as e:
        print(f"Failed to fetch sheet info: {e}", file=sys.stderr)
        return [], [], []

    sources = []
    whitelist = []
    blacklist = []
    
    for s in sheets:
        title = s.get("title")
        sheet_id = s.get("sheet_id")
        
        # 读取该 sheet 的数据
        try:
            cmd = [lark_cmd, "sheets", "+read", "--url", sheet_token, "--sheet-id", sheet_id, "--range", "A2:A100", "--as", "user"]
            res = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
            read_data = json.loads(res.stdout)
            values = read_data.get("data", {}).get("valueRange", {}).get("values", [])
            
            # 展平数据
            items = []
            for row in values:
                if row and row[0]:
                    items.append(str(row[0]).strip())
                    
            if title == "信源" or title == "Sheet1":
                sources.extend(items)
            elif title == "白名单":
                whitelist.extend(items)
            elif title == "黑名单":
                blacklist.extend(items)
        except Exception as e:
            print(f"Failed to read sheet {title}: {e}", file=sys.stderr)

    print(f"Loaded {len(sources)} sources, {len(whitelist)} whitelist, {len(blacklist)} blacklist keywords.", file=sys.stderr)
    return sources, whitelist, blacklist

def fetch_rss(url):
    try:
        # 添加 User-Agent 防止被简单的反爬虫拦截
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            items = []
            # 兼容 rss (item) 和 atom (entry) 格式
            for item in root.findall('.//item') + root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                title_elem = item.find('title') if item.find('title') is not None else item.find('{http://www.w3.org/2005/Atom}title')
                desc_elem = item.find('description') if item.find('description') is not None else item.find('{http://www.w3.org/2005/Atom}summary')
                link_elem = item.find('link') if item.find('link') is not None else item.find('{http://www.w3.org/2005/Atom}link')
                
                title = title_elem.text if title_elem is not None and title_elem.text else ""
                desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                
                link = ""
                if link_elem is not None:
                    if link_elem.text:
                        link = link_elem.text
                    elif link_elem.get('href'):
                        link = link_elem.get('href')

                if title or desc:
                    items.append({"title": title, "description": desc, "link": link})
            return items
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return []

import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_news.py <keyword>", file=sys.stderr)
        sys.exit(1)
        
    user_keyword = sys.argv[1].lower()
    
    # 从 local_state.json 自动读取 config_sheet_token
    sheet_token = None
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "local_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                sheet_token = state.get("config_sheet_token")
        except:
            pass
            
    if not sheet_token:
        print("Error: config_sheet_token not found in local_state.json. Run setup_workspace.py first.", file=sys.stderr)
        sys.exit(1)
        
    rss_sources = DEFAULT_RSS_SOURCES
    match_keywords = set(DEFAULT_EXPANDED_KEYWORDS)
    black_keywords = set()
    
    # 优先从飞书云文档读取配置
    f_sources, f_white, f_black = load_config_from_feishu(sheet_token)
    print(f"Debug: sources={f_sources}, white={f_white}, black={f_black}", file=sys.stderr)
    if f_sources:
        rss_sources = f_sources
    if f_white:
        match_keywords = set(f_white)
    if f_black:
        black_keywords = set(f_black)
            
    match_keywords.add(user_keyword)
    
    all_news = []
    seen_links = set()
    
    for source in rss_sources:
        items = fetch_rss(source)
        for item in items:
            title = item.get("title", "")
            desc = item.get("description", "")
            link = item.get("link", "")
            
            if link in seen_links and link != "":
                continue
                
            content_to_check = f"{title} {desc}".lower()
            
            # 黑名单过滤
            if any(kw in content_to_check for kw in black_keywords):
                continue
            
            # 白名单匹配
            if any(kw in content_to_check for kw in match_keywords):
                # 清理 HTML 标签等冗余信息 (简单处理)
                clean_desc = desc.replace("<p>", "").replace("</p>", "").replace("<br>", "").strip()
                # 截断过长的描述
                if len(clean_desc) > 300:
                    clean_desc = clean_desc[:300] + "..."
                    
                all_news.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "description": clean_desc
                })
                seen_links.add(link)
                
            # 4. 放宽硬性数量限制：从 20 条放宽到 50 条，给大模型更多提炼空间
            if len(all_news) >= 50:
                break
        if len(all_news) >= 50:
            break
            
    # Fix for Windows stdout encoding issue
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        
    print(json.dumps(all_news, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
