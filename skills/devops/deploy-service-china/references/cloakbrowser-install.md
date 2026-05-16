# CloakBrowser Installation on Alibaba Cloud Linux

CloakBrowser is a stealth Chromium with 57 C++ source-level patches. Drop-in Playwright/Puppeteer replacement that passes bot detection (reCAPTCHA v3, Cloudflare Turnstile, FingerprintJS, BrowserScan).

## Installation

```bash
pip install cloakbrowser
# playwright + httpx auto-installed as deps
# Binary: ~200MB Chromium, cached at ~/.cloakbrowser/
```

## Pitfalls

### 1. `playwright install-deps` Fails (apt-get not available)

Same issue as vanilla Playwright — Alibaba Cloud Linux uses yum, not apt. System deps should already be present if Playwright was previously installed. If not:

```bash
yum install -y nss atk at-spi2-atk cups-libs libdrm mesa-libgbm \
  libXcomposite libXdamage libXrandr alsa-lib pango gtk3 libxkbcommon
```

### 2. Stealth Binary Download Times Out (~200MB from GitHub)

The binary downloads from GitHub Releases. On Alibaba Cloud in China, this frequently times out (>300s).

- Primary URL (`cloakbrowser.dev`) **redirects to GitHub** — no speed benefit
- `CLOAKBROWSER_DOWNLOAD_URL` env var can override the source
- GitHub proxy pattern from Step 2 of this skill works:

```bash
# Manual download with GitHub proxy
PROXY="https://ghfast.top/"
URL="https://github.com/CloakHQ/cloakbrowser/releases/download/chromium-v146.0.7680.177.3/cloakbrowser-linux-x64.tar.gz"
curl -L -o /tmp/cloakbrowser.tar.gz "${PROXY}${URL}"

# Extract to cache
mkdir -p ~/.cloakbrowser/chromium-146.0.7680.177.3
tar xzf /tmp/cloakbrowser.tar.gz -C ~/.cloakbrowser/chromium-146.0.7680.177.3 --strip-components=1
chmod +x ~/.cloakbrowser/chromium-146.0.7680.177.3/chrome
```

### 3. Version Pinning

Check `config.py` for current platform version:
```python
python3 -c "from cloakbrowser.config import get_chromium_version; print(get_chromium_version())"
# e.g. "146.0.7680.177.3" for linux-x64
```

Archive name pattern: `cloakbrowser-{platform}.tar.gz` (e.g. `cloakbrowser-linux-x64.tar.gz`)

### 4. Memory Usage

Chromium is memory-hungry. On 2GB servers, limit concurrent pages. The stealth binary adds ~50MB overhead vs stock Chromium.

## Usage (Python)

```python
from cloakbrowser import launch

# Basic
browser = launch()
page = browser.new_page()
page.goto("https://example.com")

# With human-like behavior + GeoIP
browser = launch(
    proxy="http://user:pass@proxy:8080",
    humanize=True,
    geoip=True,
)
```

## Relationship to Vanilla Playwright

- Playwright the library stays (it's a dependency)
- Only the Chromium binary is replaced
- Same API: `launch()` returns standard Playwright `Browser` object
- Both can coexist: use `cloakbrowser.launch()` for stealth, `playwright.chromium.launch()` for normal
