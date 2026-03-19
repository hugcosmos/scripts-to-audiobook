# Scripts to Audiobook

[![English](https://img.shields.io/badge/lang-English-blue.svg)](README.md)
[![中文](https://img.shields.io/badge/lang-中文-red.svg)](README.zh.md)

Convert formatted scripts into multi-character audiobooks using **multiple TTS providers** — including Microsoft Edge TTS, ElevenLabs, iFlytek (科大讯飞), and Baidu (百度语音).

> 🌐 **Languages**: [English](README.md) | [中文](README.zh.md)

![Dark Mode UI](docs/screenshot-dark.jpg)

## Features

- **Multi-character synthesis** — Each character gets a unique voice automatically matched by language, accent, gender, and age
- **Multiple TTS Providers** — Support for Edge TTS (free), ElevenLabs, iFlytek, and Baidu
- **Voice Matching Engine** — Weighted scoring (language, accent, gender, age, narrator/dialogue suitability, diversity penalty) with score explanations
- **61-voice Priority Catalog** — Enriched metadata for all English and Chinese Edge TTS voices
- **Bilingual UI** — One-click Chinese/English interface switch (zh/en)
- **Character Voice Cards** — Preview, lock, override rate/pitch, pick alternatives
- **Synchronized Playback** — Active line highlighting, click-to-seek, character filter, timeline visualization
- **Sample/Demo Mode** — Load English or Chinese sample scripts instantly
- **Library Management** — Album-based organization with database persistence
- **Settings Management** — Web UI for configuring TTS provider credentials and storage paths
- **Outputs** — Merged MP3 audiobook + SRT subtitles + structured timeline JSON

## Architecture

```
scripts-to-audiobook-app/
├── backend/          # Python FastAPI backend (multi-provider TTS synthesis)
│   ├── main.py       # API server + voice matching engine
│   ├── database.py   # SQLite database for library management
│   ├── config.py     # Configuration management
│   └── tts_providers/# TTS provider implementations
│       ├── edge.py      # Microsoft Edge TTS (free)
│       ├── elevenlabs.py# ElevenLabs API
│       ├── iflytek.py   # iFlytek (科大讯飞)
│       └── baidu.py     # Baidu Speech (百度语音)
├── catalog/          # Enriched voice catalog files (JSON)
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
│   ├── server/       # Express server with TypeScript
│   └── shared/       # Shared schema definitions
├── data/             # Generated audiobook files and database
│   ├── outputs/      # Generated audiobook files
│   └── library.db    # SQLite database
├── logs/             # Application logs
├── samples/          # Sample scripts and voice descriptions
├── start.sh          # One-click startup script
├── stop.sh           # Stop all services
└── Dockerfile        # Docker deployment
```

## Quick Start

### 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **ffmpeg** (for audio merging)

### 2. One-Click Start (Recommended)

```bash
cd scripts-to-audiobook-app
./start.sh
```

This will:
- Check and install dependencies
- Start backend on port 8000
- Start frontend on port 5000 (or next available)

Then open: **http://localhost:5000**

### 3. Manual Start

#### Install Python dependencies

```bash
pip install edge-tts fastapi uvicorn pydub python-dotenv aiosqlite websocket-client
```

#### Install Node.js dependencies

```bash
cd frontend
npm install
```

#### Configure Environment Variables (Optional)

Create a `.env` file in the project root for TTS provider credentials:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
# iFlytek (科大讯飞) - Optional
IFLYTEK_APP_ID=
IFLYTEK_API_KEY=
IFLYTEK_API_SECRET=

# Baidu (百度语音) - Optional
BAIDU_APP_ID=
BAIDU_API_KEY=
BAIDU_API_SECRET=

# ElevenLabs - Optional
ELEVENLABS_API_KEY=

# Application Settings
STORAGE_PATH=/path/to/audiobooks
```

You can also configure these in the web UI at **Settings** page.

#### Start Backend (Port 8000)

```bash
python3 backend/main.py
```

#### Start Frontend (Port 5000)

```bash
cd frontend
npm run dev
```

### 4. Stop Services

```bash
./stop.sh
```

## Docker Deployment

### Prerequisites

- **Docker Engine** 20.10+
- **Docker Compose** 2.0+
- 端口 **5000** 和 **8000** 未被占用

### Quick Start with Docker Compose

1. **Create `.env` file** (required):

```bash
cp .env.example .env
```

Edit `.env` with your TTS provider credentials (optional, only if using third-party TTS):

```
# iFlytek (科大讯飞) - Optional
IFLYTEK_APP_ID=your_app_id
IFLYTEK_API_KEY=your_api_key
IFLYTEK_API_SECRET=your_api_secret

# Baidu (百度语音) - Optional
BAIDU_APP_ID=your_app_id
BAIDU_API_KEY=your_api_key
BAIDU_API_SECRET=your_api_secret

# ElevenLabs - Optional
ELEVENLABS_API_KEY=your_api_key

# Application Settings
STORAGE_PATH=/app/data/outputs
```

2. **Start services**:

```bash
docker-compose up -d
```

3. **Access the app**:

- Frontend: **http://localhost:5000**
- Backend API: **http://localhost:8000**

4. **Stop services**:

```bash
docker-compose down
```

### Manual Docker Build

If you prefer to run without Docker Compose:

```bash
# Build image
docker build -t scripts-to-audiobook .

# Run container (must mount .env file)
docker run -d \
  -p 5000:5000 \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.env:/app/.env:ro \
  --name scripts-to-audiobook \
  scripts-to-audiobook

# Stop container
docker stop scripts-to-audiobook
```

### View Logs

```bash
# View all logs
docker-compose logs -f

# View backend logs only
docker-compose logs -f audiobook-app
```

## Script Format

The app accepts scripts in this format (supports both `:` and `：`):

```
Narrator: Once upon a time, in a distant land...
Alice: I've been waiting for this moment my entire life.
Bob: Don't get sentimental. We have a job to do.
```

**Chinese format:**
```
旁白：从前有座山，山上有座庙...
小明：我等待这一刻已经等了一辈子。
小红：别感情用事，我们有任务要完成。
```

## Voice Descriptions (optional)

You can optionally provide voice descriptions for each character:

```
Narrator: English, American, female, adult
Alice: English, American, female, adult
Bob: English, British, male, senior
```

Supports both English and Chinese descriptions:
```
旁白：中文，普通话，女性，成年
小明：中文，普通话，男性，成年
小红：中文，台湾，女性，成年
```

## Voice Catalog

The enriched catalog at `catalog/voices_priority.json` covers:

- **47 English voices** across 14 locale variants (en-US, en-GB, en-AU, en-CA, en-IN, en-IE, en-NZ, en-SG, en-ZA, en-HK, en-KE, en-NG, en-PH, en-TZ)
- **14 Chinese voices** across 5 locale variants (zh-CN, zh-CN-liaoning, zh-CN-shaanxi, zh-HK, zh-TW)

Each voice entry includes:
- `voice_id`, `locale`, `base_language`, `accent_label`, `gender`
- `age_bucket` (child/adult/senior), `age_confidence`
- `narrator_fit_score` (0-1), `dialogue_fit_score` (0-1)
- `personalities`, `content_categories`, `recommended_tags`

Regenerate the catalog from raw data:
```bash
python3 catalog/build_catalog.py
```

## API Reference

The backend runs on port 8000:

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/voices` | GET | All voices (filter by `lang`, `gender`, `locale`) |
| `/api/voices/priority` | GET | English + Chinese priority voices |
| `/api/voices/match` | POST | Match voice description → best candidates |
| `/api/script/parse` | POST | Parse script + auto-assign voices |
| `/api/generate` | POST | Start audiobook generation job |
| `/api/jobs/{id}` | GET | Poll generation job status |
| `/api/preview` | POST | Generate short voice preview |
| `/api/audio/{project_id}/{file}` | GET | Serve generated files |
| `/api/catalog/stats` | GET | Catalog statistics |
| `/api/library/settings` | GET | Get all library settings |
| `/api/library/settings/{key}` | GET/PUT | Get/Update a specific setting |
| `/api/tts-providers` | GET | Get all TTS providers |
| `/api/albums` | GET/POST | List/Create albums |
| `/api/albums/{id}` | GET/PUT/DELETE | Get/Update/Delete album |
| `/api/audio-files` | GET/POST | List/Create audio files |
| `/api/audio-files/{id}` | GET/PUT/DELETE | Get/Update/Delete audio file |

## TTS Providers

> 🎉 **Ready to Use!** Clone and run — no API key required. Edge TTS works out of the box with 61+ voices.

### Edge TTS (Default, Free) ✅

![Ready to Use](https://img.shields.io/badge/status-ready_to_use-brightgreen)

- **No API key required** — works immediately after clone
- **61+ voices** for English and Chinese
- **Online service** (requires internet)
- **Free forever**

---

### ElevenLabs (Optional)

![Requires API Key](https://img.shields.io/badge/status-requires_API_key-yellow)

- High-quality neural voices
- Best for English content

**Setup Guide:**

1. **Register**: Go to [elevenlabs.io](https://elevenlabs.io/app/sign-up)
2. **Get API Key**: Dashboard → [API Keys](https://elevenlabs.io/app/settings/api-keys) → Create API Key
3. **Configure**: Add to `.env`:
   ```
   ELEVENLABS_API_KEY=your_api_key_here
   ```

**Pricing**: Free tier available (10,000 characters/month)

---

### iFlytek 科大讯飞 (Optional)

![Requires API Key](https://img.shields.io/badge/status-requires_API_key-yellow)

- Chinese voice synthesis
- Multiple Chinese accents and dialects

**Setup Guide:**

1. **Register**: Go to [xfyun.cn](https://www.xfyun.cn/) → Sign up
2. **Create App**: Console → [Create Application](https://console.xfyun.cn/app/create)
3. **Enable TTS**: Add "Online Voice Synthesis" service to your app
4. **Get Credentials**: App details page → copy `APPID`, `API Key`, `API Secret`
5. **Configure**: Add to `.env`:
   ```
   IFLYTEK_APP_ID=your_app_id
   IFLYTEK_API_KEY=your_api_key
   IFLYTEK_API_SECRET=your_api_secret
   ```

**Pricing**: Free tier available (50,000 characters/day for new users)

**Docs**: [科大讯飞语音合成文档](https://www.xfyun.cn/doc/tts/online_tts/API.html)

---

### Baidu 百度语音 (Optional)

![Requires API Key](https://img.shields.io/badge/status-requires_API_key-yellow)

- Chinese voice synthesis
- Multiple voice styles

**Setup Guide:**

1. **Register**: Go to [百度智能云](https://cloud.baidu.com/) → Sign up
2. **Create App**: [AI 控制台](https://console.bce.baidu.com/ai/#/ai/speech/app/create) → Create Application
3. **Enable TTS**: Select "短语音合成" service
4. **Get Credentials**: App details page → copy `AppID`, `API Key`, `Secret Key`
5. **Configure**: Add to `.env`:
   ```
   BAIDU_APP_ID=your_app_id
   BAIDU_API_KEY=your_api_key
   BAIDU_API_SECRET=your_api_secret
   ```

**Pricing**: Free tier available (50,000 calls/day)

**Docs**: [百度语音合成文档](https://cloud.baidu.com/doc/SPEECH/s/Nk38y8pbm)

## Known Limitations

- **Edge TTS requires internet** — Synthesis calls Microsoft's Edge TTS servers
- **Age bucket inference** — Age metadata is inferred heuristically; Edge TTS doesn't expose explicit age labels
- **Audio merge** — Requires `ffmpeg` installed locally
- **Concurrent jobs** — Jobs run sequentially; no queue management for high-volume use
- **Preview voices** — Preview requires internet to call TTS providers on demand

## Security

⚠️ **Before pushing to GitHub:**

1. **Ensure `.env` is ignored** (included in `.gitignore`)
2. **Never commit real credentials** — use `.env.example` as template
3. **Check for accidental sensitive data commits**:
   ```bash
   git status
   git diff --cached
   ```
4. **Clean history** (if sensitive data was committed before):
   ```bash
   git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch .env' HEAD
   ```

See [SECURITY.md](SECURITY.md) for more details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Created with 💙 by Nicky & AI*
