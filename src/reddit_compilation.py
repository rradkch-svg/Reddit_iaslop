import os
import sys
from typing import Dict, Any, Optional

try:
    from .reddit_longform import generate_25min_single_story_video
except ImportError:
    from reddit_longform import generate_25min_single_story_video

def generate_20min_reddit_compilation(
    target_duration_minutes: float = 25.0,
    output_base_dir: str = "checkpoint/reddit_longform_25min",
    aspect_ratio: str = "16:9",
    status_callback = None
) -> Dict[str, Any]:
    """
    Gera um vídeo longo de 25 minutos de UMA HISTÓRIA ÚNICA contínua (substituindo o antigo formato de compilado).
    """
    return generate_25min_single_story_video(
        target_duration_minutes=target_duration_minutes,
        output_base_dir=output_base_dir,
        aspect_ratio=aspect_ratio,
        status_callback=status_callback
    )

if __name__ == "__main__":
    print("🚀 Starting 25-Minute Single Story Long-Form Video Generator...")
    res = generate_25min_single_story_video(target_duration_minutes=25.0)
    print(f"✅ 25-Minute Long-Form Video finished successfully in: {res.get('work_dir')}")
