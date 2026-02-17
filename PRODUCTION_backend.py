from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pypdf import PdfReader
import subprocess
import zipfile
import shutil
from pathlib import Path
import uuid
import json
import time
import re
import traceback
import os
import base64

app = Flask(__name__)
CORS(app, origins=["*"])

TEMP_DIR = Path("temp_processing")
TEMP_DIR.mkdir(exist_ok=True)
jobs = {}


def extract_from_pdf(pdf_path):
    """
    Extract ACTUAL embedded code from PDF metadata fields.
    The PDF stores:
    - /RemotionCode   -> base64 encoded JSX composition
    - /ThreeJSCode    -> base64 encoded Three.js code  
    - /OrchestratorCode -> base64 encoded orchestrator
    - /Subject        -> JSON with brand data
    """
    reader = PdfReader(pdf_path)
    info = reader.metadata

    print("=== PDF METADATA KEYS ===")
    for key in info.keys():
        print(f"  {key}: {len(str(info[key]))} chars")

    # Extract brand data from Subject JSON
    subject = info.get('/Subject', '{}')
    try:
        metadata = json.loads(subject)
        brand = metadata.get('brand', {})
        marketing = metadata.get('marketing', {})
        social = metadata.get('social', {})
        brand_data = {
            "name": brand.get('name', 'YOUR BRAND'),
            "tagline": brand.get('tagline', 'Your Amazing Tagline'),
            "primary_color": brand.get('colors', {}).get('primary', '#00F3F9'),
            "secondary_color": brand.get('colors', {}).get('secondary', '#001A33'),
            "accent_color": brand.get('colors', {}).get('accent', '#00C4C9'),
            "cta": marketing.get('cta', 'Learn More'),
            "instagram": social.get('instagram', ''),
            "website": brand.get('website', ''),
        }
    except Exception as e:
        print(f"Subject parse error: {e}")
        brand_data = {
            "name": "YOUR BRAND",
            "tagline": "Your Amazing Tagline", 
            "primary_color": "#00F3F9",
            "secondary_color": "#001A33",
            "accent_color": "#00C4C9",
            "cta": "Learn More",
            "instagram": "",
            "website": "",
        }

    # Extract the ACTUAL embedded Remotion code
    remotion_b64 = info.get('/RemotionCode', '')
    remotion_code = None
    if remotion_b64:
        try:
            remotion_code = base64.b64decode(remotion_b64).decode('utf-8')
            print(f"✅ Extracted RemotionCode: {len(remotion_code)} chars")
        except Exception as e:
            print(f"RemotionCode decode error: {e}")

    # Extract orchestrator code
    orch_b64 = info.get('/OrchestratorCode', '')
    orchestrator_code = None
    if orch_b64:
        try:
            orchestrator_code = base64.b64decode(orch_b64).decode('utf-8')
            print(f"✅ Extracted OrchestratorCode: {len(orchestrator_code)} chars")
        except Exception as e:
            print(f"OrchestratorCode decode error: {e}")

    return brand_data, remotion_code, orchestrator_code


def setup_remotion_project(job_dir, brand_data, remotion_code):
    """
    Set up a complete Remotion project using the ACTUAL code from the PDF.
    Falls back to generated code if PDF code is unavailable.
    """
    src_dir = job_dir / "src"
    src_dir.mkdir(exist_ok=True)

    # Use ACTUAL code from PDF if available
    if remotion_code:
        print("🎯 Using ACTUAL embedded Remotion code from PDF!")
        composition_code = remotion_code
    else:
        print("⚠️ No embedded code found, generating from brand data...")
        composition_code = generate_fallback_composition(brand_data)

    # Write the composition
    with open(src_dir / "index.jsx", 'w') as f:
        f.write(composition_code)

    # Write package.json
    package_json = {
        "name": "video-renderer",
        "version": "1.0.0",
        "scripts": {
            "render": "remotion render src/index.jsx InstagramReel out/video.mp4"
        },
        "dependencies": {
            "remotion": "^4.0.0",
            "@remotion/cli": "^4.0.0",
            "react": "^18.2.0",
            "react-dom": "^18.2.0"
        }
    }

    with open(job_dir / "package.json", 'w') as f:
        json.dump(package_json, f, indent=2)

    print(f"✅ Remotion project ready with ACTUAL PDF code")
    return True


def generate_fallback_composition(brand_data):
    """Fallback composition if PDF code extraction fails"""
    return f'''import {{ Composition, useCurrentFrame, useVideoConfig, interpolate, spring, AbsoluteFill }} from 'remotion';
import React from 'react';

const BRAND = {{
  name: "{brand_data['name']}",
  tagline: "{brand_data['tagline']}",
  colors: {{
    primary: "{brand_data['primary_color']}",
    secondary: "{brand_data['secondary_color']}",
    accent: "{brand_data['accent_color']}"
  }},
  cta: "{brand_data['cta']}"
}};

const InstagramReel = () => {{
  const frame = useCurrentFrame();
  const {{fps}} = useVideoConfig();
  const logoSpring = spring({{frame, fps, config: {{damping: 100, stiffness: 200}}}});
  const logoOpacity = interpolate(frame, [0, 30], [0, 1]);
  const taglineOpacity = interpolate(frame, [90, 120, 240, 270], [0, 1, 1, 0]);
  const ctaOpacity = interpolate(frame, [270, 300], [0, 1]);
  const ctaScale = 1 + Math.sin(frame * 0.1) * 0.05;
  const bgAngle = interpolate(frame, [0, 450], [0, 360]);

  return (
    <AbsoluteFill style={{{{
      background: `linear-gradient(${{bgAngle}}deg, ${{BRAND.colors.primary}} 0%, ${{BRAND.colors.secondary}} 100%)`,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    }}}}>
      {{frame < 90 && (
        <div style={{{{transform: `scale(${{logoSpring}})`, opacity: logoOpacity, fontSize: 100, fontWeight: 900, color: 'white', fontFamily: 'Arial Black, sans-serif', textShadow: `0 0 40px ${{BRAND.colors.accent}}`, textAlign: 'center', padding: '0 40px'}}}}>
          {{BRAND.name}}
        </div>
      )}}
      {{frame >= 90 && frame < 270 && (
        <div style={{{{opacity: taglineOpacity, fontSize: 55, fontWeight: 700, textAlign: 'center', padding: '0 60px', color: 'white', fontFamily: 'Arial, sans-serif', lineHeight: 1.3}}}}>
          {{BRAND.tagline}}
        </div>
      )}}
      {{frame >= 270 && (
        <div style={{{{opacity: ctaOpacity, transform: `scale(${{ctaScale}})`, fontSize: 60, fontWeight: 900, color: BRAND.colors.secondary, backgroundColor: BRAND.colors.accent, padding: '25px 70px', borderRadius: '100px', fontFamily: 'Arial Black, sans-serif', boxShadow: `0 0 40px ${{BRAND.colors.accent}}`}}}}>
          {{BRAND.cta}}
        </div>
      )}}
    </AbsoluteFill>
  );
}};

export default () => (
  <Composition id="InstagramReel" component={{InstagramReel}} durationInFrames={{450}} fps={{30}} width={{1080}} height={{1920}} />
);
'''


@app.route('/api/health', methods=['GET'])
def health():
    node_ver = subprocess.run(["node", "--version"], capture_output=True, text=True)
    npm_ver = subprocess.run(["npm", "--version"], capture_output=True, text=True)
    remotion_check = subprocess.run(["npx", "remotion", "--version"], capture_output=True, text=True)
    return jsonify({
        "status": "healthy",
        "service": "Ultimate Video Renderer - PDF Code Extraction",
        "node": node_ver.stdout.strip(),
        "npm": npm_ver.stdout.strip(),
        "remotion": remotion_check.stdout.strip()[:50] if remotion_check.stdout else "available",
        "features": ["PDF code extraction", "base64 decode", "actual embedded code"]
    })


@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({"error": "No PDF provided"}), 400

    pdf_file = request.files['pdf']
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir()

    pdf_path = job_dir / "uploaded.pdf"
    pdf_file.save(pdf_path)

    try:
        print(f"\n🎬 Processing PDF: {pdf_file.filename}")
        brand_data, remotion_code, orchestrator_code = extract_from_pdf(pdf_path)

        print(f"✅ Brand: {brand_data['name']}")
        print(f"✅ Has embedded Remotion code: {remotion_code is not None}")

        setup_remotion_project(job_dir, brand_data, remotion_code)

        jobs[job_id] = {
            "created_at": time.time(),
            "brand": brand_data["name"],
            "status": "extracted",
            "brand_data": brand_data,
            "has_embedded_code": remotion_code is not None,
            "code_length": len(remotion_code) if remotion_code else 0
        }

        return jsonify({
            "job_id": job_id,
            "status": "extracted",
            "brand": brand_data["name"],
            "has_embedded_code": remotion_code is not None,
            "code_length": len(remotion_code) if remotion_code else 0,
            "message": f"Extracted {'ACTUAL embedded code' if remotion_code else 'brand data'} from PDF"
        })

    except Exception as e:
        print(f"❌ Upload error: {traceback.format_exc()}")
        if job_dir.exists():
            shutil.rmtree(job_dir)
        return jsonify({"error": str(e), "details": traceback.format_exc()}), 500


@app.route('/api/generate/<job_id>', methods=['POST'])
def generate_video(job_id):
    job_dir = TEMP_DIR / job_id

    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404

    if job_id in jobs:
        jobs[job_id]["status"] = "generating"

    try:
        brand_name = jobs.get(job_id, {}).get('brand', 'Unknown')
        has_embedded = jobs.get(job_id, {}).get('has_embedded_code', False)

        print(f"\n{'='*60}")
        print(f"🎬 RENDERING: {brand_name}")
        print(f"📦 Using: {'ACTUAL PDF embedded code' if has_embedded else 'generated fallback'}")
        print(f"{'='*60}")

        out_dir = job_dir / "out"
        out_dir.mkdir(exist_ok=True)

        # Install dependencies
        print("📦 Installing npm dependencies...")
        install = subprocess.run(
            ["npm", "install"],
            cwd=job_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )

        if install.returncode != 0:
            print(f"❌ npm install failed:\n{install.stderr}")
            return jsonify({"error": "npm install failed", "details": install.stderr[-2000:]}), 500

        print("✅ Dependencies installed!")
        print("🎥 Starting Remotion render...")

        # Render the video
        env = {
            **os.environ,
            "REMOTION_CHROME_FLAGS": "--no-sandbox --disable-setuid-sandbox",
        }

        # Try different chromium paths
        chrome_paths = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
        ]

        chrome_path = None
        for path in chrome_paths:
            if Path(path).exists():
                chrome_path = path
                break

        render_cmd = [
            "npx", "remotion", "render",
            "src/index.jsx",
            "InstagramReel",
            "out/video.mp4",
            "--log=verbose",
        ]

        if chrome_path:
            render_cmd.append(f"--browser-executable={chrome_path}")
            print(f"🌐 Using Chrome at: {chrome_path}")

        render = subprocess.run(
            render_cmd,
            cwd=job_dir,
            capture_output=True,
            text=True,
            timeout=600,
            env=env
        )

        print(f"Render exit code: {render.returncode}")
        if render.stdout:
            print(f"Render stdout (last 2000):\n{render.stdout[-2000:]}")
        if render.stderr:
            print(f"Render stderr (last 2000):\n{render.stderr[-2000:]}")

        if render.returncode != 0:
            return jsonify({
                "error": "Render failed",
                "stdout": render.stdout[-1000:],
                "stderr": render.stderr[-1000:]
            }), 500

        # Find generated video
        video_files = list((job_dir / "out").glob("*.mp4"))
        if not video_files:
            return jsonify({"error": "No MP4 generated despite success exit code"}), 500

        print(f"✅ Video rendered: {[f.name for f in video_files]}")

        # Package as ZIP
        safe_brand = brand_name.replace(' ', '_').replace('/', '_')
        zip_path = job_dir / f"{safe_brand}_Videos.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for video in video_files:
                zipf.write(video, f"{safe_brand}_instagram_reel.mp4")
            zipf.writestr("README.txt", f"""
{brand_name} - AI Generated Video
{'='*40}
File: {safe_brand}_instagram_reel.mp4
Format: MP4, 1080x1920 (9:16), 15 seconds, 30fps
Technology: Remotion + React + PDF Embedded Code
Source: ACTUAL code extracted from NextGen PDF

Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
System: ExecPDF Next-Gen Video Renderer
""")

        jobs[job_id]["status"] = "complete"

        print(f"✅ ZIP ready: {zip_path.name}")
        print(f"{'='*60}\n")

        return jsonify({
            "status": "complete",
            "download_url": f"/api/download/{job_id}",
            "brand": brand_name,
            "used_embedded_code": has_embedded,
            "message": f"✅ MP4 rendered using {'ACTUAL embedded PDF code' if has_embedded else 'generated code'}!"
        })

    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT")
        return jsonify({"error": "Render timed out after 10 minutes"}), 500
    except Exception as e:
        print(f"❌ ERROR: {traceback.format_exc()}")
        return jsonify({"error": str(e), "details": traceback.format_exc()[-2000:]}), 500


@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(jobs[job_id])


@app.route('/api/download/<job_id>', methods=['GET'])
def download_video(job_id):
    job_dir = TEMP_DIR / job_id
    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404

    zip_files = list(job_dir.glob("*_Videos.zip"))
    if not zip_files:
        return jsonify({"error": "Video not ready yet"}), 404

    return send_file(
        zip_files[0],
        as_attachment=True,
        download_name=zip_files[0].name,
        mimetype='application/zip'
    )


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ULTIMATE VIDEO RENDERER - PDF CODE EXTRACTION EDITION")
    print("   Extracts ACTUAL embedded Remotion code from PDFs")
    print("   No templates. 100% procedural. All generative.")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
