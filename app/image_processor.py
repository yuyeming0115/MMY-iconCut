"""图像处理:抠色、保护合成、Alpha 计算."""
from __future__ import annotations

import numpy as np
from PIL import Image


def load_image(path: str) -> np.ndarray:
    """加载图片为 RGBA numpy 数组 (H, W, 4), uint8."""
    img = Image.open(path).convert("RGBA")
    return np.array(img, dtype=np.uint8)


def to_qimage_compatible_rgb(arr: np.ndarray) -> np.ndarray:
    """返回 RGB 副本,用于显示."""
    return arr[..., :3].copy()


def compute_color_mask(
    rgb: np.ndarray,
    picked_colors: list[tuple[int, int, int]],
    tolerance: int,
) -> np.ndarray:
    """计算命中扣色的二值掩膜.

    Args:
        rgb: (H, W, 3) uint8
        picked_colors: 已吸取的目标颜色列表
        tolerance: 0-255,RGB 欧氏距离阈值(归一化到 0-441 范围)

    Returns:
        (H, W) bool,True 表示该像素命中需扣掉
    """
    if not picked_colors:
        return np.zeros(rgb.shape[:2], dtype=bool)

    rgb_f = rgb.astype(np.float32)
    # 阈值映射:tolerance 0-255 -> 距离 0-441.6(对角线长度)
    thresh = (tolerance / 255.0) * 441.673

    hit = np.zeros(rgb.shape[:2], dtype=bool)
    for color in picked_colors:
        c = np.array(color, dtype=np.float32)
        dist = np.sqrt(((rgb_f - c) ** 2).sum(axis=2))
        hit |= dist <= thresh
    return hit


def flood_fill_select(
    rgba: np.ndarray,
    seed_x: int,
    seed_y: int,
    tolerance: int,
) -> np.ndarray:
    """从种子点做 flood fill,返回连通区域掩膜 (H, W) bool.

    类似 PS 魔棒:只选中与种子点颜色相近且连通的区域.
    用 FLOODFILL_FIXED_RANGE:与种子点颜色比较(非相对扩散),
    容差作为每通道差值上限.

    这样圆角矩形外的白色与内部的白色是两个独立连通块,
    点击外部只选外部,不会选到内部.
    """
    h, w = rgba.shape[:2]
    try:
        import cv2
    except ImportError:
        # 无 cv2 时退化为全图颜色匹配
        seed_rgb = tuple(int(v) for v in rgba[seed_y, seed_x, :3])
        return compute_color_mask(rgba[..., :3], [seed_rgb], tolerance)

    # floodFill 需要 (H+2, W+2) mask,单通道 uint8
    mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    # 复制 RGB(floodFill 会修改图像)
    img = rgba[..., :3].copy()
    diff = (int(tolerance), int(tolerance), int(tolerance))
    flags = cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
    cv2.floodFill(img, mask, (int(seed_x), int(seed_y)), (0, 0, 0), diff, diff, flags)
    # mask 内部:连通区域为 1,其余为 0;去掉 padding
    return mask[1:-1, 1:-1].astype(bool)


def compute_edge_mask(h: int, w: int, edge_width: int) -> np.ndarray:
    """生成边缘区域掩膜 (H, W) bool.

    True 表示该像素位于图片四周 edge_width 像素范围内,
    用于"仅边缘扣色"模式:只扣边缘命中色,保护中心主体.
    """
    if edge_width <= 0:
        return np.ones((h, w), dtype=bool)
    e = min(edge_width, h // 2, w // 2)
    mask = np.zeros((h, w), dtype=bool)
    if e <= 0:
        return mask
    mask[:e, :] = True
    mask[-e:, :] = True
    mask[:, :e] = True
    mask[:, -e:] = True
    return mask


def feather_mask(mask: np.ndarray, feather: int) -> np.ndarray:
    """对掩膜做边缘羽化,返回 0-255 的 alpha 蒙版."""
    if feather <= 0:
        return (mask.astype(np.uint8)) * 255
    # 用均值模糊做羽化
    try:
        import cv2

        k = max(3, feather * 2 + 1)
        blur = cv2.blur(mask.astype(np.float32), (k, k))
        return np.clip(blur, 0, 255).astype(np.uint8)
    except ImportError:
        return mask.astype(np.uint8) * 255


def compose_alpha(
    hit_mask: np.ndarray,
    protect_mask: np.ndarray,
    feather: int,
) -> np.ndarray:
    """合成最终 Alpha 通道 (H, W) uint8.

    - hit_mask: 命中扣色区域,True=扣掉
    - protect_mask: 保护区域,>0 表示保护(不扣)
    - feather: 边缘羽化
    """
    h, w = hit_mask.shape
    alpha = np.full((h, w), 255, dtype=np.uint8)

    # 命中区域先扣为 0(带羽化)
    cut_alpha = feather_mask(hit_mask, feather)
    # cut_alpha 越大表示越接近命中,需要扣掉
    alpha = 255 - cut_alpha

    # 保护区域强制不透明
    protect = protect_mask > 0
    alpha[protect] = 255
    return alpha


def apply_alpha(rgba: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """把 alpha 应用到 rgba 副本上."""
    out = rgba.copy()
    out[..., 3] = alpha
    return out


def alpha_to_rgb_preview(alpha: np.ndarray) -> np.ndarray:
    """Alpha 蒙版转黑白 RGB 用于预览."""
    g = alpha
    return np.stack([g, g, g], axis=-1)


def export_png(rgba: np.ndarray, path: str) -> None:
    """导出 RGBA 为 PNG."""
    Image.fromarray(rgba, mode="RGBA").save(path)


def make_checkerboard(h: int, w: int, size: int = 16) -> np.ndarray:
    """生成棋盘格 RGB 背景 (H, W, 3) uint8."""
    rows = (h + size - 1) // size
    cols = (w + size - 1) // size
    block = np.zeros((rows, cols), dtype=np.uint8)
    block[::2, ::2] = 255
    block[1::2, 1::2] = 255
    # 放大到目标尺寸
    try:
        import cv2

        big = cv2.resize(
            np.stack([block, block, block], axis=-1),
            (w, h),
            interpolation=cv2.INTER_NEAREST,
        )
        a = np.array([204, 204, 204], dtype=np.uint8)
        b = np.array([255, 255, 255], dtype=np.uint8)
        mask = big[..., 0] > 0
        out = np.where(mask[..., None], b, a).astype(np.uint8)
        return out
    except ImportError:
        return np.full((h, w, 3), 204, dtype=np.uint8)


def compose_on_checker(rgba: np.ndarray, checker: np.ndarray) -> np.ndarray:
    """把半透明 rgba 合成到棋盘格上,用于结果预览."""
    alpha = rgba[..., 3:4].astype(np.float32) / 255.0
    rgb = rgba[..., :3].astype(np.float32)
    out = rgb * alpha + checker.astype(np.float32) * (1 - alpha)
    return out.astype(np.uint8)
