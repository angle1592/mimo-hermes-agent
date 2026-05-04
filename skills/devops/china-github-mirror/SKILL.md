---
name: china-github-mirror
description: Configure git to use a GitHub mirror for servers in China where github.com is slow or unreachable.
tags: [git, github, mirror, china, proxy, network]
---

# China GitHub Mirror Setup

On servers behind the Great Firewall (e.g., Alibaba Cloud domestic regions), direct `git clone https://github.com/...` may fail due to network restrictions, timeouts, or protocol errors. This skill covers finding a working mirror and configuring git to use it transparently.

## When to Use

- User reports `git clone` failures, timeouts, or protocol errors from a China-based server
- `ping github.com` works but `git clone` fails (common: HTTP/2 PROTOCOL_ERROR)
- User mentions Alibaba Cloud, Tencent Cloud, Huawei Cloud (China regions)
- You detect Chinese locale, timezone, or `/etc/os-release` indicating `ID=alinux` etc.

## Steps

### 1. Verify the issue

```bash
# Check basic connectivity
curl -s --connect-timeout 10 -o /dev/null -w "HTTP %{http_code}  Time %{time_total}s\n" https://github.com

# Try an actual clone to see the error
git clone --depth=1 https://github.com/NousResearch/hermes-agent.git /tmp/test-clone
```

Common failure patterns:
- `HTTP/2 stream 1 was not closed cleanly: PROTOCOL_ERROR`
- `Failed to connect to github.com port 443: Connection timed out`
- `The requested URL returned error: 502`

### 2. Find a working mirror

Test multiple mirrors (they come and go — always verify before configuring):

```bash
for url in \
  "https://githubfast.com" \
  "https://ghproxy.net" \
  "https://ghproxy.cc" \
  "https://hub.gitmirror.com" \
  "https://gitclone.com"; do
  code=$(curl -s --connect-timeout 8 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
  echo "$code  $url"
done
```

If direct GitHub works fast (e.g., < 2s), just use it directly and skip the rest. Mirrors add latency.

### 3. Verify the mirror with an actual clone

```bash
MIRROR="https://githubfast.com"
timeout 30 git clone --depth=1 "${MIRROR}/NousResearch/hermes-agent.git" /tmp/test-mirror
```

### 4. Configure git for transparent mirroring

Use git's `insteadOf` directive — this lets users keep using normal `https://github.com/` URLs while git transparently rewrites them:

```bash
git config --global url."https://githubfast.com/".insteadOf "https://github.com/"
```

This writes to `~/.gitconfig`. Verify:

```bash
cat ~/.gitconfig
# Should show:
# [url "https://githubfast.com/"]
#   insteadOf = https://github.com/
```

### 5. Test the mirror is actually working

```bash
git clone --depth=1 https://github.com/SomeUser/SomeRepo.git /tmp/verify
rm -rf /tmp/verify
# If it succeeds, the mirror is working transparently
```

### 6. Revert (if needed)

```bash
git config --global --unset url."https://githubfast.com/".insteadOf
```

## Downloading GitHub Release Assets

Mirrors configured via `insteadOf` only work for `git clone/pull`. For **release asset downloads** (`curl` or `wget` to `github.com/...releases/...`), you need a different approach:

```bash
# Direct download (often slow or times out)
curl -L -o file.tar.gz https://github.com/user/repo/releases/download/v1.0/file.tar.gz

# Use ghfast.top as a proxy prefix (tested 2026-05, ~4MB/s from Alibaba Cloud)
curl -L -o file.tar.gz "https://ghfast.top/https://github.com/user/repo/releases/download/v1.0/file.tar.gz"
```

The proxy URL format is: `https://ghfast.top/<original-github-url>`

If `ghfast.top` stops working, alternatives to try: `https://mirror.ghproxy.com/`, `https://gh-proxy.com/`.

## Docker Hub Mirror

`docker pull` from `registry-1.docker.io` also fails in China. Configure mirrors in `/etc/docker/daemon.json`:

```json
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://registry.docker-cn.com",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
```

Note: These mirrors come and go too. If `docker pull` still fails after configuring, consider downloading binaries directly via `ghfast.top` instead of using Docker.

## Pushing to GitHub from China

The `insteadOf` mirror config works transparently for `git push` too — git rewrites the URL the same way. But push requires authentication. Set up `~/.git-credentials`:

```bash
# Store credentials for the mirror host
echo "https://USERNAME:PAT@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials

# Configure git to use stored credentials
git config --global credential.helper store
```

**Important:** The credential URL must use `github.com` (not the mirror hostname) because `git-credentials` matches on the **rewritten** URL. The `insteadOf` rewrites `github.com` → `githubfast.com`, but git looks up credentials for the rewritten host. If push still prompts for credentials, try storing for both:

```bash
echo "https://USERNAME:PAT@githubfast.com" >> ~/.git-credentials
```

**Verify push works:**

```bash
cd /path/to/your/repo
git remote -v   # should show github.com URLs (rewritten transparently)
git push origin main 2>&1 | head -5
```

**Security:** After configuring, strip any embedded PAT from remote URLs:

```bash
# Don't leave tokens in remote URLs
git remote set-url origin https://github.com/owner/repo.git
```

The `~/.git-credentials` file handles authentication; the remote URL stays clean.

**Cleanup after use:** If the PAT was embedded in a remote URL during a session, always reset it:

```bash
git remote set-url origin https://github.com/owner/repo.git
```

## Pitfalls

- **Terminal CWD stuck on deleted directory** — If you `rm -rf` the current working directory while a persistent terminal session is using it, ALL subsequent terminal calls fail with `FileNotFoundError: [Errno 2] No such file or directory`. The `workdir` parameter won't help. Workaround: use `execute_code` (Python subprocess with explicit `cwd=`) instead of terminal until the session resets. Prevention: always `cd` to a stable directory (like `/root`) before deleting repos.
- **Mirrors come and go.** A mirror that worked today may be down tomorrow. If the configured mirror stops working, test alternatives and switch.
- **SSH protocol** (`git@github.com:user/repo.git`) is NOT affected by `insteadOf`. The mirror only works for `https://github.com/` URLs. If SSH clones fail, use HTTPS URLs instead.
- **ghproxy.net** sometimes returns HTTP/2 PROTOCOL_ERROR. Retry with `git -c http.version=HTTP/1.1 clone ...` as a workaround.
- **gitclone.com** returns 502, skip it.
- **Docker Hub mirrors** in China are unreliable. When `docker pull` fails despite mirror config, download the binary directly via `ghfast.top` and run it as a bare process or use `docker load` from a tar file.
- **`--depth=1`** (shallow clone) is recommended when you don't need full history — faster and less bandwidth.
- **nginx reverse proxy users**: This is NOT a Hermes auth issue. See the `hermes-agent` skill's "Web login / authentication issues" section instead.

## GitHub API: an alternative that often works even when mirrors don't

When you only need to **read** data (search repos, fetch metadata, browse trending), the GitHub REST API at `api.github.com` frequently works from China even when `github.com` web pages and git clones all time out. See `references/github-api-from-china.md` for search queries, Python examples, and rate-limit guidance.

## What a working mirror looks like

```
Cloning into '/tmp/test-mirror'...
remote: Enumerating objects: X, done.
remote: Counting objects: 100% (X/X), done.
remote: Compressing objects: 100% (X/X), done.
Receiving objects: 100% (X/X), X KiB | X KiB/s, done.
SUCCESS
```
