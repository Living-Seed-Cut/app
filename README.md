<div align="center">
  <img src="https://livingseed.org/wp-content/uploads/2023/05/LSeed-Logo-1.png" alt="Livingseed Logo" width="200"/>
  
  # Livingseed Media Cut
  
  **The official tool to extract audio from our ministry videos**
  
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
  [![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)](https://www.python.org/)
  [![FFmpeg](https://img.shields.io/badge/FFmpeg-4.0+-007808?logo=ffmpeg)](https://ffmpeg.org/)
  [![yt-dlp](https://img.shields.io/badge/yt--dlp-2023+-red)](https://github.com/yt-dlp/yt-dlp)
  
  [Live Demo](https://livingseed.org) · [Report Bug](https://github.com/livingseed/mediacut/issues) · [Request Feature](https://github.com/livingseed/mediacut/issues)
</div>

---

## 📖 About

Livingseed Media Cut is a robust API designed to help our ministry community easily extract audio from YouTube videos. Whether you need a sermon clip, worship song segment, or teaching excerpt, this tool makes it simple to download exactly what you need in your preferred format.

### ✨ Key Features

- 🎵 **Multiple Formats** - Download in MP3 (audio), WAV (high quality), or MP4 (video)
- ✂️ **Precise Trimming** - Extract specific time ranges or full tracks
- 📝 **Custom Metadata** - Add filename, topic/album, and artist/speaker information
- 📊 **Real-time Progress** - Track extraction progress with live updates
- 📜 **Download History** - Keep track of your recent extractions
- ⚡ **Fast & Free** - No registration required, completely free to use


---

## 🚀 Quick Start

### Prerequisites

- [Python](https://www.python.org/) (version 3.8 or higher)
- [FFmpeg](https://ffmpeg.org/) (optional, bundled version available)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/livingseed/mediacut.git
   cd mediacut/app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the app directory (optional, see `.env.example`):
   ```bash
   cp .env.example .env
   ```

4. **Run the server**
   ```bash
   python main.py
   ```

5. **Docker (Optional)**
   ```bash
   # Build and run with Docker Compose
   docker-compose up -d --build
   ```

5. **Access the API**
   
   Navigate to [http://localhost:3000/docs](http://localhost:3000/docs) to see the API documentation.

---

## 📦 Available Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Start server |
| `python main.py --help` | Show all available options |

---

## 🎯 How to Use

1. **Paste a YouTube URL** - Copy any YouTube video link
2. **Choose extraction mode**:
   - **Snippet** - Extract a specific time range
   - **Full Track** - Download the entire video audio
3. **Set time range** (for snippets) - Enter start and end times
4. **Select output format** - Choose MP3, WAV, or MP4
5. **Add metadata** (optional) - Customize filename, topic, and speaker
6. **Click "Start Extraction"** - Wait for processing to complete
7. **Download your file** - Click the download button when ready

---

## 🛠️ Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework for building APIs
- **Processing**: [yt-dlp](https://github.com/yt-dlp/yt-dlp) & [FFmpeg](https://ffmpeg.org/) - Media downloading and processing
- **Language**: [Python](https://www.python.org/) - Core programming language

---

## 📁 Project Structure

```
app/
├── config.py                # Configuration & environment vars
├── main.py                  # FastAPI app initialization
├── requirements.txt         # Python dependencies
├── routes/                  # API route handlers
│   ├── extract.py           # Audio extraction endpoints
│   ├── video_info.py        # Video info endpoints
│   ├── health.py            # Health check endpoint
│   └── app.py               # App home endpoints
├── services/                # Business logic
│   └── extractor.py         # Core extraction service
├── models/                  # Pydantic models
│   ├── requests.py          # Request schemas
│   └── responses.py         # Response schemas
├── utils/                   # Utility modules
│   └── ffmpeg_utils.py      # FFmpeg helpers
```

---

## 🌍 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server host | 0.0.0.0 |
| `YOUTUBE_PROXY_URL` | Proxy URL | None |
| `YOUTUBE_COOKIES_PATH` | Path to cookies file | None |
| `YOUTUBE_VISITOR_DATA` | Cookie-less bot bypass token (from `window.yt.config_.VISITOR_DATA`) | |
| `YOUTUBE_PO_TOKEN` | Proof of Origin Token (Optional, for advanced bypass) | |
| `YOUTUBE_COOKIES_CONTENT` | Base64 encoded content of `cookies.txt` (Fallback) | None |
| `LOG_TO_FILE` | Enable file logging | false |
| `MAX_CONCURRENT_JOBS` | Max simultaneous extractions | 3 |
| `CACHE_ENABLED` | Enable audio caching | true |
| `FFMPEG_THREADS` | Threads for processing | 4 |

See `.env.example` for all available options.

### 🍪 Cookie Content

To handle age-restricted videos or other access issues, you can provide YouTube cookies.

1.  **Export Cookies**: Use a browser extension (e.g., "Get cookies.txt" for Chrome/Firefox) to export your YouTube cookies into a `cookies.txt` file.
2.  **Place File**:
    *   **Local**: Place `cookies.txt` in your `app/` directory or any accessible path.
    *   **Docker**: Mount `cookies.txt` into the container, e.g., `/app/cookies.txt`.
3.  **Configure**: Set `YOUTUBE_COOKIES_PATH=/app/cookies.txt` (Docker) or absolute path (local).

### Google OAuth Credentials (Vercel)

For cloud deployments (like Vercel) where you cannot upload sensitive files like `client_secrets.json` or `youtube_api_creds.pickle`, you can provide them as Base64 encoded environment variables.

1.  **Encode `client_secrets.json`**:
    ```bash
    base64 -i client_secrets.json -o -
    ```
    Copy the output and set it as `GOOGLE_CLIENT_SECRETS`.

2.  **Encode `youtube_api_creds.pickle`**:
    First, generate the token locally using `python generate_token.py`. Then encode it:
    ```bash
    base64 -i youtube_api_creds.pickle -o -
    ```
    Copy the output and set it as `GOOGLE_API_TOKEN`.

### Anti-Bot Bypass (Cookie-less)

To bypass YouTube's "Sign in to confirm you’re not a bot" error without using cookies, you can use the **Visitor Data** token.

1.  **Get Visitor Data**:
    *   Open YouTube in a browser (Incognito recommended).
    *   Open Developer Tools (F12) -> Console.
    *   Run: `window.yt.config_.VISITOR_DATA`
    *   Copy the output string (e.g., `Cgt...`).

2.  **Configure**:
    *   Set `YOUTUBE_VISITOR_DATA` environment variable with this string.

### 🛡️ Vercel / Datacenter IP Bypass (Recommended)

Vercel uses AWS Datacenter IPs, which YouTube blocks aggressively. If you see "Sign in to confirm you’re not a bot", you have two options:

1.  **Use Cookies** (Free, but requires maintenance): Set `YOUTUBE_COOKIES_CONTENT`.
2.  **Use a Residential Proxy** (Paid, scalable, no cookies):
    *   Get a residential proxy (e.g., from Smartproxy, Bright Data, IPRoyal).
    *   Set `YOUTUBE_PROXY_URL` environment variable:
        ```
        http://user:pass@host:port
        ```
    *   This masks Vercel's IP with a residential one, bypassing the block.

### YouTube Cookies (Legacy/Fallback)

For cloud environments where you can't upload files easily:

1.  **Export Cookies**:
    *   Install the **"Get cookies.txt LOCALLY"** extension for Chrome/Firefox.
    *   Go to `youtube.com` and ensure you are logged in.
    *   Click the extension icon and export as `cookies.txt` (Netscape format).

2.  **Encode**:
    *   Convert the file content to Base64 (to avoid newline issues in env vars).
    *   **Mac/Linux**: `base64 -i cookies.txt`
    *   **Windows**: Use an online Base64 encoder or PowerShell.

3.  **Configure**:
    *   Copy the Base64 string.
    *   Set `YOUTUBE_COOKIES_CONTENT` environment variable with this string.

---

## 🔒 Privacy & Security

- ✅ No user data collection
- ✅ All processing happens locally or on your server
- ✅ No account required
- ✅ History stored locally in your browser
- ✅ No tracking or analytics

---

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is maintained by the Livingseed Media Team for ministry use.

---

## 👥 Support

Need help? Have questions?

- 📧 Email: [support@livingseed.org](mailto:support@livingseed.org)
- 🌐 Website: [livingseed.org](https://livingseed.org)

---

## 🙏 Acknowledgments

- Built with love by the [Livingseed Media Team](https://livingseed.org)
- Powered by [FastAPI](https://fastapi.tiangolo.com/)
- Icons by [Lucide](https://lucide.dev/)

---

<div align="center">
  <p>Made with ❤️ for the ministry community</p>
  <p>© 2025 Livingseed. All rights reserved.</p>
</div>
