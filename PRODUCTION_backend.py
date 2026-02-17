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

app = Flask(__name__)
CORS(app, origins=[
    "https://pixel-script-press.lovable.app",
    "http://localhost:3000",
    "*"
])

TEMP_DIR = Path("temp_processing")
TEMP_DIR.mkdir(exist_ok=True)
jobs = {}

def extract_brand_data_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text()
        
        brand_match = re.search(r'Brand:\s*([^\n]+)', full_text)
        brand_name = brand_match.group(1).strip() if brand_match else "YOUR BRAND"
        
        tagline_match = re.search(r'Tagline:\s*([^\n]+)', full_text)
        tagline = tagline_match.group(1).strip() if tagline_match else "Your Amazing Tagline"
        
        primary_match = re.search(r'Primary:\s*(#[0-9A-Fa-f]{6})', full_text)
        primary_color = primary_match.group(1) if primary_match else "#00F3F9"
        
        secondary_match = re.search(r'Secondary:\s*(#[0-9A-Fa-f]{6})', full_text)
        secondary_color = secondary_match.group(1) if secondary_match else "#001A33"
        
        accent_match = re.search(r'Accent:\s*(#[0-9A-Fa-f]{6})', full_text)
        accent_color = accent_match.group(1) if accent_match else "#00C4C9"
        
        cta_match = re.search(r'CTA:\s*([^\n]+)', full_text)
        cta = cta_match.group(1).strip() if cta_match else "Learn More"
        
        return {
            "name": brand_name,
            "tagline": tagline,
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "accent_color": accent_color,
            "cta": cta
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "name": "YOUR BRAND",
            "tagline": "Your Amazing Tagline",
            "primary_color": "#00F3F9",
            "secondary_color": "#001A33",
            "accent_color": "#00C4C9",
            "cta": "Learn More"
        }

def setup_remotion_project(job_dir, brand_data):
    src_dir = job_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    package_json = {
        "name": "video-renderer",
        "version": "1.0.0",
        "type": "module",
        "scripts": {"render": "remotion render src/index.jsx Video out/video.mp4"},
        "dependencies": {
            "remotion": "^4.0.0",
            "@remotion/cli": "^4.0.0",
            "react": "^18.2.0",
            "react-dom": "^18.2.0"
        }
    }
    
    with open(job_dir / "package.json", 'w') as f:
        json.dump(package_json, f, indent=2)
    
    composition = f'''
import {{Composition, useCurrentFrame, useVideoConfig, interpolate, spring}} from 'remotion';
import React from 'react';

const Video = () => {{
  const frame = useCurrentFrame();
  const {{fps}} = useVideoConfig();
  
  const logoSpring = spring({{frame, fps, config: {{damping: 100, stiffness: 200}}}});
  const logoOpacity = interpolate(frame, [0, 30], [0, 1]);
  const taglineOpacity = interpolate(frame, [90, 120, 240, 270], [0, 1, 1, 0]);
  const taglineY = interpolate(frame, [90, 120], [50, 0]);
  const ctaOpacity = interpolate(frame, [270, 300], [0, 1]);
  const ctaScale = 1 + Math.sin(frame * 0.1) * 0.05;
  
  return (
    <div style={{{{
      flex: 1,
      background: 'linear-gradient(135deg, {brand_data["primary_color"]} 0%, {brand_data["secondary_color"]} 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 60,
      color: 'white',
      fontFamily: 'Arial, sans-serif'
    }}}}>
      {{frame < 90 && (
        <div style={{{{transform: `scale(${{logoSpring}})`, opacity: logoOpacity, fontSize: 120, fontWeight: 900, textShadow: '0 0 40px rgba(255,255,255,0.5)', color: 'white'}}}}>
          {brand_data["name"]}
        </div>
      )}}
      {{frame >= 90 && frame < 270 && (
        <div style={{{{opacity: taglineOpacity, transform: `translateY(${{taglineY}}px)`, fontSize: 50, fontWeight: 700, textAlign: 'center', padding: '0 50px', maxWidth: '90%'}}}}>
          {brand_data["tagline"]}
        </div>
      )}}
      {{frame >= 270 && (
        <div style={{{{opacity: ctaOpacity, transform: `scale(${{ctaScale}})`, fontSize: 70, fontWeight: 900, color: '{brand_data["accent_color"]}', textShadow: '0 0 30px {brand_data["accent_color"]}', backgroundColor: 'white', padding: '20px 60px', borderRadius: '50px'}}}}>
          {brand_data["cta"]}
        </div>
      )}}
    </div>
  );
}};

export const RemotionRoot = () => {{
  return <Composition id="Video" component={{Video}} durationInFrames={{450}} fps={{30}} width={{1080}} height={{1920}} />;
}};
'''
    
    with open(src_dir / "index.jsx", 'w') as f:
        f.write(composition)
    
    return True

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
        brand_data = extract_brand_data_from_pdf(pdf_path)
        setup_remotion_project(job_dir, brand_data)
        
        jobs[job_id] = {
            "created_at": time.time(),
            "brand": brand_data["name"],
            "status": "extracted",
            "brand_data": brand_data
        }
        
        return jsonify({
            "job_id": job_id,
            "status": "extracted",
            "brand": brand_data["name"]
        })
    except Exception as e:
    import traceback
    error_details = traceback.format_exc()
    print(f"❌ ERROR GENERATING VIDEO:")
    print(error_details)
    if job_id in jobs:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    return jsonify({"error": str(e), "details": error_details}), 500

@app.route('/api/generate/<job_id>', methods=['POST'])
def generate_video(job_id):
    job_dir = TEMP_DIR / job_id
    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404
    
    if job_id in jobs:
        jobs[job_id]["status"] = "generating"
    
    try:
        print(f"Installing dependencies for {job_id}...")
        
        install = subprocess.run(["npm", "install"], cwd=job_dir, capture_output=True, text=True, timeout=180)
        if install.returncode != 0:
            return jsonify({"error": "Install failed", "details": install.stderr}), 500
        
        out_dir = job_dir / "out"
        out_dir.mkdir(exist_ok=True)
        
        print(f"Rendering video...")
        render = subprocess.run(["npm", "run", "render"], cwd=job_dir, capture_output=True, text=True, timeout=300)
        if render.returncode != 0:
            return jsonify({"error": "Render failed", "details": render.stderr}), 500
        
        video_files = list((job_dir / "out").glob("*.mp4"))
        if not video_files:
            return jsonify({"error": "No video generated"}), 500
        
        brand_name = jobs[job_id]['brand'].replace(' ', '_')
        zip_path = job_dir / f"{brand_name}_Video.zip"
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for video in video_files:
                zipf.write(video, f"{brand_name}_instagram_reel.mp4")
            zipf.writestr("README.txt", f"{jobs[job_id]['brand']} - Generated Video\n\nRendered successfully!")
        
        if job_id in jobs:
            jobs[job_id]["status"] = "complete"
        
        return jsonify({"status": "complete", "download_url": f"/api/download/{job_id}", "message": "Video rendered!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download/<job_id>', methods=['GET'])
def download_video(job_id):
    job_dir = TEMP_DIR / job_id
    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404
    
    zip_files = list(job_dir.glob("*_Video.zip"))
    if not zip_files:
        return jsonify({"error": "Video not ready"}), 404
    
    return send_file(zip_files[0], as_attachment=True, download_name=zip_files[0].name)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "Video Renderer"})

if __name__ == '__main__':
    print("Starting Video Rendering Backend on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
