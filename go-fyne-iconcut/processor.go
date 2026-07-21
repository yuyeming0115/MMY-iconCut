package main

// 纯 Go 图像处理：加载 PNG、吸色颜色掩膜、魔棒连通区域、笔刷保护、Alpha 合成、导出。
// 算法对齐原 Python 版(app/image_processor.py、app/brush_mask.py)。
import (
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"math"
	"os"
	"strings"
)

// Mask 单通道 0/1 掩膜。
type Mask struct {
	W, H int
	Data []byte
}

func NewMask(w, h int) *Mask {
	return &Mask{W: w, H: h, Data: make([]byte, w*h)}
}

func (m *Mask) Get(x, y int) byte {
	if x < 0 || y < 0 || x >= m.W || y >= m.H {
		return 0
	}
	return m.Data[y*m.W+x]
}

func (m *Mask) Set(x, y int, v byte) {
	if x < 0 || y < 0 || x >= m.W || y >= m.H {
		return
	}
	m.Data[y*m.W+x] = v
}

// LoadRGBA 加载图片(PNG/JPEG/BMP/GIF)为 *image.RGBA(已含 Alpha)。
func LoadRGBA(path string) (*image.RGBA, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var img image.Image
	switch strings.ToLower(filepathExt(path)) {
	case ".jpg", ".jpeg":
		img, err = jpeg.Decode(f)
	default:
		img, err = png.Decode(f)
	}
	if err != nil {
		return nil, err
	}
	return toRGBA(img), nil
}

// filepathExt 返回路径的扩展名(小写,含点号)。不导入 path/filepath 避免循环。
func filepathExt(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '.' {
			return path[i:]
		}
		if path[i] == '/' || path[i] == '\\' {
			break
		}
	}
	return ""
}

func toRGBA(img image.Image) *image.RGBA {
	if r, ok := img.(*image.RGBA); ok {
		return r
	}
	b := img.Bounds()
	out := image.NewRGBA(b)
	for y := b.Min.Y; y < b.Max.Y; y++ {
		for x := b.Min.X; x < b.Max.X; x++ {
			out.Set(x, y, img.At(x, y))
		}
	}
	return out
}

// SavePNG 导出 RGBA 为 PNG。
func SavePNG(path string, img image.Image) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return png.Encode(f, img)
}

// rgbaAt 取像素 8-bit RGBA(忽略原图 16-bit 精度)。
func rgbaAt(src *image.RGBA, x, y int) (r, g, b, a uint8) {
	c := src.RGBAAt(x, y)
	return c.R, c.G, c.B, c.A
}

// colorDist2 RGB 欧氏距离平方(8-bit)。
func colorDist2(r, g, b uint8, c color.RGBA) float64 {
	dr := float64(r) - float64(c.R)
	dg := float64(g) - float64(c.G)
	db := float64(b) - float64(c.B)
	return dr*dr + dg*dg + db*db
}

// ColorMask 计算命中扣色掩膜(吸管/全图颜色匹配)。
// tolerance 0-255 -> 距离 0-441.67(对角线)。返回 true=该像素命中(需扣掉)。
func ColorMask(src *image.RGBA, picked []color.RGBA, tolerance int) *Mask {
	w, h := src.Bounds().Dx(), src.Bounds().Dy()
	m := NewMask(w, h)
	thresh := (float64(tolerance) / 255.0) * 441.673
	thresh2 := thresh * thresh
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			r, g, b, _ := rgbaAt(src, x, y)
			for _, c := range picked {
				if colorDist2(r, g, b, c) <= thresh2 {
					m.Set(x, y, 1)
					break
				}
			}
		}
	}
	return m
}

// FloodSelect 从种子点做 flood fill,返回连通区域(魔棒)。
// 仅选中与种子点颜色相近且连通的区域(FIXED_RANGE,容差作为欧氏阈值)。
func FloodSelect(src *image.RGBA, seedX, seedY, tolerance int) *Mask {
	w, h := src.Bounds().Dx(), src.Bounds().Dy()
	m := NewMask(w, h)
	if seedX < 0 || seedY < 0 || seedX >= w || seedY >= h {
		return m
	}
	sr, sg, sb, _ := rgbaAt(src, seedX, seedY)
	seed := color.RGBA{R: sr, G: sg, B: sb}
	thresh := (float64(tolerance) / 255.0) * 441.673
	thresh2 := thresh * thresh

	visited := make([]bool, w*h)
	stack := []int{seedY*w + seedX}
	visited[seedY*w+seedX] = true
	dirs := [][2]int{{1, 0}, {-1, 0}, {0, 1}, {0, -1}}

	for len(stack) > 0 {
		idx := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		x := idx % w
		y := idx / w
		r, g, b, _ := rgbaAt(src, x, y)
		if colorDist2(r, g, b, seed) > thresh2 {
			continue
		}
		m.Set(x, y, 1)
		for _, d := range dirs {
			nx, ny := x+d[0], y+d[1]
			if nx < 0 || ny < 0 || nx >= w || ny >= h {
				continue
			}
			ni := ny*w + nx
			if visited[ni] {
				continue
			}
			visited[ni] = true
			stack = append(stack, ni)
		}
	}
	return m
}

// BrushPaint 在 (x,y) 画半径 radius 的圆;erase 时擦除。用于笔刷保护区域。
func BrushPaint(m *Mask, x, y, radius int, erase bool) {
	if m == nil {
		return
	}
	y0, y1 := max(0, y-radius), min(m.H, y+radius+1)
	x0, x1 := max(0, x-radius), min(m.W, x+radius+1)
	r2 := radius * radius
	for yy := y0; yy < y1; yy++ {
		for xx := x0; xx < x1; xx++ {
			dx, dy := xx-x, yy-y
			if dx*dx+dy*dy <= r2 {
				if erase {
					m.Set(xx, yy, 0)
				} else {
					m.Set(xx, yy, 1)
				}
			}
		}
	}
}

// BrushLine 沿 (x0,y0)->(x1,y1) 插值绘制连续笔画。
func BrushLine(m *Mask, x0, y0, x1, y1, radius int, erase bool) {
	dist := max(abs(x1-x0), abs(y1-y0))
	steps := dist / max(1, radius/3)
	if steps < 1 {
		steps = 1
	}
	for i := 0; i <= steps; i++ {
		t := float64(i) / float64(steps)
		x := int(math.Round(float64(x0) + float64(x1-x0)*t))
		y := int(math.Round(float64(y0) + float64(y1-y0)*t))
		BrushPaint(m, x, y, radius, erase)
	}
}

// Feather 对掩膜做边缘羽化,返回 0-255 的 alpha 蒙版。
func Feather(m *Mask, feather int) []byte {
	w, h := m.W, m.H
	out := make([]byte, w*h)
	if feather <= 0 {
		for i := 0; i < w*h; i++ {
			if m.Data[i] != 0 {
				out[i] = 255
			}
		}
		return out
	}
	// 先转 0/255
	src := make([]byte, w*h)
	for i := 0; i < w*h; i++ {
		if m.Data[i] != 0 {
			src[i] = 255
		}
	}
	// 可分离盒式模糊(两次一维卷积)
	r := feather
	tmp := make([]byte, w*h)
	// 横向
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			sum, cnt := 0, 0
			for k := -r; k <= r; k++ {
				xx := x + k
				if xx < 0 || xx >= w {
					continue
				}
				sum += int(src[y*w+xx])
				cnt++
			}
			tmp[y*w+x] = byte(sum / cnt)
		}
	}
	// 纵向
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			sum, cnt := 0, 0
			for k := -r; k <= r; k++ {
				yy := y + k
				if yy < 0 || yy >= h {
					continue
				}
				sum += int(tmp[yy*w+x])
				cnt++
			}
			out[y*w+x] = byte(sum / cnt)
		}
	}
	return out
}

// ComposeAlpha 合成最终 Alpha 通道(0-255)。
// hit=命中扣色区域;protect=保护区域(>0 不扣);feather=羽化像素。
func ComposeAlpha(hit *Mask, protect *Mask, feather int) []byte {
	w, h := hit.W, hit.H
	cut := Feather(hit, feather) // 0..255,越大越接近命中
	out := make([]byte, w*h)
	for i := 0; i < w*h; i++ {
		out[i] = byte(255 - int(cut[i]))
	}
	if protect != nil {
		for i := 0; i < w*h; i++ {
			if protect.Data[i] != 0 {
				out[i] = 255
			}
		}
	}
	return out
}

// ApplyAlpha 把 alpha 应用到图像副本。
func ApplyAlpha(src *image.RGBA, alpha []byte) *image.RGBA {
	out := image.NewRGBA(src.Bounds())
	copy(out.Pix, src.Pix)
	for i := 0; i < len(alpha); i++ {
		out.Pix[i*4+3] = alpha[i]
	}
	return out
}

// Checkerboard 生成棋盘格 RGB 背景。
func Checkerboard(w, h, size int) *image.RGBA {
	if size <= 0 {
		size = 16
	}
	out := image.NewRGBA(image.Rect(0, 0, w, h))
	a := color.RGBA{204, 204, 204, 255}
	b := color.RGBA{255, 255, 255, 255}
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			block := ((x/size)+(y/size))%2 == 0
			if block {
				out.Set(x, y, b)
			} else {
				out.Set(x, y, a)
			}
		}
	}
	return out
}

// ComposeResult 把半透明 RGBA 合成到棋盘格上(结果预览)。
func ComposeResult(src *image.RGBA, alpha []byte, checker *image.RGBA) *image.RGBA {
	w, h := src.Bounds().Dx(), src.Bounds().Dy()
	out := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			r, g, b, _ := rgbaAt(src, x, y)
			af := float64(alpha[y*w+x]) / 255.0
			cr, cg, cb, _ := rgbaAt(checker, x, y)
			nr := float64(r)*af + float64(cr)*(1-af)
			ng := float64(g)*af + float64(cg)*(1-af)
			nb := float64(b)*af + float64(cb)*(1-af)
			out.Set(x, y, color.RGBA{uint8(nr), uint8(ng), uint8(nb), 255})
		}
	}
	return out
}

// AlphaToGrayImg Alpha 蒙版转灰度图(显式宽高)。
func AlphaToGrayImg(alpha []byte, w, h int) *image.RGBA {
	out := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			v := alpha[y*w+x]
			out.Set(x, y, color.RGBA{v, v, v, 255})
		}
	}
	return out
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
func abs(a int) int {
	if a < 0 {
		return -a
	}
	return a
}
