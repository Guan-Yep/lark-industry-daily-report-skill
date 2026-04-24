import json
import sys
from datetime import datetime

def generate_xiaohongshu_card(news_data, date_str=""):
    """
    生成小红书风格的飞书交互式卡片 JSON 结构
    风格：高情绪价值标题、Emoji 丰富、带标签、带交互反馈按钮
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "template": "red",
            "title": {
                "content": f"🍓 {date_str} AI 行业日报",
                "tag": "plain_text"
            }
        },
        "elements": [
            {
                "tag": "markdown",
                "content": "**✨ 今日精选高能资讯，滑动解锁你的 AI 灵感库！**\n\n*(👇 点击卡片下方的按钮，告诉我你的喜好，我会越来越懂你哦~)*"
            },
            {
                "tag": "hr"
            }
        ]
    }
    
    # 选取前 5 条作为精选推送，避免卡片过长
    top_news = news_data[:5]
    
    for i, item in enumerate(top_news):
        title = item.get("title", "")
        desc = item.get("desc", "") # fix description key mapping
        link = item.get("link", "")
        category = item.get("category", "行业资讯")
        
        # 简单的小红书风格包装 (提取关键字作为封面词/Tag)
        # 实际生产中这里是由 LLM 提炼出的 cover_word 和 emojis
        emoji = "🔥" if i == 0 else "🚀" if i == 1 else "💡"
        
        md_content = f"**{emoji} [{title}]({link})**\n"
        md_content += f"👉 **核心亮点**：{desc}\n"
        md_content += f"🏷️ #{category}"
        
        card["elements"].append({
            "tag": "markdown",
            "content": md_content
        })
        
        # 添加交互按钮 (单选打分/反馈)
        card["elements"].append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "👍 多推此类"
                    },
                    "type": "primary",
                    "value": {
                        "action": "like",
                        "news_title": title,
                        "type": "feedback"
                    }
                },
                {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": "👎 减少相似"
                    },
                    "type": "default",
                    "value": {
                        "action": "dislike",
                        "news_title": title,
                        "type": "feedback"
                    }
                }
            ]
        })
        
        # 分割线 (最后一条不加)
        if i < len(top_news) - 1:
            card["elements"].append({
                "tag": "hr"
            })
            
    # 底部提示
    card["elements"].append({
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": "📝 你的每一次点击，都在塑造专属于你的 AI 信息信息流。"
            }
        ]
    })
    
    return card

def main():
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 优先使用经过 generate_report.py 宽容解析后生成的标准化数据
    json_path = os.path.join(base_dir, "parsed_news.json")
    if not os.path.exists(json_path):
        # 兼容旧版本或过渡期
        json_path = os.path.join(base_dir, "categorized_news.json")
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                news_data = data
                date_str = ""
            else:
                date_str = data.get("date", "")
                news_data = []
                for category in data.get("categories", []):
                    cat_name = category.get("name", "")
                    for item in category.get("items", []):
                        item["category"] = cat_name
                        news_data.append(item)
    except Exception as e:
        print(f"Error loading {json_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    card_json = generate_xiaohongshu_card(news_data, date_str)
    
    out_path = os.path.join(base_dir, "message_card.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(card_json, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully generated {out_path}")

if __name__ == "__main__":
    main()
