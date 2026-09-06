from __future__ import annotations
"""
IBA Cocktails Scraper — Playwright edition
==========================================
Usa Playwright (Chromium headless) para renderizar el JS de la página
y extraer el listado completo de cocteles IBA.

La página usa Elementor + lazy-loading, por eso requests/BeautifulSoup
no funciona directamente (el HTML de los cocteles no está en el servidor
sino que se inyecta vía JavaScript tras la carga).

Campos capturados por coctel:
  - name        : Nombre del coctel
  - slug        : Identificador URL (slug)
  - url         : URL completa de la ficha
  - category    : Categoría IBA
  - image_url   : URL de la imagen
  - views       : Contador de vistas

Uso:
  python scraper.py                   # Guarda en cocktails.json
  python scraper.py -o output.json    # Archivo de salida personalizado
  python scraper.py --no-save         # Solo imprime JSON por consola
  python scraper.py --headful         # Muestra el navegador (debug)
"""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ──────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────

BASE_URL = "https://iba-world.com/cocktails/all-cocktails/"
PAGE_URL = "https://iba-world.com/cocktails/all-cocktails/page/{page}/"

# Tiempo máximo de espera por página (ms)
PAGE_TIMEOUT = 45_000
# Tiempo de espera extra para que cargue el contenido JS (ms)
JS_WAIT = 4_000
# Delay entre páginas (ms) — evita throttling / ERR_HTTP2
PAGE_DELAY = 3_000
# Intentos máximos por página
MAX_RETRIES = 3


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def dismiss_age_gate(page) -> None:
    """Cierra el age gate si aparece (verificación de mayoría de edad)."""
    try:
        # Intentar hacer clic en el botón de confirmación del age gate
        btn = page.locator(
            "button[class*='age'], "
            "input[class*='age'][type='submit'], "
            "[class*='age-gate'] button, "
            "[id*='age-gate'] button, "
            "[class*='age-gate'] input[type='submit']"
        ).first
        if btn.is_visible(timeout=3_000):
            btn.click()
            page.wait_for_timeout(1_000)
    except PlaywrightTimeout:
        pass  # No había age gate, continuar normalmente


def get_total_pages(page) -> int:
    """Detecta el total de páginas leyendo los links de paginación."""
    try:
        links = page.locator("a.page-numbers").all()
        numbers = []
        for link in links:
            text = link.inner_text().strip()
            if text.isdigit():
                numbers.append(int(text))
        return max(numbers) if numbers else 1
    except Exception:
        return 1


def extract_cocktails_from_page(page) -> list[dict]:
    """
    Extrae todos los cocteles de la página actual usando JavaScript
    ejecutado directamente en el contexto del navegador.
    """
    cocktails = page.evaluate("""
    () => {
        const results = [];

        // Selectores posibles para las tarjetas de coctel
        const selectors = [
            'article.elementor-post',
            '.elementor-loop-item',
            '[class*="elementor-post"]',
            'article[class*="iba"]',
        ];

        let cards = [];
        for (const sel of selectors) {
            const found = document.querySelectorAll(sel);
            if (found.length > 0) {
                cards = Array.from(found);
                break;
            }
        }

        for (const card of cards) {
            // Buscar el link principal
            const linkEl = card.querySelector('a[href]');
            if (!linkEl) continue;

            const url = linkEl.href;
            // Filtrar solo links de cocteles
            if (!url.includes('iba-cocktail') && !url.includes('/cocktail')) continue;

            const slug = url.replace(/\\/+$/, '').split('/').pop();

            // Imagen
            const imgEl = card.querySelector('img');
            const imageUrl = imgEl ? (imgEl.dataset.src || imgEl.src) : '';
            const altName = imgEl ? imgEl.alt : '';

            // Nombre
            const h2El = card.querySelector('h2, h3, .elementor-post__title');
            const name = h2El ? h2El.textContent.trim() : altName || slug;

            // Textos de metadatos (categoría, vistas)
            // Son los nodos de texto dentro del card excluyendo nombre e imagen
            const metaTexts = [];
            const metaEls = card.querySelectorAll(
                '.elementor-post__meta, ' +
                '[class*="meta"], ' +
                '[class*="category"], ' +
                '[class*="views"], ' +
                '.elementor-icon-list-text'
            );

            metaEls.forEach(el => {
                const text = el.textContent.trim();
                if (text && text !== name) {
                    metaTexts.push(text);
                }
            });

            results.push({
                name: name,
                slug: slug,
                url: url,
                category: metaTexts[0] || '',
                image_url: imageUrl,
                views: metaTexts[1] || '',
            });
        }

        return results;
    }
    """)
    return cocktails or []


def extract_cocktails_fallback(page) -> list[dict]:
    """
    Estrategia alternativa: busca todos los links que apunten a páginas
    de cocteles, sin depender de clases específicas de Elementor.
    Útil si la estructura de clases cambia.
    """
    cocktails = page.evaluate("""
    () => {
        const results = [];
        const seen = new Set();

        // Buscar todos los links que sean de cocteles IBA
        const allLinks = document.querySelectorAll('a[href]');

        for (const a of allLinks) {
            const url = a.href;
            if (!url.includes('iba-cocktail') && !url.includes('/iba-cocktail/')) {
                continue;
            }
            if (seen.has(url)) continue;
            seen.add(url);

            const slug = url.replace(/\\/+$/, '').split('/').pop();

            // Buscar imagen más cercana
            const card = a.closest('[class*="post"], [class*="item"], article, li, div') || a;
            const imgEl = card.querySelector('img') || a.querySelector('img');
            const imageUrl = imgEl ? (imgEl.dataset.src || imgEl.src) : '';
            const altName = imgEl ? imgEl.alt : '';

            // Nombre: intentar h2/h3 o texto del link
            const headingEl = card.querySelector('h2, h3, h4');
            const name = (headingEl ? headingEl.textContent.trim() : '') ||
                          a.textContent.trim() ||
                          altName ||
                          slug;

            if (!name) continue;

            // Inferir categoría desde la URL de la imagen
            let category = '';
            if (imageUrl.includes('the-unforgettables')) {
                category = 'The Unforgettables';
            } else if (imageUrl.includes('contemporary') || imageUrl.includes('the-contemporary')) {
                category = 'Contemporary Classics';
            } else if (imageUrl.includes('new-era')) {
                category = 'New Era Drinks';
            }

            results.push({
                name: name,
                slug: slug,
                url: url,
                category: category,
                image_url: imageUrl,
                views: '',
            });
        }
        return results;
    }
    """)
    return cocktails or []


def scrape_cocktails_page(page, url: str, page_num: int) -> list[dict]:
    """Navega a una URL de página y extrae los cocteles. Reintenta en caso de error HTTP2."""
    print(f"  → Página {page_num}: {url}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Delay creciente entre reintentos
            if attempt > 1:
                wait_ms = PAGE_DELAY * attempt
                print(f"     ↻ Reintento {attempt}/{MAX_RETRIES} (esperando {wait_ms/1000:.0f}s)...")
                page.wait_for_timeout(wait_ms)

            page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
            # Esperar a que el JS de Elementor renderice el contenido
            page.wait_for_timeout(JS_WAIT)

            # Scroll para activar lazy-load
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(1_000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1_000)
            break  # Éxito, salir del loop de reintentos

        except (PlaywrightTimeout, Exception) as exc:
            if attempt == MAX_RETRIES:
                print(f"  [ERROR] Fallé {MAX_RETRIES} veces en página {page_num}: {exc}", file=sys.stderr)
                return []
            print(f"  [WARN] Error en página {page_num} (intento {attempt}): {type(exc).__name__}", file=sys.stderr)

    dismiss_age_gate(page)

    # Estrategia 1: selectores específicos de Elementor
    cocktails = extract_cocktails_from_page(page)

    # Estrategia 2 (fallback): buscar todos los links de cocteles
    if not cocktails:
        print(f"     ⚠ Estrategia 1 sin resultados, usando fallback...")
        cocktails = extract_cocktails_fallback(page)

    print(f"     ✓ {len(cocktails)} cocteles encontrados")
    return cocktails


# ──────────────────────────────────────────────
# Flujo principal
# ──────────────────────────────────────────────

def scrape_all(headful: bool = False) -> list[dict]:
    """Orquesta el scraping completo de todas las páginas."""
    all_cocktails: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            }
        )
        # Bypass age gate via cookie
        context.add_cookies([
            {"name": "age_gate", "value": "1", "domain": "iba-world.com", "path": "/"},
            {"name": "age-gate", "value": "true", "domain": "iba-world.com", "path": "/"},
        ])

        page = context.new_page()

        # ── Paso 1: Cargar primera página y detectar total de páginas ──
        print("\n[1/3] Cargando primera página y detectando paginación...")
        try:
            page.goto(BASE_URL, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
            page.wait_for_timeout(JS_WAIT)
        except PlaywrightTimeout:
            print("[ERROR] No se pudo cargar la página principal.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        dismiss_age_gate(page)

        total_pages = get_total_pages(page)
        print(f"       Total de páginas detectadas: {total_pages}")

        # ── Paso 2: Extraer cocteles de todas las páginas ──
        print("\n[2/3] Extrayendo cocteles de todas las páginas...")

        # Primera página (ya cargada)
        cocktails_p1 = extract_cocktails_from_page(page)
        if not cocktails_p1:
            cocktails_p1 = extract_cocktails_fallback(page)
        print(f"  → Página 1: {len(cocktails_p1)} cocteles encontrados")
        all_cocktails.extend(cocktails_p1)

        # Páginas restantes
        for page_num in range(2, total_pages + 1):
            # Delay entre páginas para evitar throttling
            page.wait_for_timeout(PAGE_DELAY)
            url = PAGE_URL.format(page=page_num)
            cocktails = scrape_cocktails_page(page, url, page_num)
            all_cocktails.extend(cocktails)

        browser.close()

    # Eliminar duplicados preservando orden
    seen: set[str] = set()
    unique: list[dict] = []
    for c in all_cocktails:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)

    return unique


# ──────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scraper de cocteles oficiales IBA — usa Playwright/Chromium"
    )
    parser.add_argument(
        "-o", "--output",
        default="cocktails.json",
        help="Archivo de salida JSON (default: cocktails.json)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Solo imprime JSON por consola, no guarda archivo",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Mostrar ventana del navegador (útil para depurar)",
    )
    args = parser.parse_args()

    print("=" * 55)
    print("  IBA Cocktails Scraper (Playwright edition)")
    print("  https://iba-world.com/cocktails/all-cocktails/")
    print("=" * 55)

    cocktails = scrape_all(headful=args.headful)

    print(f"\n[3/3] Total de cocteles extraídos: {len(cocktails)}")

    output = {
        "source": BASE_URL,
        "total": len(cocktails),
        "cocktails": cocktails,
    }

    if args.no_save:
        print("\n--- JSON Output ---")
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n✅ Guardado en: {output_path.resolve()}")

    # Vista previa de primeros 5 cocteles
    print("\n--- Vista previa (primeros 5) ---")
    for i, c in enumerate(cocktails[:5], 1):
        print(f"  {i}. {c['name']:30s} | {c['category']:25s} | {c['url']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
