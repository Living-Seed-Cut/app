import os
import re
import logging
import asyncio
import hashlib
import time
import uuid
import subprocess
import base64
import pickle
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, parse_qs
import threading
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import iso8601
try:
    from yt_dlp import YoutubeDL
except ImportError:
    raise ImportError("yt-dlp is required. Install with: pip install yt-dlp")
try:
    from mutagen.easyid3 import EasyID3
    from mutagen.mp3 import MP3
    METADATA_AVAILABLE = True
except ImportError:
    METADATA_AVAILABLE = False
import config
from utils.ffmpeg_utils import get_ffmpeg_path, check_ffmpeg_available, get_ffmpeg_version
from models.requests import ExtractionRequest
logger = logging.getLogger(__name__)
job_storage: Dict[str, Dict[str, Any]] = {}
file_storage: Dict[str, Dict[str, Any]] = {}
cache_storage: Dict[str, Dict[str, Any]] = {}
job_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)
CLIENT_SECRETS_FILE = 'client_secrets.json'
CREDENTIALS_PICKLE_FILE = 'token.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
ENV_CLIENT_SECRETS = 'YOUTUBE_CLIENT_SECRETS_JSON'
ENV_TOKEN_PICKLE = 'YOUTUBE_TOKEN_PICKLE_BASE64' 
def _extract_video_id(url: str) -> str:
    if 'v=' in url:
        query = urlparse(url).query
        video_id = parse_qs(query).get('v')
        if video_id:
            return video_id[0]
    match = re.search(r'(?:youtu\.be/|embed/|v/|watch\?v=|&v=)([^#\&\?]*).*', url)
    if match and len(match.group(1)) == 11:
        return match.group(1)
    raise ValueError("Invalid YouTube URL format.")
def _convert_iso_duration_to_seconds(iso_duration: str) -> int:
    try:
        duration = iso8601.parse_duration(iso_duration)
        return int(duration.total_seconds())
    except Exception:
        return 0
class YoutubeAPI:
    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir if temp_dir is not None else config.TEMP_DIR
        self._prepare_secrets_and_token()
        self.youtube = self._get_authenticated_service()
    def _prepare_secrets_and_token(self):
        global CLIENT_SECRETS_FILE
        global CREDENTIALS_PICKLE_FILE
        client_secrets_content = os.environ.get(ENV_CLIENT_SECRETS)
        if client_secrets_content:
            secrets_path = os.path.join(self.temp_dir, CLIENT_SECRETS_FILE)
            with open(secrets_path, 'w') as f:
                f.write(client_secrets_content)
            CLIENT_SECRETS_FILE = secrets_path
            logger.info("Loaded client secrets from environment variable.")
        token_base64 = os.environ.get(ENV_TOKEN_PICKLE)
        if token_base64:
            token_pickle_content = base64.b64decode(token_base64)
            token_path = os.path.join(self.temp_dir, CREDENTIALS_PICKLE_FILE)
            with open(token_path, 'wb') as f:
                f.write(token_pickle_content)
            CREDENTIALS_PICKLE_FILE = token_path
            logger.info("Loaded token pickle from environment variable.")
    def _get_authenticated_service(self):
        creds = None
        if os.path.exists(CREDENTIALS_PICKLE_FILE):
            with open(CREDENTIALS_PICKLE_FILE, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Failed to refresh token: {e}. Starting full OAuth flow.")
                    creds = self._run_oauth_flow()
            else:
                creds = self._run_oauth_flow()
            with open(CREDENTIALS_PICKLE_FILE, 'wb') as token:
                pickle.dump(creds, token)
        return build('youtube', 'v3', credentials=creds)
    def _run_oauth_flow(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, SCOPES)
        return flow.run_local_server(port=0)
class AudioSnippetExtractor(YoutubeAPI):
    SUPPORTED_FORMATS = {'mp3', 'wav', 'mp4'}
    TIME_PATTERNS = [
        r'^\d{1,2}:\d{2}:\d{2}$',
        r'^\d{1,2}:\d{2}$',
        r'^\d+$'
    ]
    def __init__(self, temp_dir: Optional[str] = None, timeout: int = config.PROCESSING_TIMEOUT):
        self.temp_dir = temp_dir or config.TEMP_DIR
        YoutubeAPI.__init__(self, temp_dir=self.temp_dir)
        self.timeout = timeout
        self.cleanup_thread = None
        self.stop_cleanup = False
        self.proxy_url = config.YOUTUBE_PROXY_URL
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info(f"Initialized AudioSnippetExtractor with temp_dir: {self.temp_dir}")
        if self.proxy_url:
            logger.info("Using configured proxy for YouTube requests")
    def start_cleanup_thread(self):
        if self.cleanup_thread is None:
            self.stop_cleanup = False
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            self.cleanup_thread.start()
            logger.info("Started automatic cleanup thread")
    def stop_cleanup_thread(self):
        self.stop_cleanup = True
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            try:
                self.cleanup_thread.join(timeout=2)
                if self.cleanup_thread.is_alive():
                    logger.warning("Cleanup thread did not stop gracefully, continuing shutdown...")
            except Exception as e:
                logger.error(f"Error stopping cleanup thread: {e}")
        logger.info("Stopped automatic cleanup thread")
    def _cleanup_worker(self):
        while not self.stop_cleanup:
            try:
                self._perform_cleanup()
                time.sleep(config.CLEANUP_INTERVAL)
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
                time.sleep(60)
    def _perform_cleanup(self):
        logger.info("Starting automatic cleanup...")
        current_time = datetime.now()
        files_to_remove = []
        for file_id, file_info in file_storage.items():
            try:
                created_at = datetime.fromisoformat(file_info['created_at'])
                age_hours = (current_time - created_at).total_seconds() / 3600
                if age_hours > config.FILE_RETENTION_HOURS:
                    files_to_remove.append(file_id)
                    logger.info(f"Marking file {file_id} for cleanup (age: {age_hours:.1f} hours)")
                elif not os.path.exists(file_info['path']):
                    files_to_remove.append(file_id)
                    logger.info(f"Marking file {file_id} for cleanup (file not found on disk)")
            except Exception as e:
                logger.error(f"Error checking file {file_id}: {e}")
                files_to_remove.append(file_id)
        for file_id in files_to_remove:
            try:
                file_info = file_storage[file_id]
                if os.path.exists(file_info['path']):
                    os.remove(file_info['path'])
                    logger.info(f"Removed old file: {file_info['path']}")
                del file_storage[file_id]
            except Exception as e:
                logger.error(f"Failed to remove file {file_id}: {e}")
        jobs_to_remove = []
        for job_id, job_info in job_storage.items():
            try:
                created_at = datetime.fromisoformat(job_info['created_at'])
                age_hours = (current_time - created_at).total_seconds() / 3600
                if age_hours > config.FILE_RETENTION_HOURS:
                    jobs_to_remove.append(job_id)
                    logger.info(f"Marking job {job_id} for cleanup (age: {age_hours:.1f} hours)")
            except Exception as e:
                logger.error(f"Error checking job {job_id}: {e}")
                jobs_to_remove.append(job_id)
        for job_id in jobs_to_remove:
            try:
                del job_storage[job_id]
                logger.info(f"Removed old job: {job_id}")
            except Exception as e:
                logger.error(f"Failed to remove job {job_id}: {e}")
        if len(file_storage) > config.MAX_FILES:
            sorted_files = sorted(
                file_storage.items(),
                key=lambda x: datetime.fromisoformat(x[1]['created_at'])
            )
            files_to_remove = sorted_files[:len(file_storage) - config.MAX_FILES]
            for file_id, file_info in files_to_remove:
                try:
                    if os.path.exists(file_info['path']):
                        os.remove(file_info['path'])
                        logger.info(f"Removed excess file: {file_info['path']}")
                    del file_storage[file_id]
                except Exception as e:
                    logger.error(f"Failed to remove excess file {file_id}: {e}")
        cache_keys_to_remove = []
        current_time = datetime.now()
        for cache_key, cache_info in cache_storage.items():
            cache_age = (current_time - cache_info['created_at']).total_seconds() / 3600
            if cache_age > config.CACHE_RETENTION_HOURS:
                cache_keys_to_remove.append(cache_key)
                try:
                    if os.path.exists(cache_info['path']):
                        os.remove(cache_info['path'])
                except Exception as e:
                    logger.warning(f"Failed to remove cached file: {e}")
        for cache_key in cache_keys_to_remove:
            del cache_storage[cache_key]
        logger.info(f"Cleanup completed. Files: {len(file_storage)}, Jobs: {len(job_storage)}, Cache: {len(cache_storage)}")
    def _validate_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            youtube_domains = ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com']
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            if not any(domain in parsed.netloc.lower() for domain in youtube_domains):
                logger.warning(f"URL may not be a YouTube URL: {url}")
            return True
        except Exception as e:
            logger.error(f"URL validation failed: {e}")
            raise ValueError("Please enter a valid YouTube URL")
    def _parse_time(self, time_str: str) -> int:
        if not any(re.match(pattern, time_str.strip()) for pattern in self.TIME_PATTERNS):
            raise ValueError("Please enter a valid time format (e.g., 30, 0:30, 1:30, or 1:30:45)")
        time_str = time_str.strip()
        if time_str.isdigit():
            return int(time_str)
        parts = time_str.split(':')
        if len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        elif len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        else:
            raise ValueError("Please enter a valid time format")
    def _validate_time_range(self, start_time: str, end_time: str) -> Tuple[int, int]:
        start_seconds = self._parse_time(start_time)
        end_seconds = self._parse_time(end_time)
        if start_seconds >= end_seconds:
            raise ValueError("End time must be greater than start time")
        if start_seconds < 0 or end_seconds < 0:
            raise ValueError("Time values cannot be negative")
        return start_seconds, end_seconds
    def _sanitize_filename(self, filename: str) -> str:
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        sanitized = re.sub(invalid_chars, '_', filename)
        if len(sanitized) > 200:
            sanitized = sanitized[:200]
        sanitized = sanitized.strip(' .')
        if not sanitized:
            sanitized = f"audio_snippet_{int(time.time())}"
        return sanitized
    def _generate_cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    def _get_cached_audio(self, url: str) -> Optional[str]:
        if not config.CACHE_ENABLED:
            return None
        cache_key = self._generate_cache_key(url)
        cache_info = cache_storage.get(cache_key)
        if not cache_info:
            return None
        cache_age = (datetime.now() - cache_info['created_at']).total_seconds() / 3600
        if cache_age > config.CACHE_RETENTION_HOURS:
            try:
                if os.path.exists(cache_info['path']):
                    os.remove(cache_info['path'])
                del cache_storage[cache_key]
            except Exception as e:
                logger.warning(f"Failed to remove expired cache: {e}")
            return None
        if not os.path.exists(cache_info['path']):
            del cache_storage[cache_key]
            return None
        logger.info(f"Using cached audio file for: {url}")
        return cache_info['path']
    def _cache_audio_file(self, url: str, file_path: str):
        if not config.CACHE_ENABLED:
            return
        cache_key = self._generate_cache_key(url)
        cache_storage[cache_key] = {
            'path': file_path,
            'created_at': datetime.now(),
            'url': url
        }
        logger.info(f"Cached audio file for: {url}")
    def _insert_metadata(self, filepath: str, topic: Optional[str], preacher: Optional[str]) -> None:
        if not METADATA_AVAILABLE:
            logger.warning("Metadata insertion not available - mutagen not installed")
            return
        file_ext = filepath[filepath.rfind(".")+1:].lower()
        try:
            if file_ext == "mp3":
                audio = MP3(filepath, ID3=EasyID3)
                if topic:
                    audio["title"] = topic
                if preacher:
                    audio["artist"] = preacher
                audio.save()
                logger.info(f"Successfully inserted MP3 metadata: title='{topic}', artist='{preacher}'")
            elif file_ext == "mp4":
                logger.info(f"MP4 metadata insertion not yet implemented for: title='{topic}', preacher='{preacher}'")
            else:
                raise ValueError(f"Metadata can only be added to MP3 and MP4 files, not {file_ext}")
        except Exception as e:
            logger.error(f"Failed to insert metadata: {e}")
            raise ValueError("Failed to add metadata to the file")
    def check_dependencies(self) -> Dict[str, bool]:
        deps = {}
        deps['ffmpeg'] = check_ffmpeg_available()
        if deps['ffmpeg']:
            version = get_ffmpeg_version()
            if version:
                logger.info(f"FFmpeg detected: {version}")
        try:
            YoutubeDL()
            deps['yt_dlp'] = True
        except Exception:
            deps['yt_dlp'] = False
        return deps
    def _extract_info_sync(self, url: str) -> Dict[str, Any]:
        video_id = _extract_video_id(url)
        request = self.youtube.videos().list(
            part="snippet,contentDetails",
            id=video_id
        )
        response = request.execute()
        if not response.get('items'):
            raise RuntimeError("Video not found or inaccessible via the API.")
        item = response['items'][0]
        snippet = item['snippet']
        content_details = item['contentDetails']
        iso_duration = content_details.get('duration', 'PT0S')
        duration_seconds = _convert_iso_duration_to_seconds(iso_duration)
        return {
            'title': snippet.get('title', 'Unknown'),
            'duration': duration_seconds,
            'uploader': snippet.get('channelTitle', 'Unknown'),
            'upload_date': snippet.get('publishedAt', 'Unknown'),
            'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url')
        }
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        logger.info(f"Extracting video info for: {url}")
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: self._extract_info_sync(url))
        except Exception as e:
            logger.error(f"Failed to extract video info: {e}")
            raise RuntimeError("Unable to access this YouTube video. Please check the URL and try again.")
    async def extract_snippet_async(self, job_id: str, request: ExtractionRequest) -> str:
        async with job_semaphore:
            try:
                job_storage[job_id]['status'] = 'processing'
                job_storage[job_id]['progress'] = 'Validating inputs...'
                job_storage[job_id]['percent'] = 5.0
                self._validate_url(request.url)
                deps = self.check_dependencies()
                if not all(deps.values()):
                    missing_deps = [k for k, v in deps.items() if not v]
                    raise RuntimeError(f"Missing required software: {', '.join(missing_deps)}. Please contact support.")
                job_storage[job_id]['progress'] = 'Getting video information...'
                job_storage[job_id]['percent'] = 10.0
                video_info = None
                video_info_failed = False
                try:
                    video_info = await self.get_video_info(request.url)
                except Exception as e:
                    logger.warning(f"Failed to get video info (API access error): {e}. Proceeding with defaults...")
                    video_info_failed = True
                    video_info = {
                        'title': f'youtube_audio_{int(time.time())}',
                        'duration': 0,
                        'uploader': 'Unknown',
                        'upload_date': 'Unknown',
                        'thumbnail': None
                    }
                video_duration = int(video_info.get('duration') or 0)
                if not video_info_failed and request.extract_full and video_duration > config.MAX_VIDEO_DURATION:
                    file_type = "video" if request.output_format == 'mp4' else "audio"
                    raise RuntimeError(f"Cannot extract full {file_type} from videos longer than {config.MAX_VIDEO_DURATION//3600} hours. Please specify a time range instead.")
                if request.extract_full:
                    start_seconds = 0
                    end_seconds = video_duration or None
                else:
                    normalized_start = request.start_time.strip() if request.start_time else '0:00'
                    start_seconds, end_seconds = self._validate_time_range(normalized_start, request.end_time)
                    snippet_duration = end_seconds - start_seconds
                    if snippet_duration > config.MAX_SNIPPET_DURATION:
                        file_type = "video" if request.output_format == 'mp4' else "audio"
                        raise RuntimeError(f"{file_type.capitalize()} snippet cannot be longer than {config.MAX_SNIPPET_DURATION//3600} hours.")
                if not request.filename:
                    filename = self._sanitize_filename(video_info['title'][:50])
                else:
                    filename = self._sanitize_filename(request.filename)
                file_id = str(uuid.uuid4())
                output_filename = f"{file_id}_{filename}.{request.output_format}"
                output_path = os.path.join(self.temp_dir, output_filename)
                downloaded_file = None
                if request.output_format in ['mp3', 'wav']:
                    cached_file = self._get_cached_audio(request.url)
                    if cached_file:
                        job_storage[job_id]['progress'] = 'Using cached audio...'
                        job_storage[job_id]['percent'] = 70.0
                        downloaded_file = cached_file
                if not downloaded_file:
                    if request.output_format == 'mp4':
                        job_storage[job_id]['progress'] = 'Downloading video...'
                        job_storage[job_id]['percent'] = 15.0
                        downloaded_file = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            lambda: self._download_video(request.url, job_id, start_seconds, end_seconds)
                        )
                    else:
                        job_storage[job_id]['progress'] = 'Downloading audio...'
                        job_storage[job_id]['percent'] = 15.0
                        temp_basename = os.path.join(self.temp_dir, f"temp_audio_{job_id}")
                        def _download_audio():
                            def progress_hook(d):
                                if d['status'] == 'downloading':
                                    if '_percent_str' in d:
                                        try:
                                            percent_str = d['_percent_str'].replace('%', '').strip()
                                            download_percent = float(percent_str)
                                            total_percent = 15.0 + (download_percent * 0.55)
                                            job_storage[job_id]['percent'] = min(total_percent, 70.0)
                                            job_storage[job_id]['progress'] = f'Downloading audio... {download_percent:.1f}%'
                                        except (ValueError, KeyError):
                                            pass
                                    elif '_eta_str' in d:
                                        job_storage[job_id]['progress'] = f'Downloading audio... ETA: {d["_eta_str"]}'
                                elif d['status'] == 'finished':
                                    job_storage[job_id]['percent'] = 70.0
                                    job_storage[job_id]['progress'] = 'Download completed, processing...'
                            ydl_opts = {
                                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                                'outtmpl': f'{temp_basename}.%(ext)s',
                                'quiet': True,
                                'progress_hooks': [progress_hook],
                                'concurrent_fragment_downloads': config.YTDL_CONCURRENT_FRAGMENTS,
                                'buffersize': 1024 * 1024,
                                'http_chunk_size': 10485760,
                                'retries': 3,
                                'fragment_retries': 3,
                                'skip_unavailable_fragments': True,
                                'socket_timeout': 20,
                                'nocheckcertificate': True,
                                'source_address': '0.0.0.0',
                                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'referer': 'https://www.youtube.com/',
                                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                                'postprocessors': [{
                                    'key': 'FFmpegExtractAudio',
                                    'preferredcodec': 'm4a',
                                    'preferredquality': '192',
                                }],
                            }
                            if self.proxy_url:
                                ydl_opts['proxy'] = self.proxy_url
                            if config.YOUTUBE_COOKIES_PATH and os.path.exists(config.YOUTUBE_COOKIES_PATH):
                                ydl_opts['cookiefile'] = config.YOUTUBE_COOKIES_PATH
                            with YoutubeDL(ydl_opts) as ydl:
                                ydl.download([request.url])
                            return f"{temp_basename}.m4a"
                        loop = asyncio.get_event_loop()
                        downloaded_file = await loop.run_in_executor(None, _download_audio)
                        self._cache_audio_file(request.url, downloaded_file)
                if request.output_format == 'mp4':
                    job_storage[job_id]['progress'] = 'Processing video...'
                    job_storage[job_id]['percent'] = 75.0
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self._process_video(downloaded_file, output_path, job_id, start_seconds, end_seconds, request.extract_full)
                    )
                else:
                    job_storage[job_id]['progress'] = 'Processing audio...'
                    job_storage[job_id]['percent'] = 75.0
                def _trim_audio():
                    codec_map = {
                        'mp3': 'libmp3lame',
                        'wav': 'pcm_s16le',
                        'flac': 'flac',
                        'aac': 'aac'
                    }
                    codec = codec_map.get(request.output_format, 'libmp3lame')
                    ffmpeg_path = get_ffmpeg_path()
                    ffmpeg_command = [
                        ffmpeg_path, '-y', '-i', downloaded_file,
                        '-c:a', codec,
                        '-avoid_negative_ts', 'make_zero',
                        '-threads', str(config.FFMPEG_THREADS),
                        '-preset', 'ultrafast',
                        '-progress', 'pipe:1'
                    ]
                    if not request.extract_full:
                        ffmpeg_command.insert(4, '-ss')
                        ffmpeg_command.insert(5, str(start_seconds))
                        ffmpeg_command.insert(6, '-t')
                        ffmpeg_command.insert(7, str(end_seconds - start_seconds))
                    if request.output_format == 'mp3':
                        ffmpeg_command.extend(['-b:a', '192k'])
                    elif request.output_format == 'wav':
                        ffmpeg_command.extend(['-ar', '44100'])
                    ffmpeg_command.append(output_path)
                    process = subprocess.Popen(
                        ffmpeg_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    snippet_duration = None
                    if request.extract_full:
                        try:
                            snippet_duration = float(video_info.get('duration') or 0)
                        except Exception:
                            snippet_duration = None
                    else:
                        snippet_duration = end_seconds - start_seconds
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line.startswith('out_time_ms='):
                            try:
                                time_ms = int(line.split('=')[1])
                                time_seconds = time_ms / 1000000.0
                                if snippet_duration and snippet_duration > 0:
                                    trim_percent = min((time_seconds / snippet_duration) * 100, 100)
                                    total_percent = 75.0 + (trim_percent * 0.20)
                                    job_storage[job_id]['percent'] = min(total_percent, 95.0)
                                    job_storage[job_id]['progress'] = f'Processing audio... {trim_percent:.1f}%'
                                else:
                                    job_storage[job_id]['progress'] = 'Processing audio...'
                            except (ValueError, IndexError):
                                pass
                    process.wait(timeout=self.timeout)
                    if process.returncode != 0:
                        raise RuntimeError("Failed to process the audio file. Please try again.")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _trim_audio)
                if os.path.exists(downloaded_file):
                    os.remove(downloaded_file)
                if not os.path.exists(output_path):
                    file_type = "video" if request.output_format == 'mp4' else "audio"
                    raise RuntimeError(f"Failed to create the {file_type} file. Please try again.")
                if request.output_format in ['mp3', 'mp4'] and METADATA_AVAILABLE:
                    if request.topic or request.preacher:
                        try:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, self._insert_metadata, output_path, request.topic, request.preacher)
                            logger.info(f"Inserted metadata for {output_path}: topic='{request.topic}', preacher='{request.preacher}'")
                        except Exception as e:
                            logger.warning(f"Failed to insert metadata: {e}")
                file_size = os.path.getsize(output_path)
                mime_type = f"video/{request.output_format}" if request.output_format == 'mp4' else f"audio/{request.output_format}"
                file_storage[file_id] = {
                    'path': output_path,
                    'filename': f"{filename}.{request.output_format}",
                    'size': file_size,
                    'created_at': datetime.now().isoformat(),
                    'mime_type': mime_type
                }
                job_storage[job_id]['status'] = 'completed'
                job_storage[job_id]['progress'] = 'Extraction completed'
                job_storage[job_id]['percent'] = 100.0
                job_storage[job_id]['completed_at'] = datetime.now().isoformat()
                job_storage[job_id]['file_id'] = file_id
                job_storage[job_id]['file_size'] = file_size
                if request.extract_full:
                    try:
                        job_storage[job_id]['duration'] = float(video_info.get('duration') or 0)
                    except Exception:
                        job_storage[job_id]['duration'] = None
                else:
                    job_storage[job_id]['duration'] = end_seconds - start_seconds
                logger.info(f"Job {job_id} completed successfully. File: {output_path}")
                return file_id
            except Exception as e:
                logger.error(f"Job {job_id} failed: {e}")
                job_storage[job_id]['status'] = 'failed'
                error_message = str(e)
                print("debugging issue: ", str(e))
                file_type = "video" if request.output_format == 'mp4' else "audio"
                if "FFmpeg failed" in error_message or "process" in error_message.lower():
                    error_message = f"Failed to process the {file_type} file. Please try again."
                elif "video information" in error_message or "access" in error_message.lower():
                    error_message = "Unable to access this YouTube video. Please check the URL and try again."
                elif "metadata" in error_message.lower():
                    error_message = f"Failed to add metadata to the {file_type} file."
                elif "dependencies" in error_message.lower():
                    error_message = "System configuration error. Please contact support."
                elif "timeout" in error_message.lower():
                    error_message = f"Processing took too long. Please try with a shorter {file_type} snippet."
                elif "network" in error_message.lower() or "connection" in error_message.lower():
                    error_message = "Network connection error. Please check your internet and try again."
                else:
                    error_message = "An unexpected error occurred. Please try again."
                job_storage[job_id]['error'] = error_message
                job_storage[job_id]['completed_at'] = datetime.now().isoformat()
                raise
    def _download_video(self, url: str, job_id: str, start_seconds: int = None, end_seconds: int = None) -> str:
        def progress_hook(d):
            if d['status'] == 'downloading':
                if '_percent_str' in d:
                    try:
                        percent_str = d['_percent_str'].replace('%', '').strip()
                        download_percent = float(percent_str)
                        total_percent = 15.0 + (download_percent * 0.55)
                        job_storage[job_id]['percent'] = min(total_percent, 70.0)
                        job_storage[job_id]['progress'] = f'Downloading video... {download_percent:.1f}%'
                    except (ValueError, KeyError):
                        pass
                elif '_eta_str' in d:
                    job_storage[job_id]['progress'] = f'Downloading video... ETA: {d["_eta_str"]}'
            elif d['status'] == 'finished':
                job_storage[job_id]['percent'] = 70.0
                job_storage[job_id]['progress'] = 'Download completed, processing...'
        temp_basename = os.path.join(self.temp_dir, f"temp_video_{job_id}")
        ydl_opts = {
            'format': 'best[ext=mp4]/best[height<=720]/best',
            'outtmpl': f'{temp_basename}.%(ext)s',
            'quiet': True,
            'progress_hooks': [progress_hook],
            'concurrent_fragment_downloads': config.YTDL_CONCURRENT_FRAGMENTS,
            'buffersize': 1024 * 1024,
            'http_chunk_size': 10485760,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'socket_timeout': 20,
            'nocheckcertificate': True,
            'source_address': '0.0.0.0',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        }
        if self.proxy_url:
            ydl_opts['proxy'] = self.proxy_url
        if config.YOUTUBE_COOKIES_PATH and os.path.exists(config.YOUTUBE_COOKIES_PATH):
            ydl_opts['cookiefile'] = config.YOUTUBE_COOKIES_PATH
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        downloaded_file = None
        for ext in ['mp4', 'webm', 'mkv']:
            potential_file = f"{temp_basename}.{ext}"
            if os.path.exists(potential_file):
                downloaded_file = potential_file
                break
        if not downloaded_file:
            raise RuntimeError("Failed to download video file")
        return downloaded_file
    def _process_video(self, input_file: str, output_path: str, job_id: str, start_seconds: int = None, end_seconds: int = None, extract_full: bool = False) -> None:
        ffmpeg_path = get_ffmpeg_path()
        ffmpeg_command = [
            ffmpeg_path, '-y', '-i', input_file,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '23',
            '-avoid_negative_ts', 'make_zero',
            '-threads', str(config.FFMPEG_THREADS),
            '-progress', 'pipe:1'
        ]
        if not extract_full and start_seconds is not None and end_seconds is not None:
            ffmpeg_command.insert(4, '-ss')
            ffmpeg_command.insert(5, str(start_seconds))
            ffmpeg_command.insert(6, '-t')
            ffmpeg_command.insert(7, str(end_seconds - start_seconds))
        ffmpeg_command.append(output_path)
        process = subprocess.Popen(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line.startswith('out_time_ms='):
                try:
                    time_ms = int(line.split('=')[1])
                    time_seconds = time_ms / 1000000.0
                    if not extract_full and start_seconds is not None and end_seconds is not None:
                        snippet_duration = end_seconds - start_seconds
                        if snippet_duration > 0:
                            progress_percent = min(75.0 + (time_seconds / snippet_duration) * 20.0, 95.0)
                            job_storage[job_id]['percent'] = progress_percent
                            job_storage[job_id]['progress'] = f'Processing video... {progress_percent:.1f}%'
                except (ValueError, IndexError):
                    pass
        if process.returncode != 0:
            raise RuntimeError("FFmpeg processing failed")
extractor = AudioSnippetExtractor()