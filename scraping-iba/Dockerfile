FROM python:3.10-slim

WORKDIR /app

# Install playwright and browser dependencies
RUN pip install --default-timeout=100 --retries 5 --no-cache-dir playwright && \
    playwright install chromium --with-deps

# Copy scripts
COPY . .

# Run the scripts in sequence
CMD ["sh", "-c", "python scraper.py && python scrape_details.py && python parse_ingredients.py"]
