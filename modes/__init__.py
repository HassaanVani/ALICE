from ._base import ModeContext, ModeRunner, DemoState
from .idle import IdleRunner
from .auto_tetris import AutoTetrisRunner
from .calibrate import CalibrateRunner
from .puppeteer import PuppeteerRunner
from .performance import PerformanceRunner

DEMO_VISIBLE_MODES = ["idle", "auto_tetris", "puppeteer", "performance"]
