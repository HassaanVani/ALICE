from ._base import ModeContext, ModeRunner, DemoState
from .idle import IdleRunner
from .auto_tetris import AutoTetrisRunner
from .puppeteer import PuppeteerRunner

UI_SWITCHABLE_MODES = ["idle", "auto_tetris", "puppeteer"]
