import json
import os
import sys
import re
from datetime import datetime

def parse_markdown_draft(md_content):
    """
    宽容解析器：从 Markdown 文本中提取结构化数据。
    即使 Agent 格式有微小偏差，也能通过标题层级和正则匹配提取核心内容。
    """
    news_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "intro": "",
        "categories": []
    }
    
    # 提取总导语 (匹配第一个一级标题后的文本，直到遇到二级标题)
    intro_match = re.search(r'^#\s+.*?\n+(.*?)(?=\n##\s+|\Z)', md_content, re.DOTALL | re.MULTILINE)
    if intro_match:
        # 清理首尾空白
        news_data["intro"] = intro_match.group(1).strip()
    
    # 标准分类映射表 (防范大模型自创分类名)
    standard_categories = ["客观事实类速报", "话题引导推文", "工具/产品推荐"]
    
    # 按照二级标题切分内容块
    # 使用正则前瞻 (?=^## |$) 来分割每个二级标题区块
    sections = re.split(r'(?m)^##\s+', md_content)
    
    # sections[0] 是一级标题和导语部分，从 sections[1] 开始是各个分类
    for section in sections[1:]:
        if not section.strip():
            continue
            
        lines = section.strip().split('\n')
        raw_cat_name = lines[0].strip()
        
        # 宽容匹配分类名称，去除可能的 emoji 或多余标点
        clean_cat_name = re.sub(r'[^\w/]', '', raw_cat_name)
        matched_cat = None
        
        for std_cat in standard_categories:
            # 如果标准分类名包含在提取出的分类名中（如“📌客观事实类速报”），则视为匹配
            if std_cat in raw_cat_name or clean_cat_name in std_cat:
                matched_cat = std_cat
                break
                
        # 兜底机制：如果完全不匹配，归入“工具/产品推荐”或者保留原名（后续会在画板生成时兜底）
        final_cat_name = matched_cat if matched_cat else raw_cat_name
        
        category = {
            "name": final_cat_name,
            "items": []
        }
        
        # 在这个分类区块中，按照三级标题提取每个新闻条目
        # 使用 re.split 切分三级标题
        items_raw = re.split(r'(?m)^###\s+', '\n'.join(lines[1:]))
        
        for item_raw in items_raw[1:]: # items_raw[0] 可能是三级标题前的空白
            if not item_raw.strip():
                continue
                
            item_lines = item_raw.strip().split('\n')
            title = item_lines[0].strip()
            
            # 提取摘要 (匹配 > 开头的行)
            desc_lines = []
            link = ""
            
            for line in item_lines[1:]:
                line = line.strip()
                if line.startswith('>'):
                    # 移除开头的 > 和空格
                    desc_lines.append(re.sub(r'^>\s*', '', line))
                elif line.startswith('-') and '[' in line and '](' in line:
                    # 提取链接
                    link_match = re.search(r'\[.*?\]\((.*?)\)', line)
                    if link_match:
                        link = link_match.group(1)
            
            # 组装单条新闻
            desc = ' '.join(desc_lines)
            # 如果大模型忘了写 >，兜底提取非链接行作为摘要
            if not desc:
                fallback_desc = [l for l in item_lines[1:] if not l.startswith('-') and l.strip()]
                desc = ' '.join(fallback_desc)
                
            category["items"].append({
                "title": title,
                "desc": desc,
                "link": link
            })
            
        if category["items"]:
            news_data["categories"].append(category)
            
    return news_data

def generate_summary_md(news_data):
    """根据提取的结构化数据，生成规范的飞书文档用 Markdown"""
    summary_md = f"{news_data.get('intro', '')}\n\n"
    for cat in news_data.get('categories', []):
        icon = "📌" if cat['name'] == "客观事实类速报" else ("💬" if cat['name'] == "话题引导推文" else "🛠️")
        summary_md += f"## {icon} {cat['name']}\n\n"
        for item in cat.get('items', []):
            summary_md += f"### {icon} {item['title']}\n"
            if item['desc']:
                summary_md += f"> {item['desc']}\n"
            if item['link']:
                summary_md += f"- [点击阅读原文]({item['link']})\n\n"
            else:
                summary_md += "\n"
    return summary_md

def generate_whiteboard_dsl(news_data):
    """根据提取的结构化数据，生成飞书画板 DSL"""
    color_map = {
        "客观事实类速报": {"border": "#047fb0", "bg": "#F5F9FB", "icon": "#047fb0", "icon_name": "cpu"},
        "话题引导推文": {"border": "#d25d5a", "bg": "#FDF6F6", "icon": "#d25d5a", "icon_name": "trending-up"},
        "工具/产品推荐": {"border": "#333dcc", "bg": "#F6F7FD", "icon": "#333dcc", "icon_name": "tool"}
    }
    
    default_style = {"border": "#6b7f06", "bg": "#F8FAF2", "icon": "#6b7f06", "icon_name": "pie-chart"}

    def create_block(category):
        c_style = color_map.get(category['name'], default_style)
        
        children_nodes = [
            {
                "type": "text", 
                "text": category['name'], 
                "fontSize": 18, 
                "fontWeight": "bold", 
                "textColor": c_style['border'], 
                "width": "fill-container", 
                "height": "fit-content"
            }
        ]
        
        for item in category.get('items', []):
            children_nodes.append({
                "type": "frame",
                "layout": "vertical",
                "gap": 8,
                "padding": 16,
                "fillColor": c_style['bg'],
                "borderRadius": 8,
                "width": "fill-container",
                "height": "fit-content",
                "children": [
                    { "type": "text", "text": item['title'], "fontSize": 15, "fontWeight": "bold", "textColor": "#1F2329", "width": "fill-container", "height": "fit-content" },
                    { "type": "text", "text": item.get('desc', ''), "fontSize": 13, "textColor": "#646A73", "width": "fill-container", "height": "fit-content" }
                ]
            })
            
        return {
            "type": "frame",
            "layout": "vertical",
            "gap": 16,
            "padding": 24,
            "width": "fill-container",
            "height": "fit-content",
            "fillColor": "#FFFFFF",
            "borderColor": c_style['border'],
            "borderWidth": 2,
            "borderRadius": 12,
            "children": children_nodes
        }

    # Dynamically distribute blocks into three columns based on specific categories
    col1, col2, col3 = [], [], []

    for cat in news_data.get('categories', []):
        block = create_block(cat)
        if cat['name'] == "客观事实类速报":
            col1.append(block)
        elif cat['name'] == "话题引导推文":
            col2.append(block)
        else:
            # 工具推荐及所有未识别的“自创”分类，都作为兜底放入第三列
            col3.append(block)

    columns = []
    for col in [col1, col2, col3]:
        if col:
            columns.append({
                "type": "frame",
                "layout": "vertical",
                "gap": 24,
                "padding": 0,
                "width": "fill-container",
                "height": "fit-content",
                "children": col
            })
        else:
            # Add an empty container to preserve 3-column width layout
            columns.append({
                "type": "frame",
                "layout": "vertical",
                "gap": 0,
                "padding": 0,
                "width": "fill-container",
                "height": "fit-content",
                "children": []
            })

    board_data = {
      "version": 2,
      "nodes": [
        {
          "type": "frame",
          "layout": "vertical",
          "gap": 32,
          "padding": 40,
          "width": 1200,
          "height": "fit-content",
          "fillColor": "#FFFFFF",
          "children": [
            {
              "type": "frame",
              "layout": "vertical",
              "gap": 12,
              "padding": 0,
              "width": "fill-container",
              "height": "fit-content",
              "alignItems": "start",
              "children": [
                {
                  "type": "text",
                  "text": f"{news_data.get('date', '今日')} 行业日报核心动态",
                  "fontSize": 28,
                  "fontWeight": "bold",
                  "textAlign": "left",
                  "width": "fill-container",
                  "height": "fit-content",
                  "textColor": "#1F2329"
                },
                {
                  "type": "text",
                  "text": news_data.get('intro', ''),
                  "fontSize": 16,
                  "textAlign": "left",
                  "width": "fill-container",
                  "height": "fit-content",
                  "textColor": "#8F959E"
                }
              ]
            },
            {
              "type": "frame",
              "layout": "horizontal",
              "gap": 24,
              "padding": 0,
              "width": "fill-container",
              "height": "fit-content",
              "alignItems": "start",
              "children": columns
            }
          ]
        }
      ]
    }
    return board_data

def main():
    draft_file = "draft_report.md"
    
    # 兼容过渡期：如果不存在 draft_report.md 但存在旧的 JSON，尝试从中读取
    if not os.path.exists(draft_file):
        if os.path.exists("categorized_news.json"):
            print("Warning: Found deprecated categorized_news.json instead of draft_report.md. Attempting to fallback...", file=sys.stderr)
            try:
                with open("categorized_news.json", "r", encoding="utf-8") as f:
                    news_data = json.load(f)
            except Exception as e:
                print(f"Error parsing legacy JSON: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Error: Could not find {draft_file}. Please ensure Agent has generated the Markdown draft.", file=sys.stderr)
            sys.exit(1)
    else:
        # 核心主干：解析 Markdown 草稿
        try:
            with open(draft_file, "r", encoding="utf-8") as f:
                md_content = f.read()
            news_data = parse_markdown_draft(md_content)
        except Exception as e:
            print(f"Error parsing Markdown draft: {e}", file=sys.stderr)
            sys.exit(1)

    # 如果解析出来没有任何新闻分类，抛出异常阻止生成空白板
    if not news_data.get("categories"):
        print("Warning: No valid news categories could be parsed from the draft. Please check the Markdown format.", file=sys.stderr)
        sys.exit(1)

    # 1. 重新生成标准的 Markdown (确保格式完美对齐，过滤掉 Agent 可能带入的杂音)
    summary_md = generate_summary_md(news_data)
    with open("summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)
    print("Successfully generated summary.md")

    # 2. 生成白板 DSL
    board_data = generate_whiteboard_dsl(news_data)
    with open("board.json", "w", encoding="utf-8") as f:
        json.dump(board_data, f, ensure_ascii=False, indent=2)
    print("Successfully generated board.json DSL")
    
    # 3. 将解析出的结构化数据存为中间件（供 send_card.py 继续使用，保持兼容）
    with open("parsed_news.json", "w", encoding="utf-8") as f:
        json.dump(news_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()