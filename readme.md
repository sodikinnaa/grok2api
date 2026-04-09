# Grok2API Fork

English-first fork of [`chenyme/grok2api`](https://github.com/chenyme/grok2api), prepared for public use and easier deployment.

> [!NOTE]
> This project is intended for learning, research, and self-hosted experimentation. You are responsible for complying with xAI/Grok terms of service and all applicable laws and regulations.

> [!NOTE]
> This fork respects the original upstream project. Please keep relevant attribution if you build on top of this fork or contribute changes back upstream.

Grok2API is a **FastAPI** server that wraps web-based Grok access into a more convenient API surface. It supports streaming and non-streaming chat, tool calls, image generation/editing, video generation/upscaling, reasoning modes, token pool concurrency, and automatic load balancing.

## Highlights

- OpenAI-style API interface for Grok
- Supports chat, image, video, and reasoning workloads
- Built-in admin panel for token, config, and cache management
- Suitable for local hosting, Docker Compose, Vercel, and Render
- This fork includes deployment-friendly defaults and public-ready documentation

## Documentation

- API docs: `http://localhost:8000/docs`
- Local English guide: `docs/README.en.md`
- User guide, Linux: `docs/userguide-linux.md`
- User guide, macOS: `docs/userguide-macos.md`
- User guide, Git Bash: `docs/userguide-gitbash.md`

<img width="4800" height="4200" alt="Grok2API admin preview" src="https://github.com/user-attachments/assets/a6669674-8afe-4ae5-bf81-a2ec1f864233" />

## Quick Start

### Run locally

```bash
uv sync
uv run granian --interface asgi --host 0.0.0.0 --port 8000 --workers 1 main:app
```

### Run with Docker Compose

```bash
git clone https://github.com/sodikinnaa/grok2api.git
cd grok2api
docker compose up -d
```

Docker Compose port variables:

- `SERVER_PORT`: port listened to by the app inside the container
- `HOST_PORT`: port exposed on the host machine

The mapping format is `HOST_PORT:SERVER_PORT`. In practice, clients connect to `HOST_PORT`, while the app inside the container still listens on `SERVER_PORT`.

Example:

```bash
HOST_PORT=9000 SERVER_PORT=8011 docker compose up -d
```

Then open:

```text
http://localhost:9000
```

### Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/sodikinnaa/grok2api&env=LOG_LEVEL,LOG_FILE_ENABLED,DATA_DIR,SERVER_STORAGE_TYPE,SERVER_STORAGE_URL&envDefaults=%7B%22DATA_DIR%22%3A%22/tmp/data%22%2C%22LOG_FILE_ENABLED%22%3A%22false%22%2C%22LOG_LEVEL%22%3A%22INFO%22%2C%22SERVER_STORAGE_TYPE%22%3A%22local%22%2C%22SERVER_STORAGE_URL%22%3A%22%22%7D)

Required settings:

- `DATA_DIR=/tmp/data`
- `LOG_FILE_ENABLED=false`

For persistent storage, use MySQL, Redis, or PostgreSQL and set both `SERVER_STORAGE_TYPE` and `SERVER_STORAGE_URL`.

### Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sodikinnaa/grok2api)

Notes:

- Free Render instances may sleep after 15 minutes of inactivity.
- Local filesystem data may be lost after restart or redeploy.
- For persistence, use MySQL, Redis, or PostgreSQL and configure `SERVER_STORAGE_TYPE` and `SERVER_STORAGE_URL`.

## Admin Panel

- URL: `http://<host>:<port>/admin`
- Default password: `grok2api`
- Config key: `app.app_key`

Change the default password before exposing the service publicly.

### Admin features

- Token management: import, add, remove, inspect status and quota
- Status filtering: normal, rate-limited, invalid, and NSFW state
- Bulk operations: refresh, export, delete, or enable NSFW in batch
- NSFW activation: one-click Unhinged activation for supported tokens
- Live configuration management
- Media cache inspection and cleanup

## Environment Variables

Configure your `.env` file before running in production.

### CORS / Cross-Origin

This fork currently enables permissive CORS by default so the API can be called from browsers across domains:

- `allow_origins=["*"]`
- `allow_methods=["*"]`
- `allow_headers=["*"]`
- `allow_credentials=False`

This setup is convenient for public token-based or bearer-auth API usage.

### Restrict to a single domain

Update the CORS middleware in `main.py` from:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

To something like:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://api.yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Restrict to multiple domains

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.yourdomain.com",
        "https://admin.yourdomain.com",
        "https://another-frontend.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Important CORS notes

- If you use `allow_origins=["*"]`, prefer `allow_credentials=False`.
- If you need cookies or browser credentials, use explicit origins instead of `*`.
- If CORS still fails in production, also inspect your reverse proxy or CDN layer (for example Nginx, Cloudflare, Render, Vercel, or preview gateways).

## Core Environment Variables

| Variable | Description | Default | Example |
| :-- | :-- | :-- | :-- |
| `LOG_LEVEL` | Log level | `INFO` | `DEBUG` |
| `LOG_FILE_ENABLED` | Enable file logging | `true` | `false` |
| `DATA_DIR` | Data directory for config, tokens, and locks | `./data` | `/data` |
| `SERVER_HOST` | Bind address | `0.0.0.0` | `0.0.0.0` |
| `SERVER_PORT` | App port | `8000` | `8000` |
| `HOST_PORT` | Host port for Docker Compose | `8000` | `9000` |
| `SERVER_WORKERS` | Worker count | `1` | `2` |
| `SERVER_STORAGE_TYPE` | Storage backend (`local`, `redis`, `mysql`, `pgsql`) | `local` | `pgsql` |
| `SERVER_STORAGE_URL` | Storage connection string | `""` | `postgresql+asyncpg://user:password@host:5432/db` |

MySQL example:

```text
mysql+aiomysql://user:password@host:3306/db
```

If you provide `mysql://`, it will be normalized automatically to `mysql+aiomysql://`.

## Available Usage Quotas

- Basic account: 80 requests / 20h
- Super account: 140 requests / 2h

## Supported Models

| Model | Usage cost | Account type | Chat | Image | Video |
| :-- | :--: | :-- | :--: | :--: | :--: |
| `grok-3` | 1 | Basic / Super | Yes | Yes | - |
| `grok-3-mini` | 1 | Basic / Super | Yes | Yes | - |
| `grok-3-thinking` | 1 | Basic / Super | Yes | Yes | - |
| `grok-4` | 1 | Basic / Super | Yes | Yes | - |
| `grok-4-thinking` | 1 | Basic / Super | Yes | Yes | - |
| `grok-4-heavy` | 4 | Super | Yes | Yes | - |
| `grok-4.1-mini` | 1 | Basic / Super | Yes | Yes | - |
| `grok-4.1-fast` | 1 | Basic / Super | Yes | Yes | - |
| `grok-4.1-expert` | 4 | Basic / Super | Yes | Yes | - |
| `grok-4.1-thinking` | 4 | Basic / Super | Yes | Yes | - |
| `grok-4.20-beta` | 1 | Basic / Super | Yes | Yes | - |
| `grok-imagine-1.0` | - | Basic / Super | - | Yes | - |
| `grok-imagine-1.0-fast` | - | Basic / Super | - | Yes | - |
| `grok-imagine-1.0-edit` | - | Basic / Super | - | Yes | - |
| `grok-imagine-1.0-video` | - | Basic / Super | - | - | Yes |

## API Endpoints

Examples below use `localhost:8000`. If you set `HOST_PORT` in Docker Compose, replace the port accordingly.

### `POST /v1/chat/completions`

General-purpose endpoint supporting chat, image generation, image editing, video generation, and video upscaling.

<details>
<summary>Supported request parameters</summary>

<br>

| Field | Type | Description | Allowed values |
| :-- | :-- | :-- | :-- |
| `model` | string | Model name | See model list above |
| `messages` | array | Message list | See message format below |
| `stream` | boolean | Enable streaming output | `true`, `false` |
| `reasoning_effort` | string | Reasoning level | `none`, `minimal`, `low`, `medium`, `high`, `xhigh` |
| `temperature` | number | Sampling temperature | `0` to `2` |
| `top_p` | number | Nucleus sampling | `0` to `1` |
| `tools` | array | Tool definitions | OpenAI function tools |
| `tool_choice` | string/object | Tool selection | `auto`, `required`, `none`, or a specific tool |
| `parallel_tool_calls` | boolean | Allow parallel tool calls | `true`, `false` |
| `video_config` | object | Video-model-specific config | For `grok-imagine-1.0-video` |
| └─`aspect_ratio` | string | Video aspect ratio | `16:9`, `9:16`, `1:1`, `2:3`, `3:2`, `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024` |
| └─`video_length` | integer | Video length in seconds | `6` to `30` |
| └─`resolution_name` | string | Resolution | `480p`, `720p` |
| └─`preset` | string | Style preset | `fun`, `normal`, `spicy`, `custom` |
| `image_config` | object | Image-model-specific config | For `grok-imagine-1.0`, `grok-imagine-1.0-fast`, `grok-imagine-1.0-edit` |
| └─`n` | integer | Number of outputs | `1` to `10` |
| └─`size` | string | Image size | `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024` |
| └─`response_format` | string | Response format | `url`, `b64_json`, `base64` |

**Message format (`messages`)**

| Field | Type | Description |
| :-- | :-- | :-- |
| `role` | string | One of `developer`, `system`, `user`, `assistant` |
| `content` | string/array | Plain text or multimodal content array |

**Multimodal content block types**

| Type | Description | Example |
| :-- | :-- | :-- |
| `text` | Text content | `{"type": "text", "text": "Describe this image"}` |
| `image_url` | Image URL | `{"type": "image_url", "image_url": {"url": "https://..."}}` |
| `input_audio` | Audio input | `{"type": "input_audio", "input_audio": {"data": "https://..."}}` |
| `file` | File input | `{"type": "file", "file": {"file_data": "https://..."}}` |

**Notes**

- `image_url`, `input_audio`, and `file` accept URLs or Data URIs (`data:<mime>;base64,...`). Raw base64 without a Data URI wrapper will fail.
- `reasoning_effort=none` disables thinking output. Other values enable thinking content.
- Tool calling is implemented as **prompt simulation + client-side execution + result injection**. The model emits tool requests via `<tool_call>{...}</tool_call>`, which are parsed into `tool_calls`; the service itself does not execute tools.
- `grok-imagine-1.0-fast` uses the same imagine waterfall pipeline and can be called directly through `/v1/chat/completions`; `n`, `size`, and `response_format` are centrally controlled by the service through `[imagine_fast]`.
- Streaming output for `grok-imagine-1.0-fast` returns only the final image, without intermediate preview frames.
- Final image URLs for streamed `grok-imagine-1.0-fast` responses preserve the original filename and do not append a `-final` suffix.
- If moderation likely blocks the final image and `image.blocked_parallel_enabled` is enabled, the service can automatically perform parallel compensation attempts using different tokens. If no final image satisfying `image.final_min_bytes` is produced, the request fails.
- `grok-imagine-1.0-edit` requires image input. For multi-image input, the service uses the last 3 images plus the last text prompt.
- `grok-imagine-1.0-video` supports text-to-video and multi-image reference video generation. You can send up to 7 reference images via multiple `image_url` blocks and refer to them in text using placeholders such as `@图1`, `@图2`; the service maps them to the correct asset IDs automatically.
- `@图N` maps one-to-one to the order of `image_url` blocks. Referencing a non-existent image index raises an error.
- Unsupported extra parameters are discarded automatically.

<br>

</details>

### `POST /v1/responses`

OpenAI Responses API-compatible endpoint.

```bash
curl http://localhost:8000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-4",
    "input": "Explain quantum tunneling",
    "stream": true
  }'
```

<details>
<summary>Supported request parameters</summary>

<br>

| Field | Type | Description |
| :-- | :-- | :-- |
| `model` | string | Model name |
| `input` | string/array | String, message array, or multimodal content blocks |
| `instructions` | string | System instructions |
| `stream` | boolean | Enable streaming output |
| `temperature` | number | Sampling temperature |
| `top_p` | number | Nucleus sampling |
| `tools` | array | Tool definitions |
| `tool_choice` | string/object | Tool selection |
| `parallel_tool_calls` | boolean | Allow parallel tool calls |
| `reasoning` | object | Reasoning parameters |
| └─`effort` | string | Reasoning level: `none`, `minimal`, `low`, `medium`, `high`, `xhigh` |

**Notes**

- Built-in tools such as `web_search`, `file_search`, and `code_interpreter` are currently mapped into function tools only to trigger tool calling behavior. Hosted execution is not performed by the service, so clients must run the tools and feed results back themselves.
- Streaming output includes `response.output_text.*` and `response.function_call_arguments.*` events.

<br>

</details>

### `POST /v1/images/generations`

Image generation endpoint.

```bash
curl http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-imagine-1.0",
    "prompt": "A cat floating in space",
    "n": 1
  }'
```

### `POST /v1/images/edits`

Image editing endpoint using `multipart/form-data`.

```bash
curl http://localhost:8000/v1/images/edits \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -F "model=grok-imagine-1.0-edit" \
  -F "prompt=Make this image sharper" \
  -F "image=@/path/to/image.png" \
  -F "n=1"
```

### `POST /v1/videos`

Video generation endpoint compatible with `videos.create`-style workflows.

```bash
curl http://localhost:8000/v1/videos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-imagine-1.0-video",
    "prompt": "A neon rainy street at night, cinematic slow tracking shot",
    "size": "1792x1024",
    "seconds": 18,
    "quality": "standard"
  }'
```

## Configuration

Main config file:

```text
data/config.toml
```

> [!NOTE]
> In production or behind a reverse proxy, set `app.app_url` to the full externally reachable URL. Otherwise generated file links may be incorrect or lead to issues such as 403 responses.

> [!TIP]
> Config structure v2.0 is automatically migrated from older layouts. Existing custom values in the legacy `[grok]` section are remapped into the newer section structure automatically.

Key configuration areas include:

- `app`: app URL, admin password, API key, streaming, thinking, custom instruction
- `proxy`: base proxy URL, asset proxy URL, Cloudflare cookies, FlareSolverr settings
- `retry`: retry limits, backoff, retry budget, reset-on-status behavior
- `token`: refresh interval, failure thresholds, multi-worker synchronization
- `cache`: auto-clean and size limits
- `chat`, `image`, `video`, `voice`, `asset`: concurrency and timeout controls
- `usage`, `nsfw`: batch and concurrency controls for maintenance operations

If you want to expose this service publicly, review at minimum:

- `app.app_key`
- `app.api_key`
- `app.app_url`
- CORS settings in `main.py`
- storage backend configuration for persistence
- reverse proxy and TLS setup

## Upstream Credit

This project is based on the original work at:

- Upstream: <https://github.com/chenyme/grok2api>

If you find this fork useful, consider starring or supporting the upstream project as well.
