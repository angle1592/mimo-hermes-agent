# 踩坑记录

实际使用中遇到的问题和解决方案，持续更新。

## 内存不足

**症状：** 子代理任务卡住，或系统 OOM Kill Hermes 进程。

**原因：** 2G 内存跑 Hermes（~400MB）+ 子代理 + MCP 工具 + Nginx，很紧张。

**解决：**
- 减少并行子代理数：`hermes config set delegation.max_concurrent_children 2`
- 关掉不需要的 MCP 服务器
- 加 swap：`fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`
- 长期方案：升级到 4G 内存

## 微信掉线

**症状：** itchat-uos 登录后几小时或几天就掉线，需要重新扫码。

**原因：** 微信网页版协议本身就不稳定，官方也不鼓励使用。

**解决：**
- 用小号，不要用主号
- 配置 systemd 自动重启：`Restart=always`
- 掉线后日志会打印新的二维码，用 `journalctl -u hermes-wechat -f` 查看
- 没有完美解决方案，这是协议层面的限制

## GitHub 访问慢/超时

**症状：** `pip install`、`git clone`、下载 release 文件超时。

**解决：**
- pip 用国内镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple hermes-agent`
- git 配代理（如果有）：`git config --global http.proxy http://proxy:port`
- 下载 GitHub release 用代理：`curl -L https://ghfast.top/https://github.com/.../file.tar.gz`
- npm 用淘宝镜像：`npm config set registry https://registry.npmmirror.com`

## Docker Hub 拉不到镜像

**症状：** `docker pull` 超时。

**解决：**
- 配置镜像加速器（编辑 `/etc/docker/daemon.json`）：
  ```json
  {
    "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
  }
  ```
  注意：腾讯云镜像对阿里云服务器可能不可用，需要找其他可用的镜像。
- 或者不用 Docker，直接下载二进制文件安装（比如 FileBrowser）。

## 钉钉消息收不到

**症状：** 配置了钉钉 Gateway 但消息没有响应。

**检查：**
- 确认用的是 Stream 模式（不是 Webhook）
- 确认 AppKey 和 AppSecret 正确
- 确认机器人已发布（不是草稿状态）
- 看日志：`journalctl -u hermes-dingtalk -f`
- 确认钉钉应用的权限已申请并通过审批

## Token 消耗比预期高

**症状：** 一天用了几千万 token。

**原因：** Agent 会话的上下文很长（包含工具调用、历史记忆等），每次交互都会发送完整上下文。

**解决：**
- 开启上下文压缩：`compression.enabled: true`
- 减少 `memory.memory_char_limit` 和 `memory.user_char_limit`
- 子代理用便宜模型（DeepSeek Flash）
- 利用缓存：缓存命中率高时成本大幅降低

## Alinux 4 / RHEL 9 上 Docker CE 装不上

**症状：** `yum install docker-ce` 报 404。

**原因：** Docker CE 的 yum repo 默认用 `$releasever`，Alinux 4 识别不到。

**解决：**
```bash
yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
sed -i 's|\$releasever|9|g' /etc/yum.repos.d/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io
```

## Hermes 大版本更新导致服务器卡死

**症状：** SSH 连不上，磁盘持续大量读写，系统无响应，只能强制重启。

**原因：** 2C2G 机器没有 swap，Hermes 更新时拉取大量 commit（100+），pip 和 npm 同时下载解压依赖包，内存和磁盘 I/O 被打满，系统卡死。

**解决：**
- **加 swap**（推荐 2GB）：
  ```bash
  fallocate -l 2G /swapfile && chmod 600 /swapfile
  mkswap /swapfile && swapon /swapfile
  echo '/swapfile swap swap defaults 0 0' >> /etc/fstab
  
  # 降低 swappiness，平时尽量不用，只在内存紧张时用
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf
  sysctl -p /etc/sysctl.d/99-swap.conf
  ```
- 大版本更新建议在能监控的时候手动操作，不要在凌晨自动跑
- 更新前确认 swap 已启用

**教训：** 低配机器不加 swap 就跑自动更新，等于给自己埋雷。

## Hermes 更新后自定义修改丢失

**症状：** `pip install --upgrade hermes-agent` 后之前的源码修改没了。

**解决：** 更新前用 patch 保存修改，更新后恢复。详见 Hermes 官方文档的"源码修改管理"章节。简单场景不需要改源码，用 skill 和 config 就够了。
