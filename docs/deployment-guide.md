# 部署指南

基于个人经验整理，不是标准教程。具体步骤请以 [Hermes Agent 官方文档](https://hermes.nousresearch.com/docs) 为准。

## 环境

- 阿里云 Linux（2 vCPU / 2GB RAM）
- Python 3.10+
- Nginx（反代用）

> 2G 内存是下限。Hermes 本身占 300-500MB，加上子代理和 MCP 工具会比较紧。**强烈建议加 2GB swap 作为缓冲**，详见 [踩坑记录](pitfalls.md)。

## 安装 Hermes Agent

```bash
pip install hermes-agent
hermes init
```

初始化后会在 `~/.hermes/` 下生成配置目录。编辑 `~/.hermes/config.yaml` 配置模型和 gateway。

## 配置模型

Hermes 支持任何 OpenAI 兼容的 API。在 `config.yaml` 的 `models` 部分配置：

```yaml
models:
  main:
    provider: deepseek          # 或 xiaomi 等
    model: deepseek-v4-pro      # 或 mimo-v2.5-pro 等
    api_key_env: DEEPSEEK_API_KEY  # 从环境变量读取
```

API Key 放在 `~/.hermes/.env` 中：

```bash
echo 'DEEPSEEK_API_KEY=sk-xxx' >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

MiMo 的接入方式见 [mimo-integration.md](mimo-integration.md)。

## 钉钉 Gateway

1. 在 [钉钉开放平台](https://open.dingtalk.com/) 创建企业内部应用
2. 消息接收模式选 **Stream 模式**（不需要公网回调）
3. 获取 AppKey 和 AppSecret
4. 配置到 Hermes：

```bash
hermes config set gateway.dingtalk.app_key "$DINGTALK_APP_KEY"
hermes config set gateway.dingtalk.app_secret "$DINGTALK_APP_SECRET"
```

## 微信 Gateway

微信接入基于 itchat-uos 协议，**有封号风险，建议用小号**。

```bash
pip install itchat-uos
hermes gateway start weixin
```

首次需要扫码登录。具体步骤参考 Hermes 官方文档的微信 gateway 章节。

## Token 监控面板

仓库里 `scripts/token_monitor.py` 是一个简单的 Token 用量监控 Web 面板。

```bash
# 启动（默认监听 127.0.0.1:8765）
python3 scripts/token_monitor.py

# 用 Nginx 反代
# location /token/ {
#     proxy_pass http://127.0.0.1:8765/;
# }
```

## systemd 服务

建议把 Hermes 和监控面板都配成 systemd 服务：

```bash
# Hermes Gateway 示例
cat > /etc/systemd/system/hermes-gateway.service << 'EOF'
[Unit]
Description=Hermes Agent Gateway
After=network.target

[Service]
Type=simple
User=hermes
EnvironmentFile=/home/hermes/.hermes/.env
ExecStart=/usr/local/bin/hermes gateway serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable hermes-gateway
systemctl start hermes-gateway
```

## 常见问题

**Q: 子代理任务很慢？**
2C2G 机器跑并行子代理会受限。建议升级内存或减少并发数。

**Q: 微信掉线？**
itchat-uos 协议不稳定，可能需要定期重新扫码。目前没有好的解决方案。

**Q: GitHub 访问慢？**
国内服务器普遍有这个问题。可以配置 git 代理或使用镜像。Hermes Agent 的 pip 安装一般没问题。

**Q: 模型 API 超时？**
检查网络连通性，尝试调大 config.yaml 中的 timeout 参数。
