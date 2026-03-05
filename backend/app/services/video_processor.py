import subprocess
from pathlib import Path

def extract_frames(video_path: str, output_dir: str, fps: int = 1):
    """Extract frames from video"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vf', f'fps={fps}',
        f'{output_dir}/frame_%04d.jpg'
    ]
    
    subprocess.run(cmd, check=True)
    return output_dir

def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds"""
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-f', 'null',
        '-'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Parse duration from output
    return 0.0  # Placeholder