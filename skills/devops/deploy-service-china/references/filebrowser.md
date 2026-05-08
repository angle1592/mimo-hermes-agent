# FileBrowser Deployment

Lightweight Go-based file server. Single binary, ~30MB, minimal memory (~9MB).

## Install

```bash
# Download via GitHub proxy (China)
PROXY="https://ghfast.top/"
URL="https://github.com/filebrowser/filebrowser/releases/download/v2.63.2/linux-amd64-filebrowser.tar.gz"
curl -L --connect-timeout 15 --max-time 180 -o /tmp/filebrowser.tar.gz "${PROXY}${URL}"

# Extract and install
cd /tmp && tar xzf filebrowser.tar.gz && chmod +x filebrowser
mv filebrowser /usr/local/bin/filebrowser
filebrowser version
```

## Config

```bash
mkdir -p /srv/filebrowser/{db,shared}

cat > /srv/filebrowser/.filebrowser.json << 'EOF'
{
  "port": 8080,
  "address": "127.0.0.1",
  "database": "/srv/filebrowser/db/filebrowser.db",
  "root": "/srv/filebrowser/shared",
  "log": "/srv/filebrowser/filebrowser.log",
  "baseurl": "/files"
}
EOF
```

## Pitfalls

1. **Password minimum 12 characters** — FileBrowser v2.63+ requires `--password` ≥ 12 chars. Default `admin`/`admin` won't work for password changes.

2. **Database locked** — Can't run CLI commands while service is running. Stop first:
   ```bash
   systemctl stop filebrowser
   filebrowser -d /srv/filebrowser/db/filebrowser.db users update admin --password "your-12char-pw"
   systemctl start filebrowser
   ```

3. **Locale change** — Set Chinese UI:
   ```bash
   systemctl stop filebrowser
   filebrowser -d /srv/filebrowser/db/filebrowser.db users update admin --locale zh-cn
   systemctl start filebrowser
   ```

4. **Subpath proxy** — Must set `baseurl` in config to match nginx location path. Without it, static assets load from wrong path and UI shows blank.

5. **Address binding** — Set `"address": "127.0.0.1"` when behind nginx. Don't expose port directly.

## File Delivery (User Preference)

FileBrowser is the designated file sharing method for this server. When the agent needs to deliver a file to the user:
1. Copy to `/srv/filebrowser/shared/` (organize into subdirectories by topic)
2. Give user the link: `http://YOUR_SERVER_IP/files/<path>`
3. Do NOT spin up temporary HTTP servers or other ad-hoc file sharing
4. Clean up stale/unused files from the shared directory

WeChat `MEDIA:` is the alternative for direct file sending.

## Nginx Config

```nginx
location /files/ {
    auth_basic off;
    proxy_pass http://127.0.0.1:8080/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 500m;
}
```
