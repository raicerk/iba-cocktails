import json
import argparse
import sys
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

def scrape_cocktail_details(page, url):
    print(f"Scraping {url}...")
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Failed to load {url}: {e}", file=sys.stderr)
        return None

    result = {
        "ingredients": [],
        "method": "",
        "garnish": "",
        "video_link": ""
    }

    try:
        # Try finding ingredients
        ing_heading = page.locator("h4, h3, h2").filter(has_text=re.compile(r"Ingredients", re.IGNORECASE)).first
        if ing_heading.count() > 0:
            wrap = ing_heading.locator("xpath=ancestor::div[contains(@class, 'elementor-widget-wrap')]").first
            if wrap.count() > 0:
                lis = wrap.locator("ul").first.locator("li").all_inner_texts()
                result["ingredients"] = [text.strip() for text in lis if text.strip()]
    except Exception as e:
        print(f"  Error parsing ingredients: {e}")

    try:
        method_heading = page.locator("h4, h3, h2").filter(has_text=re.compile(r"Method", re.IGNORECASE)).first
        if method_heading.count() > 0:
            next_widget = method_heading.locator("xpath=../../following-sibling::div")
            paras = next_widget.locator("p").all_inner_texts()
            result["method"] = "\\n".join([p.strip() for p in paras if p.strip()])
    except Exception as e:
        print(f"  Error parsing method: {e}")

    try:
        garnish_heading = page.locator("h4, h3, h2").filter(has_text=re.compile(r"Garnish", re.IGNORECASE)).first
        if garnish_heading.count() > 0:
            next_widget = garnish_heading.locator("xpath=../../following-sibling::div")
            paras = next_widget.locator("p").all_inner_texts()
            result["garnish"] = "\\n".join([p.strip() for p in paras if p.strip()])
    except Exception as e:
        print(f"  Error parsing garnish: {e}")

    try:
        # Video link (a href with youtube or iframe)
        video_link_a = page.locator("a").filter(has_text=re.compile(r"Play Video", re.IGNORECASE)).first
        if video_link_a.count() > 0:
            result["video_link"] = video_link_a.get_attribute("href")
        else:
            iframe = page.locator("iframe[src*='youtube.com'], iframe[src*='vimeo.com']").first
            if iframe.count() > 0:
                result["video_link"] = iframe.get_attribute("src")
    except Exception as e:
        print(f"  Error parsing video: {e}")

    return result

def main():
    input_file = "cocktails.json"
    output_file = "cocktails.json"
    
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    cocktails = data.get("cocktails", [])
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        for idx, cocktail in enumerate(cocktails):
            url = cocktail.get("url")
            if not url:
                continue
                
            details = scrape_cocktail_details(page, url)
            if details:
                cocktail["ingredients"] = details.get("ingredients", [])
                cocktail["method"] = details.get("method", "")
                cocktail["garnish"] = details.get("garnish", "")
                cocktail["video_link"] = details.get("video_link", "")
            
            # small delay
            time.sleep(1)
                
        browser.close()
        
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
if __name__ == "__main__":
    main()
