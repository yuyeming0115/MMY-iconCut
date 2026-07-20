"""工具枚举与全局常量."""
from enum import Enum


class Tool(Enum):
    """画布工具."""
    EYEDROPPER = "eyedropper"   # 吸管(全图颜色匹配抠色)
    WAND = "wand"               # 魔棒(连通区域抠色)
    LASSO = "lasso"             # 套索(自由圈选保护)


class ViewMode(Enum):
    """预览视图模式."""
    ORIGINAL = "original"   # 原图
    RESULT = "result"       # 抠色结果(棋盘格背景)
    ALPHA = "alpha"         # Alpha 蒙版(黑白)


# 保护区域叠加色(半透明红)
PROTECT_OVERLAY_RGBA = (255, 60, 60, 110)

# 套索拖动时的临时线条颜色
LASSO_OVERLAY_COLOR = (255, 230, 80)       # 加选:黄
LASSO_SUBTRACT_COLOR = (80, 200, 255)      # 减选:蓝

# 棋盘格背景单元大小
CHECKER_SIZE = 16
CHECKER_COLOR_A = (204, 204, 204)
CHECKER_COLOR_B = (255, 255, 255)

# 默认参数
DEFAULT_TOLERANCE = 32        # 颜色容差(吸管抠色 & 魔棒保护共用)
DEFAULT_FEATHER = 0           # 边缘羽化像素
MAX_UNDO_STEPS = 50           # 撤销栈深度
