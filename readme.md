# Grok2API Fork

**Bahasa Indonesia** | [English](docs/README.en.md)

Fork ini berbasis proyek asli [`chenyme/grok2api`](https://github.com/chenyme/grok2api) dan disesuaikan agar lebih mudah dipakai oleh pengguna Indonesia.

> [!NOTE]
> Proyek ini ditujukan untuk pembelajaran dan riset. Penggunaan tetap harus mematuhi **Terms of Use Grok/xAI** serta hukum dan regulasi yang berlaku. Jangan gunakan untuk aktivitas ilegal.

> [!NOTE]
> Fork ini tetap menghormati karya upstream. Jika melakukan modifikasi lanjutan atau membuka pull request, pertahankan atribusi yang relevan terhadap proyek asli.

Grok2API adalah server **FastAPI** yang membungkus akses Grok berbasis web menjadi endpoint API yang lebih nyaman dipakai. Project ini mendukung chat streaming/non-streaming, tool call, image generation/editing, video generation/upscale, deep reasoning, token pool concurrency, dan automatic load balancing.

## Ringkasan

- API kompatibel gaya OpenAI untuk Grok
- Mendukung chat, image, video, dan reasoning
- Ada panel admin untuk mengelola token, config, dan cache
- Cocok untuk self-hosting lokal, Docker Compose, Vercel, dan Render
- Fork ini menambahkan dokumentasi utama berbahasa Indonesia

## Perbedaan fork ini

- README utama diarahkan untuk pembaca Indonesia
- Tetap kompatibel dengan struktur dan fungsi upstream
- Referensi upstream dipertahankan agar alur update tetap jelas

<img width="4800" height="4200" alt="image" src="https://github.com/user-attachments/assets/a6669674-8afe-4ae5-bf81-a2ec1f864233" />

<br>

## Memulai Cepat

### Jalankan lokal

```bash
uv sync

uv run granian --interface asgi --host 0.0.0.0 --port 8000 --workers 1 main:app
```

### Docker Compose

```bash
git clone git@github.com:sodikinnaa/grok2api-fork.git

cd grok2api-fork

docker compose up -d
```

> Variabel port Docker Compose:
>
> - `SERVER_PORT`: port yang didengarkan aplikasi di dalam container
> - `HOST_PORT`: port yang dipublikasikan ke host
>
> Format mapping-nya adalah `HOST_PORT:SERVER_PORT`. Jadi yang kamu akses dari browser/client adalah `HOST_PORT`, sedangkan aplikasi di dalam container tetap mendengarkan di `SERVER_PORT`.
>
> Contoh: `HOST_PORT=9000 SERVER_PORT=8011 docker compose up -d`, lalu akses `http://localhost:9000`.

### Deploy ke Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/sodikinnaa/grok2api-fork&env=LOG_LEVEL,LOG_FILE_ENABLED,DATA_DIR,SERVER_STORAGE_TYPE,SERVER_STORAGE_URL&envDefaults=%7B%22DATA_DIR%22%3A%22/tmp/data%22%2C%22LOG_FILE_ENABLED%22%3A%22false%22%2C%22LOG_LEVEL%22%3A%22INFO%22%2C%22SERVER_STORAGE_TYPE%22%3A%22local%22%2C%22SERVER_STORAGE_URL%22%3A%22%22%7D)

> Wajib set `DATA_DIR=/tmp/data` dan nonaktifkan file log dengan `LOG_FILE_ENABLED=false`.
>
> Untuk penyimpanan persisten, gunakan MySQL / Redis / PostgreSQL lalu set `SERVER_STORAGE_TYPE` dan `SERVER_STORAGE_URL`.

### Deploy ke Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sodikinnaa/grok2api-fork)

> Instance gratis Render akan sleep setelah 15 menit tanpa trafik; restart atau redeploy juga bisa menghilangkan data lokal.
>
> Untuk penyimpanan persisten, gunakan MySQL / Redis / PostgreSQL lalu set `SERVER_STORAGE_TYPE` dan `SERVER_STORAGE_URL`.

<br>

## Panel Admin

- Alamat akses: `http://<host>:<port>/admin` (untuk menjalankan lokal gunakan `SERVER_PORT`, untuk Docker Compose gunakan `HOST_PORT`, default keduanya `8000`)
- Password default: `grok2api` (opsi konfigurasi `app.app_key`, disarankan untuk diubah)

**Penjelasan fitur**：

- **Manajemen Token**: impor/tambah/hapus Token, lihat status dan kuota
- **Filter status**: filter berdasarkan status (normal/rate limit/tidak valid) atau status NSFW
- **Operasi massal**: refresh, export, hapus, atau aktifkan NSFW secara massal
- **Aktivasi NSFW**: aktifkan mode Unhinged untuk Token dengan satu klik (memerlukan proxy atau `cf_clearance`)
- **Manajemen konfigurasi**: ubah konfigurasi sistem secara online
- **Manajemen cache**: lihat dan bersihkan cache media

<br>

## Variabel Lingkungan

> Konfigurasikan file `.env`

| Nama variabel | Keterangan | Nilai default | Contoh |
| :-- | :-- | :-- | :-- |
| `LOG_LEVEL` | Level log | `INFO` | `DEBUG` |
| `LOG_FILE_ENABLED` | Apakah file log diaktifkan | `true` | `false` |
| `DATA_DIR` | Direktori data (konfigurasi/Token/lock) | `./data` | `/data` |
| `SERVER_HOST` | Alamat listen service | `0.0.0.0` | `0.0.0.0` |
| `SERVER_PORT` | Port service | `8000` | `8000` |
| `HOST_PORT` | Port mapping host untuk Docker Compose | `8000` | `9000` |
| `SERVER_WORKERS` | Jumlah proses service | `1` | `2` |
| `SERVER_STORAGE_TYPE` | Tipe storage (`local`/`redis`/`mysql`/`pgsql`) | `local` | `pgsql` |
| `SERVER_STORAGE_URL` | Connection string storage (boleh kosong jika `local`) | `""` | `postgresql+asyncpg://user:password@host:5432/db` |

> Contoh MySQL: `mysql+aiomysql://user:password@host:3306/db` (jika mengisi `mysql://`, akan otomatis dikonversi menjadi `mysql+aiomysql://`)

<br>

## Jumlah Penggunaan Tersedia

- Akun Basic: 80 kali / 20h
- Akun Super: 140 kali / 2h

<br>

## Model yang Tersedia

| Nama model | Hitungan penggunaan | Akun yang tersedia | Fitur percakapan | Fitur gambar | Fitur video |
| :-- | :--: | :-- | :--: | :--: | :--: |
| `grok-3` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-3-mini` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-3-thinking` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-4` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-4-thinking` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-4-heavy` | 4 | Super | Didukung | Didukung | - |
| `grok-4.1-mini` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-4.1-fast` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-4.1-expert` | 4 | Basic/Super | Didukung | Didukung | - |
| `grok-4.1-thinking` | 4 | Basic/Super | Didukung | Didukung | - |
| `grok-4.20-beta` | 1 | Basic/Super | Didukung | Didukung | - |
| `grok-imagine-1.0` | - | Basic/Super | - | Didukung | - |
| `grok-imagine-1.0-fast` | - | Basic/Super | - | Didukung | - |
| `grok-imagine-1.0-edit` | - | Basic/Super | - | Didukung | - |
| `grok-imagine-1.0-video` | - | Basic/Super | - | - | Didukung |

<br>

## Penjelasan Endpoint

> Contoh di bawah secara default menggunakan `localhost:8000`; jika Docker Compose mengatur `HOST_PORT`, ganti dengan port yang sesuai.

### `POST /v1/chat/completions`

> Endpoint umum, mendukung chat, image generation, image editing, video generation, dan video upscaling

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-4",
    "messages": [{"role":"user","content":"你好"}]
  }'
```

<details>
<summary>Parameter request yang didukung</summary>

<br>

| Field | Tipe | Keterangan | Parameter yang tersedia |
| :-- | :-- | :-- | :-- |
| `model` | string | Nama model | Lihat daftar model di atas |
| `messages` | array | Daftar pesan | Lihat format pesan di bawah |
| `stream` | boolean | Apakah mengaktifkan output streaming | `true`, `false` |
| `reasoning_effort` | string | Tingkat reasoning | `none`, `minimal`, `low`, `medium`, `high`, `xhigh` |
| `temperature` | number | Temperatur sampling | `0` ~ `2` |
| `top_p` | number | Nucleus sampling | `0` ~ `1` |
| `tools` | array | Definisi tool | OpenAI function tools |
| `tool_choice` | string/object | Pemilihan tool | `auto`, `required`, `none` atau tool tertentu |
| `parallel_tool_calls` | boolean | Apakah mengizinkan pemanggilan tool paralel | `true`, `false` |
| `video_config` | object | **Objek konfigurasi khusus model video** | Mendukung: `grok-imagine-1.0-video` |
| └─`aspect_ratio` | string | Rasio aspek video | `16:9`, `9:16`, `1:1`, `2:3`, `3:2`, `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024` |
| └─`video_length` | integer | Durasi video (detik) | `6` ~ `30` |
| └─`resolution_name` | string | Resolusi | `480p`, `720p` |
| └─`preset` | string | Preset gaya | `fun`, `normal`, `spicy`, `custom` |
| `image_config` | object | **Objek konfigurasi khusus model gambar** | Mendukung: `grok-imagine-1.0` / `grok-imagine-1.0-fast` / `grok-imagine-1.0-edit` |
| └─`n` | integer | Jumlah generasi | `1` ~ `10` |
| └─`size` | string | Ukuran gambar | `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024` |
| └─`response_format` | string | Format respons | `url`, `b64_json`, `base64` |

**Format pesan (messages)**：

| Field | Tipe | Keterangan |
| :-- | :-- | :-- |
| `role` | string | Peran: `developer`, `system`, `user`, `assistant` |
| `content` | string/array | Isi pesan, mendukung teks biasa atau array multimodal |

**Tipe blok konten multimodal (content array)**：

| type | Keterangan | Contoh |
| :-- | :-- | :-- |
| `text` | Konten teks | `{"type": "text", "text": "Deskripsikan gambar ini"}` |
| `image_url` | URL gambar | `{"type": "image_url", "image_url": {"url": "https://..."}}` |
| `input_audio` | Audio | `{"type": "input_audio", "input_audio": {"data": "https://..."}}` |
| `file` | File | `{"type": "file", "file": {"file_data": "https://..."}}` |

**Catatan**：

- `image_url/input_audio/file` hanya mendukung URL atau Data URI (`data:<mime>;base64,...`), base64 mentah akan menyebabkan error.
- `reasoning_effort`: `none` berarti tidak mengeluarkan thinking, sedangkan nilai lain akan mengeluarkan konten thinking.
- Pemanggilan tool menggunakan **simulasi prompt + client-side execution dan pengisian balik**: model mengeluarkan permintaan panggilan melalui `<tool_call>{...}</tool_call>`, lalu service mem-parsing-nya menjadi `tool_calls`; tool tidak dieksekusi oleh service.
- `grok-imagine-1.0-fast` menggunakan alur generasi imagine waterfall yang sama, sehingga bisa langsung dipanggil lewat `/v1/chat/completions`; parameter `n/size/response_format` dikendalikan secara terpusat oleh service melalui `[imagine_fast]`.
- Output streaming `grok-imagine-1.0-fast` di `/v1/chat/completions` hanya mengembalikan gambar final, tanpa preview di tengah proses.
- URL gambar hasil streaming `grok-imagine-1.0-fast` akan mempertahankan nama file asli (tanpa menambahkan suffix `-final`).
- Jika gambar diduga terblokir moderasi sehingga tidak ada gambar final, dan `image.blocked_parallel_enabled` aktif, service akan otomatis menjalankan generasi kompensasi paralel sesuai `image.blocked_parallel_attempts`, serta memprioritaskan token yang berbeda; jika tetap tidak ada gambar final yang memenuhi `image.final_min_bytes`, respons akan gagal.
- `grok-imagine-1.0-edit` wajib menyertakan gambar; untuk multi-gambar, secara default akan diambil **3 gambar terakhir** dan teks terakhir.
- `grok-imagine-1.0-video` mendukung text-to-video dan video referensi multi-gambar: bisa mengirim hingga `7` gambar referensi melalui beberapa `image_url`, lalu menggunakan placeholder seperti `@图1`, `@图2` dalam teks; service akan otomatis menggantinya dengan `assetId` yang sesuai.
- `@图N` berkorespondensi satu per satu dengan urutan `image_url`; jika mereferensikan nomor gambar yang tidak ada, akan langsung error.
- Parameter lain di luar yang disebutkan di atas akan otomatis dibuang dan diabaikan.

<br>

</details>

<br>

### `POST /v1/responses`

> Endpoint kompatibel dengan OpenAI Responses API

```bash
curl http://localhost:8000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-4",
    "input": "解释一下量子隧穿",
    "stream": true
  }'
```

<details>
<summary>Parameter request yang didukung</summary>

<br>

| Field | Tipe | Keterangan |
| :-- | :-- | :-- |
| `model` | string | Nama model |
| `input` | string/array | Konten input, mendukung string, array pesan, atau blok konten multimodal |
| `instructions` | string | Instruksi sistem |
| `stream` | boolean | Apakah menggunakan output streaming |
| `temperature` | number | Temperatur sampling |
| `top_p` | number | Nucleus sampling |
| `tools` | array | Definisi tool (mendukung function tool; tipe tool bawaan dijelaskan di bawah) |
| `tool_choice` | string/object | Pemilihan tool (auto/required/none atau tool tertentu) |
| `parallel_tool_calls` | boolean | Apakah mengizinkan pemanggilan tool paralel |
| `reasoning` | object | Parameter reasoning |
| └─`effort` | string | Tingkat reasoning | `none`, `minimal`, `low`, `medium`, `high`, `xhigh` |

**Catatan**：

- Tool bawaan `web_search` / `file_search` / `code_interpreter` saat ini akan dipetakan menjadi function tool untuk **memicu pemanggilan**, tetapi **tidak mengeksekusi hosted tool**, sehingga client perlu menjalankan dan mengisi balik hasilnya sendiri.
- Output streaming akan mencakup event `response.output_text.*` dan `response.function_call_arguments.*`.

<br>

</details>

<br>

### `POST /v1/images/generations`

> Endpoint image generation

```bash
curl http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-imagine-1.0",
    "prompt": "一只在太空漂浮的猫",
    "n": 1
  }'
```

<details>
<summary>Parameter request yang didukung</summary>

<br>

| Field | Tipe | Keterangan | Parameter yang tersedia |
| :-- | :-- | :-- | :-- |
| `model` | string | Nama model gambar | `grok-imagine-1.0` |
| `prompt` | string | Prompt deskripsi gambar | - |
| `n` | integer | Jumlah generasi | `1` - `10` (mode streaming hanya mendukung `1` atau `2`) |
| `stream` | boolean | Apakah mengaktifkan output streaming | `true`, `false` |
| `size` | string | Ukuran gambar | `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024` |
| `quality` | string | Kualitas gambar | - (belum didukung) |
| `response_format` | string | Format respons | `url`, `b64_json`, `base64` |
| `style` | string | Gaya | - (belum didukung) |

**Catatan**：

- Parameter `quality` dan `style` disediakan untuk kompatibilitas OpenAI, tetapi saat ini belum mendukung kustomisasi.
- Jika edit multi-gambar menerima lebih dari 3 gambar, hanya **3 gambar terakhir** yang akan dipakai sebagai referensi.

<br>

</details>

<br>

### `POST /v1/images/edits`

> Endpoint image editing (`multipart/form-data`)

```bash
curl http://localhost:8000/v1/images/edits \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -F "model=grok-imagine-1.0-edit" \
  -F "prompt=把图片变清晰" \
  -F "image=@/path/to/image.png" \
  -F "n=1"
```

<details>
<summary>Parameter request yang didukung</summary>

<br>

| Field | Tipe | Keterangan | Parameter yang tersedia |
| :-- | :-- | :-- | :-- |
| `model` | string | Nama model gambar | `grok-imagine-1.0-edit` |
| `prompt` | string | Deskripsi edit | - |
| `image` | file | Gambar yang akan diedit | `png`, `jpg`, `webp` |
| `n` | integer | Jumlah generasi | `1` - `10` (mode streaming hanya mendukung `1` atau `2`) |
| `stream` | boolean | Apakah mengaktifkan output streaming | `true`, `false` |
| `size` | string | Ukuran gambar | `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024` |
| `quality` | string | Kualitas gambar | - (belum didukung) |
| `response_format` | string | Format respons | `url`, `b64_json`, `base64` |
| `style` | string | Gaya | - (belum didukung) |

**Catatan**：

- Parameter `quality` dan `style` disediakan untuk kompatibilitas OpenAI, tetapi saat ini belum mendukung kustomisasi.

<br>

</details>

<br>

### `POST /v1/videos`

> Endpoint video generation (kompatibel dengan OpenAI videos.create)

```bash
curl http://localhost:8000/v1/videos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GROK2API_API_KEY" \
  -d '{
    "model": "grok-imagine-1.0-video",
    "prompt": "霓虹雨夜街头，慢镜头追拍",
    "size": "1792x1024",
    "seconds": 18,
    "quality": "standard"
  }'
```

<details>
<summary>Parameter request yang didukung</summary>

<br>

| Field | Tipe | Keterangan | Parameter yang tersedia |
| :-- | :-- | :-- | :-- |
| `model` | string | Nama model video | `grok-imagine-1.0-video` |
| `prompt` | string | Prompt video | - |
| `size` | string | Rasio frame (akan dipetakan ke aspect_ratio) | `1280x720`, `720x1280`, `1792x1024`, `1024x1792`, `1024x1024` |
| `seconds` | integer | Durasi target (detik) | `6` ~ `30` |
| `quality` | string | Kualitas video (dipetakan ke resolution) | `standard`, `high` |
| `image_reference` | array | Gambar referensi (opsional) | Kompatibel dengan format array content block OpenAI (`[{"type":"image_url"...}]`) atau array string URL biasa; untuk satu gambar tetap gunakan array satu elemen |
| `input_reference` | file | Gambar referensi multipart (opsional) | `png`, `jpg`, `webp` |

**Catatan**：

- Service sudah mendukung ekspansi berantai otomatis untuk durasi 6~30 detik, **tanpa perlu menggunakan `/v1/video/extend`**.
- `quality=standard` sesuai dengan `480p`; `quality=high` sesuai dengan `720p`.
- Jika pool akun Basic meminta `720p`, hasilnya akan dibuat sebagai `480p` terlebih dahulu lalu di-upscale sesuai `video.upscale_timing`.
- `image_reference` wajib menggunakan format array, dengan maksimum 7 gambar referensi; untuk satu gambar pun tetap gunakan array satu elemen. `input_reference` terutama untuk upload gambar referensi melalui form; jika keduanya dikirim bersamaan, keduanya akan digabung sebagai input referensi sesuai urutan; placeholder seperti `@图1`, `@图2` bisa digunakan di prompt.

<br>

</details>

<br>

## Konfigurasi Parameter

File konfigurasi: `data/config.toml`

> [!NOTE]
> Saat deployment production atau di balik reverse proxy, pastikan `app.app_url` dikonfigurasi sebagai URL lengkap yang dapat diakses dari luar,
> jika tidak, link akses file bisa salah atau memunculkan masalah seperti 403.

> [!TIP]
> **Upgrade struktur konfigurasi v2.0**: setelah update, pengguna versi lama akan **dimigrasikan otomatis** ke struktur baru tanpa perlu mengubah konfigurasi secara manual.
> Nilai kustom pada section `[grok]` lama akan otomatis dipetakan ke section konfigurasi baru yang sesuai.

| Modul | Field | Nama konfigurasi | Keterangan | Nilai default |
| :-- | :-- | :-- | :-- | :-- |
| **app** | `app_url` | Alamat aplikasi | URL akses eksternal layanan Grok2API saat ini, digunakan untuk akses link file. | `""` |
|  | `app_key` | Password admin | Password untuk login ke panel admin Grok2API (wajib diisi). | `grok2api` |
|  | `api_key` | API key | Token untuk memanggil layanan Grok2API (opsional, mendukung pemisah koma atau array). | `""` |
|  | `function_enabled` | Sakelar Function | Apakah fitur function diaktifkan. | `false` |
|  | `function_key` | Function key | Kunci pemanggilan Function (opsional). | `""` |
|  | `image_format` | Format gambar | Format gambar yang dihasilkan (url atau base64). | `url` |
|  | `video_format` | Format video | Format video yang dihasilkan (html atau url, url adalah link hasil pemrosesan). | `html` |
|  | `temporary` | Percakapan sementara | Apakah mode percakapan sementara diaktifkan. | `true` |
|  | `disable_memory` | Nonaktifkan memory | Menonaktifkan fitur memory Grok agar respons tidak menyertakan konteks yang tidak relevan. | `true` |
|  | `stream` | Respons streaming | Apakah output streaming diaktifkan secara default. | `true` |
|  | `thinking` | Chain of thought | Apakah output chain-of-thought diaktifkan secara default. | `true` |
|  | `dynamic_statsig` | Fingerprint dinamis | Apakah fingerprint Statsig dihasilkan secara dinamis. | `true` |
|  | `custom_instruction` | Instruksi kustom | Teks multi-baris yang diteruskan sebagai `customPersonality` ke Grok. | `""` |
|  | `filter_tags` | Filter tag | Secara otomatis memfilter tag khusus dalam respons Grok. | `["xaiartifact","xai:tool_usage_card","grok:render"]` |
| **proxy** | `base_proxy_url` | URL proxy dasar | Alamat service dasar untuk mem-proxy request ke situs resmi Grok. | `""` |
|  | `asset_proxy_url` | URL proxy aset | Alamat untuk mem-proxy aset statis (gambar/video) dari situs resmi Grok. | `""` |
|  | `cf_cookies` | CF Cookies | String Cookie lengkap yang ditulis saat refresh FlareSolverr. | `""` |
|  | `skip_proxy_ssl_verify` | Lewati verifikasi SSL proxy | Aktifkan saat proxy memakai sertifikat self-signed (hanya melewati sertifikat proxy, situs tujuan tetap diverifikasi). | `false` |
|  | `enabled` | Refresh CF otomatis | Apakah refresh CF otomatis diaktifkan. | `false` |
|  | `flaresolverr_url` | Alamat FlareSolverr | Alamat HTTP service FlareSolverr. | `""` |
|  | `refresh_interval` | Interval refresh | Interval refresh otomatis `cf_clearance` (detik). | `3600` |
|  | `timeout` | Timeout challenge | Timeout menunggu challenge CF (detik). | `60` |
|  | `cf_clearance` | CF Clearance | Cookie verifikasi Cloudflare. | `""` |
|  | `browser` | Fingerprint browser | Identifier fingerprint browser `curl_cffi` (misalnya `chrome136`). | `chrome136` |
|  | `user_agent` | User-Agent | String User-Agent untuk request HTTP. | `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36` |
| **retry** | `max_retry` | Maksimum retry | Jumlah maksimum retry saat request ke service Grok gagal. | `3` |
|  | `retry_status_codes` | Kode status retry | Daftar kode status HTTP yang memicu retry. | `[401, 429, 403]` |
|  | `reset_session_status_codes` | Kode status reset | Daftar kode status HTTP yang memicu pembuatan ulang session (untuk rotasi proxy). | `[403]` |
|  | `retry_backoff_base` | Basis backoff | Delay dasar untuk backoff retry (detik). | `0.5` |
|  | `retry_backoff_factor` | Faktor backoff | Koefisien eksponensial pengali backoff retry. | `2.0` |
|  | `retry_backoff_max` | Batas atas backoff | Delay maksimum untuk satu kali retry (detik). | `20.0` |
|  | `retry_budget` | Budget backoff | Total waktu maksimum retry untuk satu request (detik). | `60.0` |
| **token** | `auto_refresh` | Refresh otomatis | Apakah mekanisme refresh Token otomatis diaktifkan. | `true` |
|  | `refresh_interval_hours` | Interval refresh | Interval waktu refresh Token biasa (jam). | `8` |
|  | `super_refresh_interval_hours` | Interval refresh Super | Interval waktu refresh Token Super (jam). | `2` |
|  | `fail_threshold` | Ambang kegagalan | Berapa kali Token gagal berturut-turut sebelum ditandai tidak tersedia. | `5` |
|  | `save_delay_ms` | Delay penyimpanan | Delay write gabungan saat Token berubah (milidetik). | `500` |
|  | `usage_flush_interval_sec` | Interval flush penggunaan | Interval minimum untuk menulis field penggunaan ke database (detik). | `5` |
|  | `reload_interval_sec` | Interval sinkronisasi | Interval refresh status Token pada skenario multi-worker (detik). | `30` |
| **cache** | `enable_auto_clean` | Pembersihan otomatis | Apakah pembersihan cache otomatis diaktifkan; jika aktif, cache akan direklamasi saat melebihi batas. | `true` |
|  | `limit_mb` | Ambang pembersihan | Ambang ukuran cache (MB); jika terlampaui akan memicu pembersihan. | `512` |
| **chat** | `concurrent` | Batas paralel | Batas paralel endpoint Reverse. | `50` |
|  | `timeout` | Timeout request | Timeout endpoint Reverse (detik). | `60` |
|  | `stream_timeout` | Timeout idle stream | Timeout idle stream (detik). | `60` |
| **image** | `timeout` | Timeout request | Timeout request WebSocket (detik). | `60` |
|  | `stream_timeout` | Timeout idle stream | Timeout idle stream WebSocket (detik). | `60` |
|  | `final_timeout` | Timeout gambar final | Waktu tunggu maksimum setelah menerima gambar kualitas menengah untuk gambar final (detik). | `15` |
|  | `blocked_grace_seconds` | Grace period moderasi | Masa tenggang untuk menilai gambar kemungkinan terblokir moderasi setelah menerima gambar menengah (detik). | `10` |
|  | `nsfw` | Mode NSFW | Apakah request WebSocket mengaktifkan NSFW. | `true` |
|  | `medium_min_bytes` | Byte minimum gambar menengah | Ukuran byte minimum untuk mengidentifikasi gambar kualitas menengah. | `30000` |
|  | `final_min_bytes` | Byte minimum gambar final | Ukuran byte minimum untuk mengidentifikasi gambar final (biasanya JPG > 100KB). | `100000` |
|  | `blocked_parallel_attempts` | Jumlah kompensasi paralel | Berapa kali generasi kompensasi paralel dilakukan saat diduga terkena moderasi/pemblokiran. | `5` |
|  | `blocked_parallel_enabled` | Sakelar kompensasi paralel | Apakah kompensasi paralel diaktifkan (jika aktif, akan memprioritaskan token yang berbeda). | `true` |
| **imagine_fast** | `n` | Jumlah generasi | Hanya berlaku untuk `grok-imagine-1.0-fast`. | `1` |
|  | `size` | Ukuran gambar | `1280x720` / `720x1280` / `1792x1024` / `1024x1792` / `1024x1024` | `1024x1024` |
|  | `response_format` | Format respons | `url` / `b64_json` / `base64` | `url` |
| **video** | `concurrent` | Batas paralel | Batas paralel endpoint Reverse. | `100` |
|  | `timeout` | Timeout request | Timeout endpoint Reverse (detik). | `60` |
|  | `stream_timeout` | Timeout idle stream | Timeout idle stream (detik). | `60` |
|  | `upscale_timing` | Waktu upscale | Mode upscale 720p untuk pool akun Basic: `single` (upscale setelah tiap ekspansi) / `complete` (upscale setelah semua ekspansi selesai). | `complete` |
| **voice** | `timeout` | Timeout request | Timeout request Voice (detik). | `60` |
| **asset** | `upload_concurrent` | Paralel upload | Jumlah paralel maksimum untuk endpoint upload. | `100` |
|  | `upload_timeout` | Timeout upload | Timeout endpoint upload (detik). | `60` |
|  | `download_concurrent` | Paralel download | Jumlah paralel maksimum untuk endpoint download. | `100` |
|  | `download_timeout` | Timeout download | Timeout endpoint download (detik). | `60` |
|  | `list_concurrent` | Paralel query | Jumlah paralel maksimum untuk endpoint query aset. | `100` |
|  | `list_timeout` | Timeout query | Timeout endpoint query aset (detik). | `60` |
|  | `list_batch_size` | Ukuran batch query | Jumlah Token yang dapat diproses dalam satu kali query. | `50` |
|  | `delete_concurrent` | Paralel hapus | Jumlah paralel maksimum untuk endpoint hapus aset. | `100` |
|  | `delete_timeout` | Timeout hapus | Timeout endpoint hapus aset (detik). | `60` |
|  | `delete_batch_size` | Ukuran batch hapus | Jumlah Token yang dapat dihapus dalam satu kali proses. | `50` |
| **nsfw** | `concurrent` | Batas paralel | Batas request paralel saat mengaktifkan mode NSFW secara massal. | `60` |
|  | `batch_size` | Ukuran batch | Jumlah item per batch saat mengaktifkan mode NSFW secara massal. | `30` |
|  | `timeout` | Timeout request | Timeout request terkait aktivasi NSFW (detik). | `60` |
| **usage** | `concurrent` | Batas paralel | Batas request paralel saat me-refresh usage secara massal. | `100` |
|  | `batch_size` | Ukuran batch | Jumlah item per batch saat me-refresh usage secara massal. | `50` |
|  | `timeout` | Timeout request | Timeout endpoint query usage (detik). | `60` |

<br>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Chenyme/grok2api&type=Timeline)](https://star-history.com/#Chenyme/grok2api&Timeline)
