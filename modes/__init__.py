from ._base import ModeContext, ModeRunner, DemoState
from .idle import IdleRunner
from .auto_sort import AutoSortRunner
from .auto_tetris import AutoTetrisRunner
from .demo import DemoRunner
from .calibrate import CalibrateRunner
from .puppeteer import PuppeteerRunner
from .performance import PerformanceRunner

# Modes advertised to dashboard clients during demos.
# "calibrate" still works via switch_mode() but is not shown in the UI.
DEMO_VISIBLE_MODES = ["idle", "auto_sort", "auto_tetris", "demo", "puppeteer", "performance"]
