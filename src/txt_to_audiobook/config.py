"""Configuration: paths, voice lists, and defaults."""

from pathlib import Path

# ========== Path Configuration ==========
# Project root: two levels up from this file (src/txt_to_audiobook -> project root)
BASE_DIR = Path(__file__).resolve().parents[2]
TXT_INPUT_DIR = str(BASE_DIR / "txt_input")
OUTPUT_DIR = str(BASE_DIR / "output")
TEMP_DIR = str(BASE_DIR / "temp")

# ========== Recommended Chinese Voices ==========
RECOMMENDED_VOICES = {
    "1": "zh-CN-YunxiNeural",      # Male - gentle (recommended)
    "2": "zh-CN-XiaoxiaoNeural",   # Female - gentle
    "3": "zh-CN-XiaoyiNeural",     # Female - lively
    "4": "zh-CN-YunyangNeural",    # Male - news anchor
    "5": "zh-CN-XiaochenNeural",   # Female - mature
    "6": "zh-CN-YunfengNeural",    # Male - deep
}

# ========== Voice Display Names (for GUI) ==========
VOICE_DISPLAY_NAMES = {
    "Yunxi (Male - Gentle) ⭐": "zh-CN-YunxiNeural",
    "Xiaoxiao (Female - Gentle)": "zh-CN-XiaoxiaoNeural",
    "Xiaoyi (Female - Lively)": "zh-CN-XiaoyiNeural",
    "Yunyang (Male - News)": "zh-CN-YunyangNeural",
    "Xiaochen (Female - Mature)": "zh-CN-XiaochenNeural",
    "Yunfeng (Male - Deep)": "zh-CN-YunfengNeural",
}

# ========== Default voice ==========
DEFAULT_VOICE = "zh-CN-YunxiNeural"
