from flask import Flask, render_template, request, jsonify
from video_pipeline import VideoProcessor, LOCAL_OUTPUT, strip_ansi
import threading, webbrowser, os, time, uuid, re

app = Flask(__name__)
os.makedirs(LOCAL_OUTPUT, exist_ok=True)

# Global state
processor      = None
processor_lock = threading.Lock()
jobs           = {}   # job_id -> {status, stage, progress, pct, result, error}

def get_processor(model="base"):
    global processor
    with processor_lock:
        if processor is None or getattr(processor, "_model_name", None) != model:
            def dummy_cb(stage, detail, pct=None): pass
            processor = VideoProcessor(whisper_model=model, progress_cb=dummy_cb)
            processor._model_name = model
    return processor

def run_job(job_id, url, model):
    def cb(stage, detail, pct=None):
        jobs[job_id]["stage"]    = stage
        jobs[job_id]["progress"] = detail
        if pct is not None:
            jobs[job_id]["pct"]  = pct

    jobs[job_id]["status"] = "running"
    try:
        proc = get_processor(model)
        proc.progress_cb = cb

        results = proc.process_video(video_source=url, output_dir=LOCAL_OUTPUT, use_cache=True)

        with open(results["summary"],    "r", encoding="utf-8") as f: summary = f.read()
        with open(results["timestamps"], "r", encoding="utf-8") as f: timestamps = f.read()

        jobs[job_id]["status"]    = "done"
        jobs[job_id]["progress"]  = "Complete!"
        jobs[job_id]["pct"]       = 100
        jobs[job_id]["result"]    = {
            "summary":    summary,
            "timestamps": timestamps,
            "stats":      results["stats"],
        }
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"]  = strip_ansi(e)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/process", methods=["POST"])
def process():
    data  = request.json or {}
    url   = data.get("url", "").strip()
    model = data.get("model", "base")

    if not url:
        return jsonify({"error": "No URL"}), 400

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {
        "status": "pending", 
        "stage": "queued",
        "progress": "Starting...", 
        "pct": 5,
        "result": None, 
        "error": None
    }

    threading.Thread(target=run_job, args=(job_id, url, model), daemon=True).start()
    return jsonify({"job_id": job_id})

@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify(job)

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    print("\nStarting server on http://127.0.0.1:5000")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(port=5000, debug=False, threaded=True)