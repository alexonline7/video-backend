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

app = Flask(__name__)
CORS(app, origins=["*"])

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

        instagram_match = re.search(r'Instagram:\s*([^\n]+)', full_text)
        instagram = instagram_match.group(1).strip() if instagram_match else ""

        print(f"✅ Extracted brand: {brand_name}")
        print(f"   Primary: {primary_color}, Secondary: {secondary_color}")

        return {
            "name": brand_name,
            "tagline": tagline,
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "accent_color": accent_color,
            "cta": cta,
            "instagram": instagram
        }
    except Exception as e:
        print(f"Error extracting: {traceback.format_exc()}")
        return {
            "name": "YOUR BRAND",
            "tagline": "Your Amazing Tagline",
            "primary_color": "#00F3F9",
            "secondary_color": "#001A33",
            "accent_color": "#00C4C9",
            "cta": "Learn More",
            "instagram": ""
        }


def setup_remotion_project(job_dir, brand_data):
    """
    Set up Remotion project - NO npm install needed
    Packages are pre-installed in Docker image
    """
    src_dir = job_dir / "src"
    src_dir.mkdir(exist_ok=True)

    # package.json - references global packages
    package_json = {
        "name": "video-renderer",
        "version": "1.0.0",
        "scripts": {
            "render": "remotion render src/index.jsx Video out/video.mp4 --props='{\"brand\": \"" + brand_data['name'] + "\"}'"
        },
        "dependencies": {
            "remotion": "*",
            "@remotion/cli": "*",
            "react": "*",
            "react-dom": "*"
        }
    }

    with open(job_dir / "package.json", 'w') as f:
        json.dump(package_json, f, indent=2)

    # Full Remotion composition with brand data
    composition = f'''import {{Composition, useCurrentFrame, useVideoConfig, interpolate, spring, AbsoluteFill}} from 'remotion';
import React from 'react';

// Brand DNA from PDF
const BRAND = {{
  name: "{brand_data['name']}",
  tagline: "{brand_data['tagline']}",
  primary: "{brand_data['primary_color']}",
  secondary: "{brand_data['secondary_color']}",
  accent: "{brand_data['accent_color']}",
  cta: "{brand_data['cta']}"
}};

// SCENE 1: Logo Entrance (0-90 frames / 0-3s)
const LogoEntrance = () => {{
  const frame = useCurrentFrame();
  const {{fps}} = useVideoConfig();

  const scale = spring({{
    frame,
    fps,
    config: {{damping: 100, stiffness: 200, mass: 0.5}}
  }});

  const opacity = interpolate(frame, [0, 20], [0, 1]);

  const glowSize = 20 + Math.sin(frame * 0.2) * 10;

  return (
    <AbsoluteFill style={{{{
      background: `linear-gradient(135deg, ${{BRAND.primary}} 0%, ${{BRAND.secondary}} 100%)`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column'
    }}}}>
      <div style={{{{
        transform: `scale(${{scale}})`,
        opacity,
        fontSize: 110,
        fontWeight: 900,
        color: 'white',
        fontFamily: 'Arial Black, sans-serif',
        textShadow: `0 0 ${{glowSize}}px ${{BRAND.accent}}, 0 0 ${{glowSize * 2}}px ${{BRAND.primary}}`,
        textAlign: 'center',
        letterSpacing: '-2px'
      }}}}>
        {brand_data['name']}
      </div>
      <div style={{{{
        marginTop: 30,
        width: `${{scale * 200}}px`,
        height: 4,
        background: `linear-gradient(90deg, transparent, ${{BRAND.accent}}, transparent)`,
        borderRadius: 2
      }}}} />
    </AbsoluteFill>
  );
}};

// SCENE 2: Tagline Animation (90-270 frames / 3-9s)
const TaglineScene = () => {{
  const frame = useCurrentFrame();
  const {{fps}} = useVideoConfig();

  const words = BRAND.tagline.split(' ');

  return (
    <AbsoluteFill style={{{{
      background: `linear-gradient(135deg, ${{BRAND.secondary}} 0%, ${{BRAND.primary}}44 100%)`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
      padding: '0 60px'
    }}}}>
      <div style={{{{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 12 }}}}>
        {{words.map((word, i) => {{
          const wordSpring = spring({{
            frame: frame - i * 5,
            fps,
            config: {{damping: 80, stiffness: 150}}
          }});
          const wordOpacity = interpolate(
            frame - i * 5,
            [0, 15],
            [0, 1],
            {{extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}}
          );
          return (
            <span key={{i}} style={{{{
              fontSize: 72,
              fontWeight: 900,
              color: i % 2 === 0 ? 'white' : BRAND.accent,
              fontFamily: 'Arial Black, sans-serif',
              transform: `translateY(${{(1 - wordSpring) * 60}}px)`,
              opacity: wordOpacity,
              textShadow: `0 4px 20px rgba(0,0,0,0.3)`
            }}}}>
              {{word}}
            </span>
          );
        }})}}
      </div>
    </AbsoluteFill>
  );
}};

// SCENE 3: CTA (270-450 frames / 9-15s)
const CTAScene = () => {{
  const frame = useCurrentFrame();
  const {{fps}} = useVideoConfig();

  const scale = spring({{
    frame,
    fps,
    config: {{damping: 60, stiffness: 100}}
  }});

  const pulse = 1 + Math.sin(frame * 0.15) * 0.05;
  const glowIntensity = 20 + Math.sin(frame * 0.2) * 10;

  return (
    <AbsoluteFill style={{{{
      background: `radial-gradient(circle at center, ${{BRAND.primary}}66 0%, ${{BRAND.secondary}} 70%)`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
      gap: 40
    }}}}>
      <div style={{{{
        fontSize: 52,
        fontWeight: 700,
        color: 'white',
        opacity: interpolate(frame, [0, 20], [0, 1]),
        fontFamily: 'Arial, sans-serif',
        textAlign: 'center'
      }}}}>
        {brand_data['name']}
      </div>

      <div style={{{{
        transform: `scale(${{scale * pulse}})`,
        backgroundColor: BRAND.accent,
        color: BRAND.secondary,
        fontSize: 52,
        fontWeight: 900,
        padding: '30px 80px',
        borderRadius: 100,
        fontFamily: 'Arial Black, sans-serif',
        boxShadow: `0 0 ${{glowIntensity}}px ${{BRAND.accent}}, 0 0 ${{glowIntensity * 2}}px ${{BRAND.accent}}44`,
        letterSpacing: 2
      }}}}>
        {brand_data['cta'].upper() if hasattr(brand_data['cta'], 'upper') else brand_data['cta']}
      </div>
    </AbsoluteFill>
  );
}};

// MAIN VIDEO
const Video = () => {{
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{{{ backgroundColor: BRAND.secondary }}}}>
      {{frame < 90 && <LogoEntrance />}}
      {{frame >= 90 && frame < 270 && <TaglineScene />}}
      {{frame >= 270 && <CTAScene />}}
    </AbsoluteFill>
  );
}};

export const RemotionRoot = () => (
  <Composition
    id="Video"
    component={{Video}}
    durationInFrames={{450}}
    fps={{30}}
    width={{1080}}
    height={{1920}}
  />
);
'''

    with open(src_dir / "index.jsx", 'w') as f:
        f.write(composition)

    print(f"✅ Remotion project created for {brand_data['name']}")
    return True


@app.route('/api/health', methods=['GET'])
def health():
    # Check what's available
    node_ver = subprocess.run(["node", "--version"], capture_output=True, text=True)
    npm_ver = subprocess.run(["npm", "--version"], capture_output=True, text=True)
    remotion_check = subprocess.run(["remotion", "--version"], capture_output=True, text=True)

    return jsonify({
        "status": "healthy",
        "service": "Video Renderer - Remotion Edition",
        "node": node_ver.stdout.strip(),
        "npm": npm_ver.stdout.strip(),
        "remotion": remotion_check.stdout.strip() or remotion_check.stderr.strip()
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
        print(f"Upload error: {traceback.format_exc()}")
        if job_dir.exists():
            shutil.rmtree(job_dir)
        return jsonify({"error": str(e)}), 500


@app.route('/api/generate/<job_id>', methods=['POST'])
def generate_video(job_id):
    job_dir = TEMP_DIR / job_id

    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404

    if job_id in jobs:
        jobs[job_id]["status"] = "generating"

    try:
        print(f"\n{'='*50}")
        print(f"🎬 RENDERING VIDEO: {jobs[job_id]['brand']}")
        print(f"{'='*50}")

        # Create output directory
        out_dir = job_dir / "out"
        out_dir.mkdir(exist_ok=True)

        # Link node_modules from global install
        node_modules_link = job_dir / "node_modules"
        if not node_modules_link.exists():
            print("📦 Linking global node_modules...")
            install = subprocess.run(
                ["npm", "install"],
                cwd=job_dir,
                capture_output=True,
                text=True,
                timeout=180,
                env={**os.environ, "npm_config_prefer_offline": "true"}
            )
            print(f"npm install stdout: {install.stdout[-500:] if install.stdout else 'none'}")
            print(f"npm install stderr: {install.stderr[-500:] if install.stderr else 'none'}")

            if install.returncode != 0:
                print(f"❌ npm install failed with code {install.returncode}")
                return jsonify({
                    "error": "npm install failed",
                    "details": install.stderr
                }), 500

        print("✅ Dependencies ready")
        print("🎥 Starting Remotion render...")

        # Render with Remotion
        render = subprocess.run(
            ["npx", "remotion", "render", "src/index.jsx", "Video", "out/video.mp4",
             "--browser-executable=/usr/bin/chromium",
             "--log=verbose"],
            cwd=job_dir,
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ, "REMOTION_CHROME_FLAGS": "--no-sandbox"}
        )

        print(f"Render exit code: {render.returncode}")
        print(f"Render stdout: {render.stdout[-2000:] if render.stdout else 'none'}")
        print(f"Render stderr: {render.stderr[-2000:] if render.stderr else 'none'}")

        if render.returncode != 0:
            return jsonify({
                "error": "Render failed",
                "details": render.stderr[-1000:]
            }), 500

        # Find generated files
        video_files = list((job_dir / "out").glob("*.mp4"))

        if not video_files:
            return jsonify({"error": "No video generated"}), 500

        print(f"✅ Video rendered: {[f.name for f in video_files]}")

        # Package as ZIP
        brand_name = jobs[job_id]['brand'].replace(' ', '_')
        zip_path = job_dir / f"{brand_name}_Video.zip"

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for video in video_files:
                zipf.write(video, f"{brand_name}_instagram_reel.mp4")
            zipf.writestr("README.txt", f"""
{jobs[job_id]['brand']} - Generated Video
=====================================
File: {brand_name}_instagram_reel.mp4
Format: MP4, 1080x1920, 15s, 30fps
Technology: Remotion + React

Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
""")

        if job_id in jobs:
            jobs[job_id]["status"] = "complete"

        print(f"✅ ZIP package created!")
        print(f"{'='*50}\n")

        return jsonify({
            "status": "complete",
            "download_url": f"/api/download/{job_id}",
            "files_count": len(video_files),
            "message": "ACTUAL MP4 video rendered with Remotion!"
        })

    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT: Render took too long")
        return jsonify({"error": "Rendering timed out"}), 500
    except Exception as e:
        print(f"❌ ERROR: {traceback.format_exc()}")
        return jsonify({"error": str(e), "details": traceback.format_exc()}), 500


@app.route('/api/download/<job_id>', methods=['GET'])
def download_video(job_id):
    job_dir = TEMP_DIR / job_id

    if not job_dir.exists():
        return jsonify({"error": "Job not found"}), 404

    zip_files = list(job_dir.glob("*_Video.zip"))

    if not zip_files:
        return jsonify({"error": "Video not ready"}), 404

    return send_file(
        zip_files[0],
        as_attachment=True,
        download_name=zip_files[0].name
    )


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 VIDEO RENDERING BACKEND - REMOTION EDITION")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, debug=False)
