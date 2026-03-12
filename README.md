# Long-to-Short Video Pipeline (Bhakti Niche)

This project is a fully automated Long-to-Short Video Pipeline for the Bhakti niche, specifically targeting videos from Premanand Ji Maharaj. It downloads a long-form video, transcribes it, uses AI to find the best 10 emotional/controversial Q&A clips, edits them into 9:16 vertical reels, and automatically staggers uploads to Instagram.

## Prerequisites

- Python 3.10+
- FFmpeg installed on your system.
- Instagram Professional/Creator account connected to a Facebook Page.
- A free Gemini API Key from Google AI Studio.

## Managing Assets (Logo / Background Music)

If you'd like to extend the code for visual overlays:
1. Add your branding image to the repo and name it `logo.png`.
2. Add your chill lofi track and name it `bg.mp3`.
3. You can utilize MoviePy's `CompositeVideoClip` and `AudioFileClip` inside `main.py` (`create_reels` function) to burn these into the reels before exporting.

*(Note: In Phase 2, the pipeline is configured strictly to crop the 9:16 video without adding text/bg audio based on the exact user specification. You can customize the source easily!)*

## Changing the YouTube Channel URL

By default, the script pulls the latest video from `https://www.youtube.com/@PremanandJiMaharaj/videos` when triggered via GitHub Actions Cron. 
If you want to track a different channel:
1. Open `main.py`.
2. Locate the line inside `def main():` that specifies the default channel: `youtube_url = "https://www.youtube.com/@PremanandJiMaharaj/videos"`.
3. Update it to your newly desired channel link.

## GitHub Secrets Setup

To run this autonomously on GitHub Actions, you must define the following Secrets in your repository:
1. Go to your repository **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.
2. Add the following keys exactly:
   - `GEMINI_API_KEY`: Your Google Gemini API Key.
   - `INSTAGRAM_ACCESS_TOKEN`: Your Meta Graph API Permanent Access Token for the connected IG account.
   - `INSTAGRAM_USER_ID`: The unique ID for the Instagram professional account.

## How to Trigger Manually from GitHub Actions

1. Go to the **Actions** tab in your GitHub repository.
2. Select **Daily Bhakti Reel Pipeline** on the left menu.
3. Click the **Run workflow** dropdown button on the right.
4. (Optional) Provide a specific YouTube Video URL. If left blank, it will securely scrape the latest video from the default configured channel.
5. Click the green **Run workflow** button.

## Local Usage

1. Run `pip install -r requirements.txt`.
2. Set your environment variables locally for `GEMINI_API_KEY` etc.
3. Run `python main.py`. 
4. Provide the youtube video link when prompted.
5. The script will interactively ask you if you want to export each clip before processing it.
