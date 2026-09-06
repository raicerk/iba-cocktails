import json
import re

def parse_ingredient_line(line):
    line = line.strip()
    result = {
        "ingredient": line,
        "quantity": None,
        "unit": None,
        "original": line
    }
    
    if not line or line.lower() == "n/a":
        return result

    # Regex to capture quantity at the start. Matches numbers, decimals, fractions (e.g. 1/2, 1.5, 30, 2-3)
    qty_match = re.match(r'^([\d\.\/\-]+(?:(?:\s+|-)[\d\.\/\-]+)?)\s+', line)
    
    if qty_match:
        qty_str = qty_match.group(1).strip()
        
        # Try to evaluate the quantity to a float
        try:
            if '/' in qty_str and '-' not in qty_str and ' ' not in qty_str:
                num, den = qty_str.split('/')
                qty_val = float(num) / float(den)
            elif '-' in qty_str:
                # e.g., 2-3 dashes -> use the max or average, let's just keep as string or take average
                parts = qty_str.split('-')
                qty_val = (float(parts[0]) + float(parts[1])) / 2
            else:
                qty_val = float(qty_str)
            result["quantity"] = round(qty_val, 2)
        except Exception:
            # If parsing fails, just keep it as a string or leave None
            result["quantity"] = qty_str
        
        remainder = line[qty_match.end():]
        
        # Regex to capture known units
        units_pattern = r'^(ml|cl|oz|dash(?:es)?|drop(?:s)?|bar spoon(?:s)?|tsp|tbsp|part(?:s)?|cube(?:s)?|sprig(?:s)?|leaf|leaves|wedge(?:s)?|slice(?:s)?|piece(?:s)?)\b\s*'
        unit_match = re.match(units_pattern, remainder, re.IGNORECASE)
        
        if unit_match:
            result["unit"] = unit_match.group(1).lower().strip()
            result["ingredient"] = remainder[unit_match.end():].strip()
        else:
            # No specific unit found, meaning the quantity refers directly to the ingredient (e.g. "1/2 Fresh Lime")
            result["unit"] = None
            result["ingredient"] = remainder.strip()
            
    else:
        # Check for textual quantities like "Half", "A dash of", "Top up with"
        if line.lower().startswith("top up with "):
            result["ingredient"] = line[len("top up with "):].strip()
            result["unit"] = "top up"
        elif line.lower().startswith("fill with "):
            result["ingredient"] = line[len("fill with "):].strip()
            result["unit"] = "fill"
        else:
            # Just ingredient
            pass

    # Clean up ingredient text (e.g., if it starts with 'of ')
    if result["ingredient"].lower().startswith("of "):
        result["ingredient"] = result["ingredient"][3:].strip()
        
    return result

def main():
    input_file = "cocktails.json"
    output_file = "cocktails_parsed.json"
    
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for cocktail in data.get("cocktails", []):
        raw_ingredients = cocktail.get("ingredients", [])
        
        # Avoid double parsing if already parsed
        if raw_ingredients and isinstance(raw_ingredients[0], dict):
            continue
            
        parsed_ingredients = []
        for line in raw_ingredients:
            # some cocktails have extra text or method steps in ingredients due to scraper,
            # but we parse it anyway. The user can refine later.
            parsed = parse_ingredient_line(line)
            parsed_ingredients.append(parsed)
            
        cocktail["ingredients"] = parsed_ingredients
        
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print("Parsed ingredients successfully. Saved to cocktails_parsed.json")

if __name__ == "__main__":
    main()
