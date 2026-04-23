import json
import os
import sys

def main():
    try:
        with open("categorized_news.json", "r", encoding="utf-8") as f:
            news_data = json.load(f)
    except Exception as e:
        print(f"Error loading categorized_news.json: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. Generate Markdown Summary
    summary_md = f"{news_data.get('intro', '')}\n\n"
    for cat in news_data.get('categories', []):
        icon = "📌" if cat['name'] == "客观事实类速报" else ("💬" if cat['name'] == "话题引导推文" else "🛠️")
        summary_md += f"## {icon} {cat['name']}\n\n"
        for item in cat.get('items', []):
            summary_md += f"### {icon} {item['title']}\n"
            summary_md += f"> {item['desc']}\n"
            summary_md += f"- [点击阅读原文]({item['link']})\n\n"

    with open("summary.md", "w", encoding="utf-8") as f:
        f.write(summary_md)

    # 2. Generate Whiteboard DSL dynamically based on categories (3-column layout)
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
                    { "type": "text", "text": item['desc'], "fontSize": 13, "textColor": "#646A73", "width": "fill-container", "height": "fit-content" }
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
    col1 = []
    col2 = []
    col3 = []

    for cat in news_data.get('categories', []):
        block = create_block(cat)
        if cat['name'] == "客观事实类速报":
            col1.append(block)
        elif cat['name'] == "话题引导推文":
            col2.append(block)
        elif cat['name'] == "工具/产品推荐":
            col3.append(block)
        else:
            # Fallback if there are unknown categories
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
            # Add an empty container to preserve 3-column width layout even if a category is missing
            columns.append({
                "type": "frame",
                "layout": "vertical",
                "gap": 0,
                "padding": 0,
                "width": "fill-container",
                "height": "fit-content",
                "children": []
            })

    # If only one column is needed (e.g. very few items), just use one column
    # The layout handles this naturally since columns list will only have 1 item
    
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
              "alignItems": "start", # align top instead of stretch for masonry
              "children": columns
            }
          ]
        }
      ]
    }

    with open("board.json", "w", encoding="utf-8") as f:
        json.dump(board_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
