import os
import sys
import json
import time
import logging
import requests
from datetime import timedelta
from yt_dlp import YoutubeDL
from faster_whisper import WhisperModel
import google.generativeai as genai
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.fx.Crop import Crop

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def download_video(url, output_filename="input_video.mp4"):
    logging.info(f"Downloading video from {url}...")
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        'outtmpl': output_filename,
        'merge_output_format': 'mp4',
        'playlist_items': '1', # Ensure only the latest is grabbed if it's a channel link
    }
    
    if os.path.exists("cookies.txt"):
        logging.info("Using cookies.txt for authentication...")
        ydl_opts['cookiefile'] = 'cookies.txt'
        
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        logging.info("Download completed.")
    except Exception as e:
        logging.error(f"Failed to download video: {e}")
        raise

def format_timestamp(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"

def transcribe_video(video_path, txt_out="transcript.txt", vtt_out="transcript.vtt"):
    logging.info("Starting transcription using faster-whisper (tiny model)...")
    try:
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(video_path, beam_size=5)
        
        full_text = ""
        vtt_content = "WEBVTT\n\n"
        
        for segment in segments:
            text = segment.text.strip()
            full_text += text + " "
            start_str = format_timestamp(segment.start)
            end_str = format_timestamp(segment.end)
            vtt_content += f"{start_str} --> {end_str}\n{text}\n\n"
            
        with open(txt_out, "w", encoding="utf-8") as f:
            f.write(full_text.strip())
            
        with open(vtt_out, "w", encoding="utf-8") as f:
            f.write(vtt_content)
            
        logging.info("Transcription completed.")
        return full_text.strip()
    except Exception as e:
        logging.error(f"Transcription failed: {e}")
        raise

def detect_clips_gemini(transcript):
    logging.info("Sending transcript to Gemini 1.5 Flash API for clip detection...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")
    
    try:
        genai.configure(api_key=api_key)
        prompt = """You are a viral short-form video editor for a spiritual YouTube channel 
(Premanand Ji Maharaj). Analyze this transcript and extract the top 10 
most emotionally powerful or controversial Question-and-Answer moments 
between a devotee and Maharaj.

For each clip, output ONLY valid JSON in this exact format:
[
  {
    "start": "00:02:10",
    "end": "00:03:00",
    "hook_title": "Is Karma Real?"
  }
]

Rules:
- Each clip must be between 30 and 90 seconds long
- Focus on emotional, surprising, or controversial moments
- hook_title must be max 5 words, written as a question or bold statement
- Output ONLY the JSON array. No explanation, no markdown.
"""
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt + "\n\nTRANSCRIPT:\n" + transcript, safety_settings=safety_settings)
        
        try:
            text = response.text.strip()
        except ValueError:
            text = response.candidates[0].content.parts[0].text.strip() if response.candidates else ""

        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        clips = json.loads(text.strip())
        logging.info(f"Successfully detected {len(clips)} clips.")
        return clips
    except Exception as e:
        logging.error(f"Failed to detect clips or parse JSON from Gemini: {e}\nResponse: {response.text if 'response' in locals() else 'None'}")
        return []

def time_to_seconds(time_str):
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0

def create_reels(clips, input_video="input_video.mp4"):
    logging.info("Starting video generation...")
    output_dir = "output_clips"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    reels_created = []
    try:
        with VideoFileClip(input_video) as video:
            for idx, clip_data in enumerate(clips):
                reel_filename = os.path.join(output_dir, f"reel_{idx+1:02d}.mp4")
                start_sec = time_to_seconds(clip_data.get("start", "00:00:00"))
                end_sec = time_to_seconds(clip_data.get("end", "00:00:30"))
                hook = clip_data.get("hook_title", "Reel")
                
                logging.info(f"Processing Clip {idx+1}: {hook} ({clip_data.get('start')} to {clip_data.get('end')})")
                
                try:
                    sub = video.subclipped(start_sec, end_sec)
                    w, h = sub.size
                    target_w = int(h * 9 / 16)
                    # libx264 requires dimensions divisible by 2
                    if target_w % 2 != 0: target_w -= 1
                    if h % 2 != 0: h -= 1
                    
                    x_center = w / 2
                    y_center = h / 2
                    
                    cropped = sub.with_effects([Crop(width=target_w, height=h, x_center=x_center, y_center=y_center)])
                    
                    logging.info(f"Exporting {reel_filename}...")
                    cropped.write_videofile(
                        reel_filename, 
                        codec="libx264", 
                        audio_codec="aac",
                        temp_audiofile=os.path.join(output_dir, f"temp-audio-reel_{idx+1:02d}.m4a"),
                        remove_temp=True,
                        fps=30,
                        logger=None,
                        ffmpeg_params=["-pix_fmt", "yuv420p"]
                    )
                    reels_created.append(reel_filename)
                except Exception as e:
                    logging.error(f"Error processing {reel_filename}: {e}")
                    
        return reels_created
    except Exception as e:
        logging.error(f"Video editing failed: {e}")
        raise

def upload_sequence(reels):
    queue = [{"filename": r} for r in reels]
    with open("upload_queue.json", "w") as f:
        json.dump(queue, f, indent=4)
        
    access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    ig_user_id = os.environ.get("INSTAGRAM_USER_ID")
    
    if not access_token or not ig_user_id:
        logging.warning("Instagram credentials missing. Skipping automated uploads. Queue saved to upload_queue.json")
        return
        
    for idx, item in enumerate(queue):
        reel_file = item["filename"]
        try:
            logging.info(f"Uploading {reel_file} to Instagram...")
            
            # Host file temporarily to satisfy Graph API's requirement for a video_url
            logging.info(f"Hosting {reel_file} temporarily...")
            with open(reel_file, "rb") as f:
                res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}).json()
                temp_url = res["data"]["url"]
                video_url = temp_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            
            # 1. Create Media Container
            url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
            payload = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": "Divine Wisdom \n\n#PremanandJiMaharaj #Bhakti #Spirituality #Wisdom",
                "access_token": access_token
            }
            r = requests.post(url, data=payload).json()
            if "error" in r:
                raise Exception(f"Graph API Upload Error: {r['error']}")
            creation_id = r.get("id")
            
            # 2. Status Polling
            status_url = f"https://graph.facebook.com/v19.0/{creation_id}?fields=status_code&access_token={access_token}"
            while True:
                status_req = requests.get(status_url).json()
                status = status_req.get("status_code")
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    raise Exception("Instagram media processing failed.")
                time.sleep(5)
                
            # 3. Publish
            publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
            pub_r = requests.post(publish_url, data={"creation_id": creation_id, "access_token": access_token}).json()
            if "error" in pub_r:
                raise Exception(f"Publish Error: {pub_r['error']}")
                
            logging.info(f"Successfully published {reel_file}. Post ID: {pub_r.get('id')}")
            
            # Cleanup File
            if os.path.exists(reel_file):
                os.remove(reel_file)
                logging.info(f"Deleted {reel_file} to save space.")
            
            # Staggered sleep between uploads
            if idx < len(queue) - 1:
                logging.info("Waiting 2 hours (7200 seconds) before next upload to avoid spam limits...")
                time.sleep(7200)
                
        except Exception as e:
            logging.error(f"Failed to upload {reel_file}: {e}")

def main():
    try:
        youtube_url = os.environ.get("YOUTUBE_URL")
        if not youtube_url or youtube_url.strip() == "":
            if os.environ.get("GITHUB_ACTIONS"):
                # specific channel default for automation if no specific video is passed
                youtube_url = "https://www.youtube.com/@PremanandJiMaharaj/videos" 
                logging.info(f"No specific YOUTUBE_URL provided in CI. Defaulting to pulling latest video from {youtube_url}")
            else:
                youtube_url = input("Enter YouTube video URL to process: ").strip()

        if not youtube_url:
            logging.error("No YouTube URL provided.")
            sys.exit(1)

        # STEP 1: SCRAPER
        if not os.path.exists("input_video.mp4"):
            download_video(youtube_url)
        else:
            logging.info("Input video already exists, skipping download.")

        # STEP 2: TRANSCRIPTION
        if not os.path.exists("transcript.txt"):
            transcript = transcribe_video("input_video.mp4")
        else:
            logging.info("Transcript already exists, skipping transcription.")
            with open("transcript.txt", "r", encoding="utf-8") as f:
                transcript = f.read()

        # STEP 3: AI CLIP DETECTION
        clips = detect_clips_gemini(transcript)
        if not clips:
            logging.error("No clips parsed. Exiting pipeline.")
            sys.exit(1)

        # STEP 4: VIDEO EDITING
        reels = create_reels(clips)

        # STEP 5: UPLOAD
        if reels:
            upload_sequence(reels)
        else:
            logging.info("No reels were exported.")

        # STEP 6: CLEANUP
        logging.info("Starting final cleanup of large files...")
        files_to_delete = ["input_video.mp4", "transcript.txt", "transcript.vtt"]
        for f in files_to_delete:
            if os.path.exists(f):
                os.remove(f)
                logging.info(f"Deleted {f}")

        logging.info("Pipeline Execution Finished Successfully.")
        
    except Exception as e:
        logging.error(f"Pipeline crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
