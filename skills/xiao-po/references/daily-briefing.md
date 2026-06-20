# 每日早报 (Daily Morning Briefing) 工作流

## 概述
主人设置了每日早报 cron job，约北京时间 05:30 自动触发。无用户在线，全程自主执行，最终回复自动推送。

## 执行流程

### 1. 搜索新闻
按优先级搜索 AI/技术新闻：

**搜索源优先级**：
1. DuckDuckGo (`ddgs news -k '...' -m 10`) — 国际新闻首选
2. **HN Firebase API** (`hacker-news.firebaseio.com`) — 技术社区热点（网页版超时，但 API 可用）
3. GitHub Trending (`github.com/trending`) — 开源项目（必须带 User-Agent）
4. 36氪 AI 频道 (`36kr.com/information/AI`) — 中文 AI 资讯
5. 36氪快讯 (`36kr.com/newsflashes`) — 中文科技快讯

### 2. ⚠️ 中国大陆网络注意事项
此服务器在阿里云中国大陆节点，**国际站经常超时**：

| 源 | 可用性 | 备注 |
|---|---|---|
| DuckDuckGo | ❌ 经常超时 | DNS/连接问题 |
| Hacker News *网页* | ❌ 经常超时 | 国际站连接慢 |
| **HN Firebase API** | ✅ **可靠** | `hacker-news.firebaseio.com` 1-2秒响应 |
| GitHub Trending | ⚠️ 需要 User-Agent | 不带 UA 会返回登录页 |
| Baidu | ⚠️ 有验证码 | 搜索结果页触发安全验证 |
| **36kr.com** | ✅ **可靠** | 国内站，始终可用 |

**HN Firebase API 用法**（2026-06-20 验证可用）：
```bash
# 获取热门故事 ID 列表
curl -sL --max-time 20 'https://hacker-news.firebaseio.com/v0/topstories.json'

# 获取单个故事详情
curl -sL --max-time 8 'https://hacker-news.firebaseio.com/v0/item/{id}.json'
# 返回: {"title":"...","url":"...","score":123,"descendants":45}
```

**Fallback 策略**：DDG（1次尝试，超时则跳过）→ HN Firebase API → GitHub Trending → 36kr.com → "今天网络不太好"

### 3. 内容筛选
从搜索结果中挑选 **最多 3 条**，按以下优先级：
1. AI/技术新闻（新模型、重大更新、开源项目）
2. 科技圈热点
3. 轻松有趣的内容（兜底）

### 4. 输出格式
```
☀️ **主人早安！X月X日早报来啦～**

**1️⃣ [标题]**
一两句话说明是什么、为什么值得看。
🔗 链接

**2️⃣ [标题]**
...
🔗 链接

**3️⃣ [标题]**
...
🔗 链接
```

**格式规则**：
- 开头用 ☀️ + 日期问候
- 每条用 emoji 数字编号 (1️⃣2️⃣3️⃣)
- 标题加粗
- 一两句话说清楚，不要太长
- 附链接
- 语气轻松自然，符合小珀人设
- 如果确实没新闻，简单说一句"今天比较平静"，不硬凑
- 末尾可以加一句小珀风格的补充

### 5. 禁止事项
- ❌ 不要编造新闻内容
- ❌ 不要超过 3 条
- ❌ 不要太正式/太长
- ❌ 不要用 send_message（cron job 自动推送）
- ❌ 搜索不到就说没有，不要虚构
