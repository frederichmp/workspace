"""Módulo de configurações do Personal Agent."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = DATA_DIR / "memory"
LOGS_DIR = DATA_DIR / "logs"

AGENT_NAME = os.getenv("AGENT_NAME", "PersonalAgent")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-pro")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
