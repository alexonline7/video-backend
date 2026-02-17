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
import traceback
import os
import base64

app = Flask(__name__)
CORS(app, origins=["*"])

TEMP_DIR = Path("temp_processing")
TEMP_DIR.mkdir(exist_ok=True)
jobs = {}


def extract_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    info = reader.metadata

    print("=== PDF METADATA ===")
    for key in info.keys():
        print(f"  {key}: {len(str(info[key]))} chars")

    # Extract brand data
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
        }
    except:
        brand_data = {
            "name": "YOUR BRAND",
            "tagline": "Your Amazing Tagline",
            "primary_color": "#00F3F9",
            "secondary_color": "#001A33",
            "accent_color": "#00C4C9",
            "cta": "Learn More",
            "instagram": "",
        }

    # Extract embedded Remotion code
    remotion_code = None
    remotion_b64 = info.get('/RemotionCode', '')
    if remotion_b64:
        try:
            remotion_code = base64.b64decode(remotion_b64).decode('utf-8')
            print(f"✅ RemotionCode extracted: {len(remotion_code)} chars")
        except Exception as e:
            print(f"RemotionCode error: {e}")

    return brand_data, remotion_code


def fix_remotion_exports(code):
    """
    Fix Remotion 4.x compatibility:
    - Replace 'export default () => (<Composition...)' 
    - With 'export const RemotionRoot = () => (<Composition...)'
    This is required for Remotion 4.x render command
    """
    # Replace export default with RemotionRoot
    if 'export default () =>' in code:
        code = code.replace(
            'export default () =>',
            'export const RemotionRoot = () =>'
        )
        print("✅ Fixed: export default → RemotionRoot")
    elif 'export default function' in code:
        code = code.replace(
            'export default function',
            'export function RemotionRoot'
        )
        print("✅ Fixed: export default function → RemotionRoot")
    
    # If no RemotionRoot exists at all, append one
    if 'RemotionRoot' not in code and 'Composition' in code:
        # Extract composition id
        import re
        comp_match = re.search(r'id=["\'](\w+)["\']', code)
        comp_id = comp_match.group(1) if comp_match else 'InstagramReel'
        comp_match2 = re.search(r'component=\{(\w+)\}', code)
        comp_component = comp_match2.group(1) if comp_match2 else 'InstagramReel'
        
        code += f'''
export const RemotionRoot = () => (
  <Composition
    id="{comp_id}"
    component={{{comp_component}}}
    durationInFrames={{450}}
    fps={{30}}
    width={{1080}}
    height={{1920}}
  />
);
'''
        print(f"✅ Added RemotionRoot wrapper for {comp_id}")
    
    return code


def setup_project(job_dir, brand_data, remotion_code):
    src_dir = job_dir / "src"
    src_dir.mkdir(exist_ok=True)

    if remotion_code:
        print("🎯 Using ACTUAL embedded code from PDF!")
        # Fix Remotion 4.x compatibility
        fixed_code = fix_remotion_exports(remotion_code)
    else:
        print("⚠️ Generating fallback composition...")
        fixed_code = generate_fallback(brand_data)

    with open(src_dir / "index.jsx", 'w') as f:
        f.write(fixed_code)

    # Write remotion.config.ts
    with open(job_dir / "remotion.config.ts", 'w') as f:
        f.write("export default {};\n")

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

    print("✅ Project ready!")
    return True


def generate_fallback(brand_data):
    return f'''import {{ Composition, useCurrentFrame, useVideoConfig, interpolate, spring, AbsoluteFill }} from 'remotion';
import React from 'react';

const BRAND = {{
  name: "{brand_data['name']}",
  tagline: "{brand_data['tagline']}",
  primary: "{brand_data['primary_color']}",
  secondary: "{brand_data['secondary_color']}",
  accent: "{brand_data['accent_color']}",
  cta: "{brand_data['cta']}"
}};

const Video = () => {{
  const frame = useCurrentFrame();
  const {{fps}} = useVideoConfig();
  const scale = spring({{frame, fps, config: {{damping: 100, stiffness: 200}}}});
  const opacity = interpolate(frame, [0, 30], [0, 1]);
  const taglineOpacity = interpolate(frame, [90, 120, 240, 270], [0, 1, 1, 0]);
  const ctaOpacity = interpolate(frame, [270, 300], [0, 1]);
  const bgAngle = interpolate(frame, [0, 450], [0, 360]);

  return (
    <AbsoluteFill style={{{{background: `linear-gradient(${{bgAngle}}deg, ${{BRAND.primary}}, ${{BRAND.secondary}})`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}}}>
      {{frame < 90 && <div style={{{{transform: `scale(${{scale}})`, opacity, fontSize: 100, fontWeight: 900, color: "white", fontFamily: "Arial Black", textShadow: `0 0 40px ${{BRAND.accent}}`, textAlign: "center", padding: "0 40px"}}}}>{brand_data['name']}</div>}}
      {{frame >= 90 && frame < 270 && <div style={{{{opacity: taglineOpacity, fontSize: 55, fontWeight: 700, textAlign: "center", padding: "0 60px", color: "white", fontFamily: "Arial"}}}}>{brand_data['tagline']}</div>}}
      {{frame >= 270 && <div style={{{{opacity: ctaOpacity, fontSize: 60, fontWeight: 900, color: BRAND.secondary, backgroundColor: BRAND.accent, padding: "25px 70px", borderRadius: "100px", fontFamily: "Arial Black"}}}}>{brand_data['cta']}</div>}}
    </AbsoluteFill>
  );
}};

export const RemotionRoot = () => (
  <Composition id="InstagramReel" component={{Video}} durationInFrames={{450}} fps={{30}} width={{1080}} height={{1920}} />
);
'''


@app.route('/api/health', methods=['GET'])
def health():
    node_ver = subprocess.run(["node", "--version"], capture_output=True, text=True)
    npm_ver = subprocess.run(["npm", "--version"], capture_output=True, text=True)
    return jsonify({
        "status": "healthy",
        "service": "Ultimate Renderer v3 - RemotionRoot Fix",
        "node": node_ver.stdout.strip(),
        "npm": npm_ver.stdout.strip(),
    })


@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return jsonify({"error": "No PDF"}), 400

    pdf_file = request.files['pdf']
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir()

    pdf_path = job_dir / "uploaded.pdf"
    pdf_file.save(pdf_path)

    try:
        print(f"\n📄 Processing: {pdf_file.filename}")
        brand_data, remotion_code = extract_from_pdf(pdf_path)
        setup_project(job_dir, brand_data, remotion_code)

        jobs[job_id] = {
            "created_at": time.time(),
            "brand": brand_data["name"],
            "status": "extracted",
            "brand_data": brand_data,
            "has_embedded_code": remotion_code is not None,
        }

        return jsonify({
            "job_id": job_id,
            "status": "extracted",
            "brand": brand_data["name"],
            "has_embedded_code": remotion_code is not None,
        })

    except Exception as e:
        print(f"❌ {traceback.format_exc()}")
        if job_dir.exists():
            shutil.rmtree(job_dir)
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate/<job_id>', methods=['POST'])
def generate_video(job_id):
    job_dir = TEMP_DIR / job_id
    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404

    try:
        brand_name = jobs.get(job_id, {}).get('brand', 'Brand')
        has_embedded = jobs.get(job_id, {}).get('has_embedded_code', False)

        print(f"\n{'='*60}")
        print(f"🎬 RENDERING: {brand_name}")
        print(f"📦 Code source: {'ACTUAL PDF code' if has_embedded else 'fallback'}")
        print(f"{'='*60}")

        out_dir = job_dir / "out"
        out_dir.mkdir(exist_ok=True)

        # npm install
        print("📦 npm install...")
        install = subprocess.run(
            ["npm", "install"],
            cwd=job_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )
        print(f"npm install exit: {install.returncode}")
        if install.stderr:
            print(f"npm stderr: {install.stderr[-1000:]}")

        if install.returncode != 0:
            return jsonify({
                "error": "npm install failed",
                "details": install.stderr[-2000:]
            }), 500

        print("✅ npm install done!")

        # Find chromium
        chrome_paths = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
        chrome_path = next((p for p in chrome_paths if Path(p).exists()), None)
        print(f"🌐 Chrome: {chrome_path}")

        # Build render command
        render_cmd = [
            "npx", "remotion", "render",
            "src/index.jsx",
            "InstagramReel",
            "out/video.mp4",
            "--log=verbose",
            "--concurrency=1",
        ]
        if chrome_path:
            render_cmd.append(f"--browser-executable={chrome_path}")

        env = {
            **os.environ,
            "REMOTION_CHROME_FLAGS": "--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage",
        }

        print(f"🎥 Running: {' '.join(render_cmd)}")
        render = subprocess.run(
            render_cmd,
            cwd=job_dir,
            capture_output=True,
            text=True,
            timeout=600,
            env=env
        )

        print(f"Render exit: {render.returncode}")
        print(f"STDOUT:\n{render.stdout[-3000:]}")
        print(f"STDERR:\n{render.stderr[-3000:]}")

        if render.returncode != 0:
            return jsonify({
                "error": "Render failed",
                "stdout": render.stdout[-1500:],
                "stderr": render.stderr[-1500:]
            }), 500

        video_files = list((job_dir / "out").glob("*.mp4"))
        if not video_files:
            return jsonify({"error": "No MP4 generated"}), 500

        safe_brand = brand_name.replace(' ', '_')
        zip_path = job_dir / f"{safe_brand}_Videos.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for video in video_files:
                zipf.write(video, f"{safe_brand}_instagram_reel.mp4")
            zipf.writestr("README.txt", f"{brand_name} - Generated by ExecPDF\nRendered: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        jobs[job_id]["status"] = "complete"
        print(f"✅ DONE! ZIP ready.")

        return jsonify({
            "status": "complete",
            "download_url": f"/api/download/{job_id}",
            "brand": brand_name,
            "used_embedded_code": has_embedded,
            "message": "MP4 rendered successfully!"
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Render timed out"}), 500
    except Exception as e:
        print(f"❌ {traceback.format_exc()}")
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
        return jsonify({"error": "Not found"}), 404
    zip_files = list(job_dir.glob("*_Videos.zip"))
    if not zip_files:
        return jsonify({"error": "Not ready"}), 404
    return send_file(zip_files[0], as_attachment=True, download_name=zip_files[0].name)


if __name__ == '__main__':
    print("🚀 Ultimate Backend v3 - RemotionRoot Fix Edition")
    app.run(host='0.0.0.0', port=5000, debug=False)
