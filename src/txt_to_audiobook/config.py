"""Configuration: paths, voice lists, and defaults."""

from pathlib import Path

# ========== Path Configuration ==========
# Project root: two levels up from this file (src/txt_to_audiobook -> project root)
BASE_DIR = Path(__file__).resolve().parents[2]
TXT_INPUT_DIR = str(BASE_DIR / "txt_input")
OUTPUT_DIR = str(BASE_DIR / "output")
TEMP_DIR = str(BASE_DIR / "temp")

# ========== Recommended Chinese Voices ==========
# Only voices actually available in edge-tts free API.
RECOMMENDED_VOICES = {
    "1": "zh-CN-YunxiNeural",       # Male - sunshine (recommended)
    "2": "zh-CN-XiaoxiaoNeural",    # Female - warm
    "3": "zh-CN-XiaoyiNeural",      # Female - lively
    "4": "zh-CN-YunyangNeural",     # Male - professional
    "5": "zh-CN-YunjianNeural",     # Male - passionate
    "6": "zh-CN-YunxiaNeural",      # Male - cute
}

# ========== Voice Display Names (for Web UI) ==========
# Key: Chinese name (Gender - style) → Value: edge-tts voice ID
VOICE_DISPLAY_NAMES = {
    "云希 (男·阳光) ⭐": "zh-CN-YunxiNeural",
    "晓晓 (女·温暖)": "zh-CN-XiaoxiaoNeural",
    "晓伊 (女·活泼)": "zh-CN-XiaoyiNeural",
    "云扬 (男·专业)": "zh-CN-YunyangNeural",
    "云健 (男·热血)": "zh-CN-YunjianNeural",
    "云夏 (男·可爱)": "zh-CN-YunxiaNeural",
}

# ========== Chinese voice names (for TTS self-introduction) ==========
VOICE_CN_NAMES = {
    "zh-CN-YunxiNeural": "云希",
    "zh-CN-XiaoxiaoNeural": "晓晓",
    "zh-CN-XiaoyiNeural": "晓伊",
    "zh-CN-YunyangNeural": "云扬",
    "zh-CN-YunjianNeural": "云健",
    "zh-CN-YunxiaNeural": "云夏",
}

# ========== Default voice ==========
DEFAULT_VOICE = "zh-CN-YunxiNeural"

# ========== Ensure directories exist ==========
def ensure_dirs() -> None:
    """Create output/ and temp/ directories if they don't exist."""
    for d in (OUTPUT_DIR, TEMP_DIR, TXT_INPUT_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)

# Run on import so the dirs are always ready
ensure_dirs()
