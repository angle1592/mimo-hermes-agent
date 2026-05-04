# GitHub API Access from China

When `github.com` web pages time out (common behind the GFW on Alibaba Cloud), the GitHub REST API at `api.github.com` often remains accessible. This is because the API endpoint resolves to different IPs and uses a simpler TLS handshake that firewalls are less likely to block.

## Key API endpoints that work from China

### Search repositories (trending discovery)

```bash
curl -s -H "User-Agent: Mozilla/5.0" \
  "https://api.github.com/search/repositories?q=created:>2026-04-24+stars:>50&sort=stars&order=desc&per_page=25"
```

No auth token needed for public data. Adjust `created:>` date to a week ago.

### Get single repo details

```bash
curl -s -H "User-Agent: Mozilla/5.0" \
  "https://api.github.com/repos/{owner}/{repo}"
```

### Rate limits

Without authentication: 60 requests/hour. With a personal access token: 5000 requests/hour. Always use `-H "User-Agent: ..."` — the API rejects requests without it.

## What does NOT work from China

| Method | Works? |
|--------|--------|
| `curl github.com/trending` | ❌ Timeout |
| `requests.get('https://github.com/trending')` from Python | ❌ Timeout |
| `api.github.com/search/repositories` | ✅ Usually works |
| `api.github.com/repos/{owner}/{repo}` | ✅ Usually works |
| `gh` CLI (if installed) | ❌ Uses same endpoints as web |
| GitHub mirror sites (githubfast.com, etc.) | ⚠️ Hit or miss |

## Using the API vs scraping

The GitHub API is the **preferred** method even when web access works:
- Structured JSON, no HTML parsing needed
- You get stars, forks, language, description, topics all in one call
- No need to guess CSS selectors that GitHub might change
- Rate limits are generous enough for daily polling jobs

## Python example

```python
import requests

headers = {'User-Agent': 'Mozilla/5.0'}
url = 'https://api.github.com/search/repositories'
params = {
    'q': 'created:>2026-04-24 stars:>50',
    'sort': 'stars',
    'order': 'desc',
    'per_page': 25
}
resp = requests.get(url, headers=headers, params=params, timeout=20)
data = resp.json()
for item in data['items']:
    print(f"{item['full_name']} ⭐{item['stargazers_count']} — {item.get('description', 'N/A')[:100]}")
```
