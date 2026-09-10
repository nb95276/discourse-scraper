# Discourse Forum Scraper & Exporter

针对 **Discourse** 架构论坛（尤其是配置了 Cloudflare 高度防护与严格频控机制的论坛，如 `linux.do`）的通用、高鲁棒性全楼层抓取与 Markdown/JSON 导出工具。

## 🌟 核心特性

- **原生 REST API**：直接获取结构化 JSON，告别脆弱的 DOM/HTML 解析。
- **Cloudflare TLS 指纹模拟**：基于 `curl_cffi` 模拟 Chrome 浏览器指纹，平稳穿越 Cloudflare 质询。
- **全楼层自动翻页**：支持获取长帖完整全部楼层（包含引用关系、点赞数、发表者及时间戳）。
- **智能防限流（Rack::Attack）**：支持请求延迟控制与 429 指数退避重试，防止被论坛临时封禁。
- **格式化导出**：一键生成适于大模型摘要提炼或 Obsidian 知识库存储的 Clean Markdown 和完整原始 JSON。

## 🚀 快速使用

### 1. 安装依赖

```bash
pip install curl_cffi beautifulsoup4
```

### 2. 准备 Cookie（针对高防护/需要登录的论坛）

1. 在浏览器（Chrome/Edge）安装扩展（如 *Get cookies.txt LOCALLY*）。
2. 打开论坛页面并登录。
3. 导出 Netscape 格式的 Cookie 文件，保存为 `cookies.txt`（参考 `scripts/cookies.example.txt`）。

### 3. 命令行运行

```bash
# 抓取单个话题（支持 URL 或数字 ID）
python scripts/discourse_scraper.py https://linux.do/t/topic/2882314 --cookie cookies.txt

# 批量抓取多个话题，导出到指定目录
python scripts/discourse_scraper.py 2882314 2874466 2871601 2873439 --cookie cookies.txt -o ./output

# 仅导出 Markdown 格式
python scripts/discourse_scraper.py 2882314 --cookie cookies.txt -f md
```

## 📋 架构说明

详见 [SKILL.md](./SKILL.md) 了解完整的 SOP 与底层机制分析。
