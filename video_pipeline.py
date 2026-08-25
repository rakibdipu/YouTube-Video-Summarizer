#!/usr/bin/env python3
"""
Video Processing Pipeline - Fast & Dynamic Progress Edition
Uses faster-whisper with multi-threading, live segment progress, and async reporting.
"""

import os, sys, subprocess, argparse, shutil, re
from pathlib import Path
import time, hashlib, json
from typing import Optional, List

# ── Force UTF-8 Output on Windows ──────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Colors ───────────────────────────────────────────────────────────────────
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    ORANGE = "\033[38;5;208m"; AMBER = "\033[38;5;214m"; YELLOW = "\033[38;5;220m"
    RESET = Style.RESET_ALL;   BOLD = Style.BRIGHT;      DIM = Style.DIM
    RED = Fore.RED;            GREEN = Fore.GREEN;        WHITE = Fore.WHITE
    CYAN = Fore.CYAN
except ImportError:
    ORANGE=AMBER=YELLOW=RESET=BOLD=DIM=RED=GREEN=WHITE=CYAN=""

LOCAL_OUTPUT = r"C:\video_sum_tmp"

def _line(w=60): return "─" * w
def banner(t):
    p = max(0, (60-len(t)-2)//2)
    print(f"\n{BOLD}{ORANGE}{'='*60}\n{'='*p} {AMBER}{t}{ORANGE} {'='*p}\n{'='*60}{RESET}\n")
def section(t):
    print(f"\n{BOLD}{ORANGE}{_line()}\n  {AMBER}>>  {WHITE}{t}{RESET}\n{ORANGE}{_line()}{RESET}")
def step(m):  print(f"{AMBER}  * {RESET}{m}")
def ok(m):    print(f"{GREEN}  + {RESET}{m}")
def warn(m):  print(f"{YELLOW}  ! {RESET}{m}")
def err(m):   print(f"{RED}  x {RESET}{m}")
def info(m):  print(f"{CYAN}  i {RESET}{m}")
def stat_row(l,v): print(f"    {AMBER}{l:<22}{RESET}{WHITE}{v}{RESET}")
def format_time(s):
    try:
        s = float(s)
        m, s = divmod(int(s), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    except Exception:
        return "00:00"
def strip_ansi(t): return re.sub(r'\x1b\[[0-9;]*m','',str(t))

import yt_dlp
from imageio_ffmpeg import get_ffmpeg_exe
from faster_whisper import WhisperModel
from transformers import pipeline as hf_pipeline, BartTokenizer
import torch
from tqdm import tqdm


class VideoProcessor:
    def __init__(self, whisper_model="base", summarizer_model="facebook/bart-large-cnn",
                 progress_cb=None):
        self.progress_cb = progress_cb or (lambda s, d, p=None: None)
        banner("Initializing VideoProcessor")

        _src = get_ffmpeg_exe()
        _dir = os.path.dirname(_src)
        _std = os.path.join(_dir, "ffmpeg.exe")
        if not os.path.exists(_std):
            step("Copying ffmpeg -> ffmpeg.exe for yt-dlp")
            try:
                shutil.copy2(_src, _std)
            except Exception:
                pass
        self.ffmpeg_dir = _dir

        # Multi-threaded faster-whisper (CPU optimized)
        cpu_count = os.cpu_count() or 4
        threads = min(8, max(2, cpu_count - 2))
        step(f"Loading Whisper model  -> {AMBER}{whisper_model}{RESET} (Threads: {threads})")
        self.progress_cb("init", f"Loading Whisper model ({whisper_model})...", 5)
        
        self.whisper_model = WhisperModel(
            whisper_model, 
            device="cpu", 
            compute_type="int8", 
            cpu_threads=threads,
            num_workers=2
        )
        ok(f"Whisper '{whisper_model}' loaded successfully")

        # Summarizer
        device = 0 if torch.cuda.is_available() else -1
        device_name = f"{GREEN}GPU{RESET}" if device == 0 else f"{AMBER}CPU{RESET}"
        step(f"Compute device         -> {device_name}")
        step(f"Loading summarizer     -> {AMBER}{summarizer_model}{RESET}")
        self.progress_cb("init", "Loading BART summarizer...", 8)
        self.summarizer = hf_pipeline("summarization", model=summarizer_model, device=device)
        self.tokenizer  = BartTokenizer.from_pretrained(summarizer_model)
        ok("Summarizer loaded")

        print(f"\n{BOLD}{ORANGE}{'─'*60}{RESET}")
        ok(f"{BOLD}VideoProcessor ready!{RESET}\n")

    def _hash(self, src): return hashlib.md5(src.encode()).hexdigest()[:10]

    def download_video(self, url, output_path="downloaded_video.mp4"):
        section("Downloading Video")
        step(f"Source -> {AMBER}{url}{RESET}")
        self.progress_cb("download", "Connecting to video...", 10)

        # Progress hook for yt-dlp
        def ytdl_hook(d):
            if d.get('status') == 'downloading':
                p_str = d.get('_percent_str', '0%')
                clean_p = strip_ansi(p_str).strip()
                eta_str = d.get('_eta_str', '')
                speed_str = d.get('_speed_str', '')
                msg = f"Downloading video: {clean_p} ({speed_str})"
                self.progress_cb("download", msg, 20)

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_path,
            "merge_output_format": "mp4",
            "ffmpeg_location": self.ffmpeg_dir,
            "quiet": True,
            "no_warnings": True,
            "extractor_retries": 5,
            "retries": 10,
            "fragment_retries": 10,
            "progress_hooks": [ytdl_hook]
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title","Unknown")
                dur   = info.get("duration")
                step(f"Title    -> {AMBER}{title}{RESET}")
                if dur: step(f"Duration -> {AMBER}{format_time(dur)}{RESET}")
                self.progress_cb("download", f"Downloading: {title[:40]}...", 15)
                ydl.download([url])
            ok(f"Downloaded to: {output_path}\n")
            return output_path
        except Exception as e:
            err(f"Download failed: {strip_ansi(e)}")
            raise

    def extract_audio(self, video_path, audio_path="extracted_audio.wav"):
        section("Extracting Audio")
        self.progress_cb("audio", "Extracting high-quality audio track...", 35)
        try:
            cmd = [get_ffmpeg_exe(), "-y", "-i", video_path,
                   "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                   audio_path]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"FFmpeg: {r.stderr}")
            ok(f"Audio extracted to: {audio_path}\n")
            self.progress_cb("audio", "Audio extraction complete!", 40)
            return audio_path
        except Exception as e:
            err(f"Audio extraction failed: {e}"); raise

    def transcribe(self, audio_path, language=None):
        section("Transcribing Audio")
        info("Using faster-whisper with live segment updates...")
        self.progress_cb("transcribe", "Starting AI transcription...", 42)

        start = time.time()
        segments, meta = self.whisper_model.transcribe(
            audio_path,
            language=language,
            beam_size=1,
            word_timestamps=False,
        )

        total_dur = meta.duration if hasattr(meta, "duration") and meta.duration else 1.0
        detected_lang = meta.language if hasattr(meta, "language") else (language or "unknown")

        text_parts = []
        ts_parts   = []
        
        for seg in segments:
            text_parts.append(seg.text.strip())
            s = format_time(seg.start)
            e = format_time(seg.end)
            ts_parts.append(f"[{s} - {e}] {seg.text.strip()}")
            
            # Real-time progress updates for every segment!
            cur_time = seg.end
            sub_pct = min(75, 42 + int((cur_time / total_dur) * 33))
            msg = f"Transcribing: {format_time(cur_time)} / {format_time(total_dur)} ({int(cur_time/total_dur*100)}%)"
            self.progress_cb("transcribe", msg, sub_pct)

        transcript = " ".join(text_parts)
        timestamped = "\n".join(ts_parts)
        elapsed = time.time() - start
        word_count = len(transcript.split())

        ok(f"Transcription done in {elapsed:.1f}s")
        stat_row("Language:", detected_lang)
        stat_row("Words:",    str(word_count))
        print()

        self.progress_cb("transcribe", f"Transcription complete! ({word_count} words)", 75)
        return {
            "text": transcript, "timestamped_text": timestamped,
            "language": detected_lang, "duration": elapsed, "word_count": word_count,
        }

    def chunk_text(self, text, max_tokens=800):
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        chunks, i = [], 0
        while i < len(tokens):
            end = min(i + max_tokens, len(tokens))
            chunks.append(self.tokenizer.decode(tokens[i:end], skip_special_tokens=True))
            i = end
        return chunks

    def summarize(self, text, max_length=150, min_length=50):
        section("Summarizing")
        self.progress_cb("summarize", "Preparing text for AI summary...", 78)
        wc = len(text.split())
        if wc <= 60:
            self.progress_cb("summarize", "Summary complete!", 95)
            return text

        chunks   = self.chunk_text(text, 800)
        summaries = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            self.progress_cb("summarize", f"Summarizing section {i+1} of {total_chunks}...", 78 + int((i/total_chunks)*17))
            try:
                cw = len(chunk.split())
                s = self.summarizer(
                    chunk,
                    max_length=max(30, min(max_length, cw//2)),
                    min_length=max(10, min(min_length, cw//4)),
                    do_sample=False,
                    clean_up_tokenization_spaces=True,
                )[0]["summary_text"]
                summaries.append(s)
            except Exception as e:
                warn(f"Chunk {i+1} failed: {e}"); summaries.append(chunk)

        final = "\n\n".join(
            [f"• Key Point {i+1}:\n{s}" for i, s in enumerate(summaries)]
        ) if len(summaries) > 1 else summaries[0]
        
        ok("Summary done!\n")
        self.progress_cb("summarize", "Summary generation complete!", 95)
        return final

    def process_video(self, video_source, output_dir=LOCAL_OUTPUT,
                      keep_audio=False, keep_video=False,
                      language=None, max_summary_length=150, use_cache=True):

        banner("Video Processing Pipeline")
        src_hash = self._hash(video_source)
        run_dir  = os.path.join(output_dir, src_hash)
        Path(run_dir).mkdir(exist_ok=True, parents=True)
        cache_file = os.path.join(run_dir, "metadata.json")

        # Cache hit
        if use_cache and os.path.exists(cache_file):
            ok(f"Cache hit! ({src_hash})")
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["stats"]["cached"] = True
            self.progress_cb("done", "Loaded instantly from cache!", 100)
            return data

        # Download or use local file
        if video_source.startswith(("http://","https://","www.")):
            video_path = os.path.join(run_dir, "video.mp4")
            video_path = self.download_video(video_source, video_path)
            is_dl = True
        else:
            if not os.path.exists(video_source):
                raise FileNotFoundError(f"Not found: {video_source}")
            video_path = video_source; is_dl = False

        audio_path = os.path.join(run_dir, "audio.wav")
        audio_path = self.extract_audio(video_path, audio_path)

        tr  = self.transcribe(audio_path, language)
        summary = self.summarize(tr["text"], max_length=max_summary_length)

        # Save outputs
        transcript_path  = os.path.join(run_dir, "transcript.txt")
        timestamps_path  = os.path.join(run_dir, "timestamps.txt")
        summary_path     = os.path.join(run_dir, "summary.txt")
        markdown_path    = os.path.join(run_dir, "report.md")

        with open(transcript_path,  "w", encoding="utf-8") as f: f.write(tr["text"])
        with open(timestamps_path,  "w", encoding="utf-8") as f: f.write(tr["timestamped_text"])
        with open(summary_path,     "w", encoding="utf-8") as f: f.write(summary)

        wc   = tr["word_count"]
        sl   = len(summary.split())
        comp = (sl/wc*100) if wc > 0 else 0.0

        md = (f"# Video Analysis Report\n\n"
              f"**Source:** `{video_source}`  \n"
              f"**Language:** `{tr['language']}`  \n"
              f"**Compression:** `{comp:.1f}%`  \n"
              f"**Date:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n---\n\n"
              f"## Summary\n{summary}\n\n---\n\n"
              f"## Timestamped Transcript\n```\n{tr['timestamped_text']}\n```\n")
        with open(markdown_path, "w", encoding="utf-8") as f: f.write(md)

        results = {
            "transcript": transcript_path, "timestamps": timestamps_path,
            "summary": summary_path,       "markdown": markdown_path,
            "audio":   audio_path if keep_audio else None,
            "video":   video_path if keep_video or not is_dl else None,
            "stats": {"language": tr["language"], "word_count": wc,
                      "summary_length": sl, "compression": comp, "cached": False},
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        # Cleanup temp audio and downloaded video to save disk space
        if not keep_audio and os.path.exists(audio_path): 
            try: os.remove(audio_path)
            except Exception: pass
        if not keep_video and is_dl and os.path.exists(video_path): 
            try: os.remove(video_path)
            except Exception: pass

        banner("Done!")
        self.progress_cb("done", "Complete!", 100)
        return results


def main():
    if len(sys.argv) == 1:
        banner("Video Processing Pipeline")
        while True:
            url = input(f"{AMBER}URL or file path:{RESET} ").strip()
            if not url: break
            model = input(f"{AMBER}Model (tiny/base/small) [base]:{RESET} ").strip() or "base"
            proc = VideoProcessor(whisper_model=model)
            r = proc.process_video(url)
            section("Done"); stat_row("Summary:", r["summary"]); stat_row("Report:", r["markdown"])
            if input(f"\n{AMBER}Another? (y/n):{RESET} ").strip().lower() not in ("y","yes"): break
        return

    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--whisper-model", "-w", default="base")
    p.add_argument("--output-dir", "-o", default=LOCAL_OUTPUT)
    p.add_argument("--language", "-l")
    p.add_argument("--keep-audio", action="store_true")
    p.add_argument("--keep-video", action="store_true")
    p.add_argument("--max-summary-length", type=int, default=150)
    p.add_argument("--no-cache", action="store_true")
    a = p.parse_args()
    VideoProcessor(whisper_model=a.whisper_model).process_video(
        a.source, a.output_dir, a.keep_audio, a.keep_video,
        a.language, a.max_summary_length, not a.no_cache)

if __name__ == "__main__":
    main()