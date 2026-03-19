# Scripts to Audiobook

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README.md)
[![中文](https://img.shields.io/badge/lang-中文-red.svg)](README.zh.md)

将格式化剧本转换为多角色有声书，支持 **多种 TTS 提供商** —— 包括 Microsoft Edge TTS、ElevenLabs、科大讯飞和百度语音。

> 🌐 **语言**: [English](README.md) | [中文](README.zh.md)

![Dark Mode UI](docs/screenshot-dark.jpg)

## 功能特性

- **多角色合成** —— 每个角色自动分配独特的声音，按语言、口音、性别和年龄匹配
- **多 TTS 提供商支持** —— 支持 Edge TTS（免费）、ElevenLabs、科大讯飞、百度语音
- **声音匹配引擎** —— 加权评分（语言、口音、性别、年龄、旁白/对话适配度、多样性惩罚）并显示评分说明
- **61 声音优先目录** —— 为所有英语和中文 Edge TTS 声音提供丰富元数据
- **双语界面** —— 一键切换中文/英文界面（zh/en）
- **角色声音卡片** —— 预览、锁定、覆盖语速/音调、选择备选声音
- **同步播放** —— 当前行高亮、点击跳转、角色过滤、时间线可视化
- **示例/演示模式** —— 即时加载英文或中文示例剧本
- **库管理** —— 基于专辑的组织方式，数据库持久化存储
- **设置管理** —— Web UI 配置 TTS 提供商凭证和存储路径
- **输出** —— 合并的 MP3 有声书 + SRT 字幕 + 结构化时间线 JSON

## 架构

```
scripts-to-audiobook-app/
├── backend/          # Python FastAPI 后端（多提供商 TTS 合成）
│   ├── main.py       # API 服务器 + 声音匹配引擎
│   ├── database.py   # SQLite 数据库用于库管理
│   ├── config.py     # 配置管理
│   └── tts_providers/# TTS 提供商实现
│       ├── edge.py      # Microsoft Edge TTS（免费）
│       ├── elevenlabs.py# ElevenLabs API
│       ├── iflytek.py   # 科大讯飞
│       └── baidu.py     # 百度语音
├── catalog/          # 丰富的声音目录文件（JSON）
│   ├── voices_all.json
│   ├── voices_english.json
│   ├── voices_chinese.json
│   ├── voices_priority.json
│   ├── voices_edge.json
│   ├── voices_elevenlabs.json
│   ├── voices_iflytek.json
│   ├── voices_baidu.json
│   └── catalog_stats.json
├── frontend/         # React + Vite + Tailwind + shadcn/ui
│   ├── client/src/
│   │   ├── pages/    # ScriptInput, VoiceCast, Generate, Playback, Catalog, Library, Settings
│   │   ├── components/ # Layout, VoiceCard, ErrorBoundary
│   │   └── lib/      # api.ts, i18n.ts, sampleData.ts
│   ├── server/       # Express 服务器（TypeScript）
│   └── shared/       # 共享模式定义
├── data/             # 生成的有声书文件和数据库
│   ├── outputs/      # 生成的有声书文件
│   └── library.db    # SQLite 数据库
├── logs/             # 应用程序日志
├── samples/          # 示例剧本和声音描述
├── start.sh          # 一键启动脚本
├── stop.sh           # 停止所有服务
└── Dockerfile        # Docker 部署
```

## 快速开始

### 1. 环境要求

- **Python 3.11+**
- **Node.js 18+**
- **ffmpeg**（用于音频合并）

### 2. 一键启动（推荐）

```bash
cd scripts-to-audiobook-app
./start.sh
```

这将：
- 检查并安装依赖
- 在端口 8000 启动后端
- 在端口 5000（或下一个可用端口）启动前端

然后打开：**http://localhost:5000**

### 3. 手动启动

#### 安装 Python 依赖

```bash
pip install edge-tts fastapi uvicorn pydub python-dotenv aiosqlite websocket-client
```

#### 安装 Node.js 依赖

```bash
cd frontend
npm install
```

#### 配置环境变量（可选）

在项目根目录创建 `.env` 文件用于 TTS 提供商凭证：

```bash
cp .env.example .env
```

编辑 `.env` 填入你的凭证：

```
# 科大讯飞 - 可选
IFLYTEK_APP_ID=
IFLYTEK_API_KEY=
IFLYTEK_API_SECRET=

# 百度语音 - 可选
BAIDU_APP_ID=
BAIDU_API_KEY=
BAIDU_API_SECRET=

# ElevenLabs - 可选
ELEVENLABS_API_KEY=

# 应用程序设置
STORAGE_PATH=/path/to/audiobooks
```

你也可以在 **设置** 页面通过 Web UI 配置这些选项。

#### 启动后端（端口 8000）

```bash
python3 backend/main.py
```

#### 启动前端（端口 5000）

```bash
cd frontend
npm run dev
```

### 4. 停止服务

```bash
./stop.sh
```

## Docker 部署

### 环境要求

- **Docker Engine** 20.10+
- **Docker Compose** 2.0+
- 端口 **5000** 和 **8000** 未被占用

### 使用 Docker Compose 快速开始

1. **创建 `.env` 文件**（必需）：

```bash
cp .env.example .env
```

编辑 `.env` 填入 TTS 提供商凭证（可选，仅在使用第三方 TTS 时需要）：

```
# 科大讯飞 - 可选
IFLYTEK_APP_ID=your_app_id
IFLYTEK_API_KEY=your_api_key
IFLYTEK_API_SECRET=your_api_secret

# 百度语音 - 可选
BAIDU_APP_ID=your_app_id
BAIDU_API_KEY=your_api_key
BAIDU_API_SECRET=your_api_secret

# ElevenLabs - 可选
ELEVENLABS_API_KEY=your_api_key

# 应用程序设置
STORAGE_PATH=/app/data/outputs
```

2. **启动服务**：

```bash
docker-compose up -d
```

3. **访问应用**：

- 前端：**http://localhost:5000**
- 后端 API：**http://localhost:8000**

4. **停止服务**：

```bash
docker-compose down
```

### 手动 Docker 构建

如果你不想使用 Docker Compose：

```bash
# 构建镜像
docker build -t scripts-to-audiobook .

# 运行容器（必须挂载 .env 文件）
docker run -d \
  -p 5000:5000 \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.env:/app/.env:ro \
  --name scripts-to-audiobook \
  scripts-to-audiobook

# 停止容器
docker stop scripts-to-audiobook
```

### 查看日志

```bash
# 查看所有日志
docker-compose logs -f

# 仅查看后端日志
docker-compose logs -f audiobook-app
```

## 剧本格式

应用接受以下格式的剧本（支持 `:` 和 `：`）：

```
Narrator: Once upon a time, in a distant land...
Alice: I've been waiting for this moment my entire life.
Bob: Don't get sentimental. We have a job to do.
```

**中文格式：**
```
旁白：从前有座山，山上有座庙...
小明：我等待这一刻已经等了一辈子。
小红：别感情用事，我们有任务要完成。
```

## 声音描述（可选）

你可以为每个角色提供可选的声音描述：

```
Narrator: English, American, female, adult
Alice: English, American, female, adult
Bob: English, British, male, senior
```

支持中英文描述：
```
旁白：中文，普通话，女性，成年
小明：中文，普通话，男性，成年
小红：中文，台湾，女性，成年
```

## 声音目录

丰富的目录位于 `catalog/voices_priority.json`，包含：

- **47 个英语声音**，涵盖 14 种地区变体（en-US、en-GB、en-AU、en-CA、en-IN、en-IE、en-NZ、en-SG、en-ZA、en-HK、en-KE、en-NG、en-PH、en-TZ）
- **14 个中文声音**，涵盖 5 种地区变体（zh-CN、zh-CN-liaoning、zh-CN-shaanxi、zh-HK、zh-TW）

每个声音条目包含：
- `voice_id`、`locale`、`base_language`、`accent_label`、`gender`
- `age_bucket`（child/adult/senior）、`age_confidence`
- `narrator_fit_score`（0-1）、`dialogue_fit_score`（0-1）
- `personalities`、`content_categories`、`recommended_tags`

从原始数据重新生成目录：
```bash
python3 catalog/build_catalog.py
```

## API 参考

后端运行在端口 8000：

| 端点 | 方法 | 描述 |
|---|---|---|
| `/api/health` | GET | 健康检查 |
| `/api/voices` | GET | 所有声音（按 `lang`、`gender`、`locale` 过滤） |
| `/api/voices/priority` | GET | 英语 + 中文优先声音 |
| `/api/voices/match` | POST | 匹配声音描述 → 最佳候选 |
| `/api/script/parse` | POST | 解析剧本 + 自动分配声音 |
| `/api/generate` | POST | 开始有声书生成任务 |
| `/api/jobs/{id}` | GET | 轮询生成任务状态 |
| `/api/preview` | POST | 生成短声音预览 |
| `/api/audio/{project_id}/{file}` | GET | 提供生成的文件 |
| `/api/catalog/stats` | GET | 目录统计 |
| `/api/library/settings` | GET | 获取所有库设置 |
| `/api/library/settings/{key}` | GET/PUT | 获取/更新特定设置 |
| `/api/tts-providers` | GET | 获取所有 TTS 提供商 |
| `/api/albums` | GET/POST | 列出/创建专辑 |
| `/api/albums/{id}` | GET/PUT/DELETE | 获取/更新/删除专辑 |
| `/api/audio-files` | GET/POST | 列出/创建音频文件 |
| `/api/audio-files/{id}` | GET/PUT/DELETE | 获取/更新/删除音频文件 |

## TTS 提供商

> 🎉 **开箱即用！** Clone 后直接运行 —— 无需任何 API 密钥。Edge TTS 自带 61+ 声音，立即可用。

### Edge TTS（默认，免费）✅

![开箱即用](https://img.shields.io/badge/status-开箱即用-brightgreen)

- **无需 API 密钥** —— Clone 后立即可用
- **61+ 声音** 支持英语和中文
- **在线服务**（需要互联网）
- **永久免费**

---

### ElevenLabs（可选）

![需要 API 密钥](https://img.shields.io/badge/status-需要_API_密钥-yellow)

- 高质量神经声音
- 最适合英文内容

**配置指南：**

1. **注册账号**：访问 [elevenlabs.io](https://elevenlabs.io/app/sign-up)
2. **获取 API Key**：控制台 → [API Keys](https://elevenlabs.io/app/settings/api-keys) → 创建 API Key
3. **配置**：添加到 `.env`：
   ```
   ELEVENLABS_API_KEY=your_api_key_here
   ```

**价格**：提供免费额度（每月 10,000 字符）

---

### 科大讯飞（可选）

![需要 API 密钥](https://img.shields.io/badge/status-需要_API_密钥-yellow)

- 中文语音合成
- 多种中文口音和方言

**配置指南：**

1. **注册账号**：访问 [讯飞开放平台](https://www.xfyun.cn/) → 注册
2. **创建应用**：控制台 → [创建应用](https://console.xfyun.cn/app/create)
3. **开通服务**：在应用中添加"在线语音合成"服务
4. **获取凭证**：应用详情页 → 复制 `APPID`、`API Key`、`API Secret`
5. **配置**：添加到 `.env`：
   ```
   IFLYTEK_APP_ID=your_app_id
   IFLYTEK_API_KEY=your_api_key
   IFLYTEK_API_SECRET=your_api_secret
   ```

**价格**：提供免费额度（新用户每日 50,000 字符）

**文档**：[科大讯飞语音合成文档](https://www.xfyun.cn/doc/tts/online_tts/API.html)

---

### 百度语音（可选）

![需要 API 密钥](https://img.shields.io/badge/status-需要_API_密钥-yellow)

- 中文语音合成
- 多种声音风格

**配置指南：**

1. **注册账号**：访问 [百度智能云](https://cloud.baidu.com/) → 注册
2. **创建应用**：[AI 控制台](https://console.bce.baidu.com/ai/#/ai/speech/app/create) → 创建应用
3. **开通服务**：选择"短语音合成"服务
4. **获取凭证**：应用详情页 → 复制 `AppID`、`API Key`、`Secret Key`
5. **配置**：添加到 `.env`：
   ```
   BAIDU_APP_ID=your_app_id
   BAIDU_API_KEY=your_api_key
   BAIDU_API_SECRET=your_api_secret
   ```

**价格**：提供免费额度（每日 50,000 次调用）

**文档**：[百度语音合成文档](https://cloud.baidu.com/doc/SPEECH/s/Nk38y8pbm)

## 已知限制

- **Edge TTS 需要互联网** —— 合成调用 Microsoft 的 Edge TTS 服务器
- **年龄桶推断** —— 年龄元数据是启发式推断的；Edge TTS 不公开显式年龄标签
- **音频合并** —— 需要本地安装 `ffmpeg`
- **并发任务** —— 任务顺序运行；高容量使用无队列管理
- **预览声音** —— 预览需要互联网按需调用 TTS 提供商

## 安全提示

⚠️ **在推送到 GitHub 之前：**

1. **确保 `.env` 文件已被忽略**（已包含在 `.gitignore` 中）
2. **不要提交真实凭证** —— 使用 `.env.example` 作为模板
3. **检查没有敏感数据被意外提交**：
   ```bash
   git status
   git diff --cached
   ```
4. **清理历史记录**（如果之前已提交敏感数据）：
   ```bash
   git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch .env' HEAD
   ```

## 许可证

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

---

*Created with 💙 by Nicky & AI*
