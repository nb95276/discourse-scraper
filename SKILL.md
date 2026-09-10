---
name: discourse-scraper
description: 通用 Discourse 论坛（如 linux.do）高鲁棒性抓取、全楼层解析与 Markdown 导出 SOP。利用 Discourse 原生 REST API、curl_cffi 浏览器 TLS 指纹模拟、Netscape Cookie 复用与指数退避限速策略，完美绕过 Cloudflare 盾与 429 限流。当用户提到“抓取Discourse”、“爬取linux.do”、“Discourse论坛爬虫”、“提取论坛帖子”、“discourse scraper”或需要对 Discourse 论坛长帖做全楼层归档与总结时使用。
---

# Discourse 论坛高鲁棒性抓取与归档 SOP

本 SOP 沉淀自对 **Discourse** 架构论坛（尤其是配置了 Cloudflare 高度防护与 Rack::Attack 频率限制的知名站点，如 `linux.do`）的大规模深度实战抓取。

---

## 1. 核心认知与架构原理

### 1.1 放弃 DOM 解析，直奔原生 REST API
Discourse 是一个前后端分离的 SPA（单页应用）。任何网页链接（如 `https://linux.do/t/topic/12345`）在 URL 末尾加上 `.json` 即可直接获取完整的结构化数据：
```text
https://linux.do/t/topic/{topic_id}.json
```
- **无需用 BeautifulSoup 扣 HTML DOM**，DOM 会因前端版本更新、动态虚拟滚动渲染而极不稳定。
- 原生 JSON 中提供了字段齐全的元数据：标题、分类、标签、阅读量、每个楼层发表者、发帖时间、点赞数、引用回复关系（`reply_to_post_number`），以及经过服务端渲染的富文本内容（`cooked`）。

### 1.2 全楼层分页的三种机制
Discourse 默认首包通常只返回前 20 楼。要获取长帖的全部内容：
1. **页面分页（推荐，最稳定通用）**：
   `GET /t/topic/{topic_id}.json?page=2`、`page=3`... 每页 20 楼，直到返回的 `posts` 列表为空。
2. **精准 Post ID 块抓取（Discourse 前端机制）**：
   首次请求返回的 `post_stream.stream` 是该话题全部回帖 ID 的整型数组。可按 50 个一组拆分后请求：
   `GET /t/{topic_id}/posts.json?post_ids[]=101&post_ids[]=102...`
   *注：高防护站点该接口可能校验特有的 session 或 CSRF 头。*
3. **楼层游标机制**：
   `GET /t/{topic_id}/{post_number}.json`（从某个楼层编号向后加载）。

---

## 2. 高防护对抗三大要点（以 linux.do 为例）

### 2.1 绕过 Cloudflare TLS 指纹检测（JA3 / HTTP2）
- **现象**：普通 Python `requests`、`urllib` 或常规命令行 `curl` 会立刻遭遇 `403 Forbidden` 或 `Just a moment...` 质询页面。
- **方案**：使用 **`curl_cffi`**（底层基于 cURL-impersonate），在发起请求时指定 `impersonate="chrome124"` 或 `"chrome131"`，完美模拟原生 Chrome 浏览器的 TLS 握手特征。

### 2.2 身份认证与 Cookie 复用
- **现象**：很多私密版块要求登录，且通过 Cloudflare 盾必须具备凭证。
- **方案**：使用浏览器插件（如 *Get cookies.txt LOCALLY*）导出标准 Netscape 格式的 Cookie 文件。
- **核心凭证**：
  - `cf_clearance`：Cloudflare 盾通行令牌。
  - `_t`：Discourse 的核心用户认证 Token。
  - `_forum_session`：论坛会话状态。

### 2.3 频率控制与规避 429（Rack::Attack 机制）
- **现象**：Discourse 针对高频请求有基于 Redis 的 `Rack::Attack` 拦截。并发 3~4 个请求就会直接触发 `429 Too Many Requests`，将 IP 关入 30~60 秒小黑屋。
- **硬性规则**：
  - **绝不使用无脑并发/多线程**，所有话题与翻页必须**串行**进行。
  - 每次请求间隔建议保持在 **1.0 ~ 2.0 秒**。
  - 一旦捕获到 `429` 状态码，必须实施**指数退避**（等待 10s、20s、30s 后重试），绝不可强行重发。

---

## 3. 开箱即用 CLI 工具

技能内置了完整的生产级脚本 `scripts/discourse_scraper.py`。

### 3.1 常用命令示例

```bash
# 1. 抓取单个话题，保存为 Markdown 与 JSON
python scripts/discourse_scraper.py https://linux.do/t/topic/2882314 --cookie cookies.txt

# 2. 批量抓取多个话题，指定输出目录
python scripts/discourse_scraper.py 2882314 2874466 2871601 --cookie cookies.txt --output ./data

# 3. 指定抓取延迟（单位：秒）和输出格式
python scripts/discourse_scraper.py 2873439 --cookie cookies.txt --delay 1.5 --format md
```

### 3.2 脚本核心参数
| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `topics` | 话题 ID 或完整的 Discourse 帖子 URL（支持多个） | 必填 |
| `--cookie`, `-c` | 包含 `cf_clearance` 和 `_t` 的 Netscape cookie 文本路径 | 可选（公开帖可不带，强防帖必带） |
| `--output`, `-o` | 输出目录 | 当前目录下的 `output` |
| `--format`, `-f` | 导出格式：`md`、`json`、`both` | `both` |
| `--delay`, `-d` | 请求间隔延迟（秒），防止 429 限流 | `1.0` |

---

## 4. 输出格式与内容规范

导出的 Markdown 文件已对 `cooked` HTML 进行富文本剥离，保留核心结构：
```markdown
# [帖子标题]

- **链接**: https://linux.do/t/topic/2882314
- **总楼层数**: 24
- **发布时间**: 2026-09-10T01:03:38.360Z

---

### 第 1 楼: 昵称 (@用户名) | 赞数: 0 | 时间: ...
[楼主正文内容]

---

### 第 2 楼: 昵称 (@用户名) (回复 #1 楼) | 赞数: 3 | 时间: ...
[回帖内容]
```
方便直接投喂给 LLM 制作摘要、提炼观点或归档至个人知识库（Obsidian/Notion）。
