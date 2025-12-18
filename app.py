import os, uuid, subprocess, shutil
from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)
UPLOAD_DIR = "uploads"
OUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Image → Video</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;margin:24px;max-width:860px}
    .card{border:1px solid #e5e7eb;border-radius:12px;padding:16px}
    input,select,button{font-size:16px;padding:10px}
    button{cursor:pointer}
    .row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
    .muted{color:#6b7280}
  </style>
</head>
<body>
  <h2>Tạo video đổi ảnh (MP4)</h2>
  <div class="card">
    <form method="post" action="/make" enctype="multipart/form-data">
      <div class="row">
        <div>
          <div><b>Chọn nhiều ảnh</b></div>
          <input type="file" name="images" multiple accept="image/*" required>
        </div>
      </div>
      <br>
      <div class="row">
        <div>
          <div><b>Thời lượng mỗi ảnh (giây)</b></div>
          <input type="number" name="sec" value="2" min="1" max="10">
        </div>
        <div>
          <div><b>Tỉ lệ video</b></div>
          <select name="ratio">
            <option value="1080:1920">9:16 (TikTok)</option>
            <option value="1080:1080">1:1</option>
            <option value="1920:1080">16:9</option>
          </select>
        </div>
        <div>
          <div><b>Hiệu ứng</b></div>
          <select name="effect">
            <option value="kenburns">Zoom nhẹ (TikTok-style)</option>
            <option value="none">Không hiệu ứng</option>
          </select>
        </div>
      </div>
      <br>
      <button type="submit">Xuất video</button>
      <p class="muted">Upload ảnh → ghép thành video MP4.</p>
    </form>
  </div>
</body>
</html>
"""

@app.get("/")
def home():
    return render_template_string(HTML)

@app.post("/make")
def make():
    files = request.files.getlist("images")
    if not files:
        return "No images", 400

    sec = int(request.form.get("sec", 2))
    ratio = request.form.get("ratio", "1080:1920")
    effect = request.form.get("effect", "kenburns")
    w, h = map(int, ratio.split(":"))

    job = uuid.uuid4().hex
    job_dir = os.path.join(UPLOAD_DIR, job)
    os.makedirs(job_dir, exist_ok=True)

    paths = []
    for i, f in enumerate(files):
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            continue
        p = os.path.join(job_dir, f"{i:04d}{ext}")
        f.save(p)
        paths.append(p)

    if not paths:
        shutil.rmtree(job_dir, ignore_errors=True)
        return "No valid images (jpg/png/webp).", 400

    concat_path = os.path.join(job_dir, "list.txt")
    with open(concat_path, "w", encoding="utf-8") as fp:
        for p in paths:
            fp.write(f"file '{os.path.abspath(p)}'\n")
            fp.write(f"duration {sec}\n")
        fp.write(f"file '{os.path.abspath(paths[-1])}'\n")

    out_path = os.path.join(OUT_DIR, f"{job}.mp4")

    base = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    )
    vf = base
    if effect == "kenburns":
        vf = base + f",zoompan=z='min(zoom+0.0007,1.08)':d=1:s={w}x{h}:fps=30"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-vf", vf,
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        out_path
    ]

    try:
        subprocess.check_call(cmd)
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return f"FFmpeg failed: {e}", 500
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    return send_file(out_path, as_attachment=True, download_name="video.mp4")
