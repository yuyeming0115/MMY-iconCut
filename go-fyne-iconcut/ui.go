package main

// Fyne 界面：加载图片、吸管/魔棒/笔刷三工具、容差/羽化/笔刷大小、原图/结果/Alpha 预览、导出 PNG。
import (
	"image"
	"image/color"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/widget"
)

// PixCanvas 自绘画布：把鼠标坐标映射回图像像素,并转发 tap/drag 回调。
type PixCanvas struct {
	widget.BaseWidget
	img    image.Image
	curW   float32
	curH   float32
	onTap  func(int, int)
	onDrag func(int, int)
}

func NewPixCanvas(onTap, onDrag func(int, int)) *PixCanvas {
	p := &PixCanvas{onTap: onTap, onDrag: onDrag}
	p.ExtendBaseWidget(p)
	return p
}

func (p *PixCanvas) SetImage(img image.Image) {
	p.img = img
	p.Refresh()
}

func (p *PixCanvas) CreateRenderer() fyne.WidgetRenderer {
	img := canvas.NewImageFromImage(p.img)
	img.FillMode = canvas.ImageFillStretch
	img.ScaleMode = canvas.ImageScalePixels
	return &pixRenderer{p: p, img: img}
}

func (p *PixCanvas) MinSize() fyne.Size {
	if p.img == nil {
		return fyne.NewSize(360, 360)
	}
	b := p.img.Bounds()
	return fyne.NewSize(float32(b.Dx()), float32(b.Dy()))
}

func (p *PixCanvas) Tapped(e *fyne.PointEvent) {
	x, y := p.toPixel(e.Position)
	if p.onTap != nil {
		p.onTap(x, y)
	}
}

func (p *PixCanvas) DragStart(e *fyne.DragEvent) {
	x, y := p.toPixel(e.Position)
	p.onDrag(x, y)
}

func (p *PixCanvas) DragEnd() {}

func (p *PixCanvas) Dragged(e *fyne.DragEvent) {
	x, y := p.toPixel(e.Position)
	if p.onDrag != nil {
		p.onDrag(x, y)
	}
}

func (p *PixCanvas) toPixel(pos fyne.Position) (int, int) {
	if p.img == nil || p.curW <= 0 || p.curH <= 0 {
		return int(pos.X), int(pos.Y)
	}
	b := p.img.Bounds()
	sx := float32(b.Dx()) / p.curW
	sy := float32(b.Dy()) / p.curH
	x := int(pos.X * sx)
	y := int(pos.Y * sy)
	x = clamp(x, 0, b.Dx()-1)
	y = clamp(y, 0, b.Dy()-1)
	return x, y
}

type pixRenderer struct {
	p   *PixCanvas
	img *canvas.Image
}

func (r *pixRenderer) Layout(size fyne.Size) {
	r.p.curW = size.Width
	r.p.curH = size.Height
	r.img.Resize(size)
}
func (r *pixRenderer) MinSize() fyne.Size { return r.p.MinSize() }
func (r *pixRenderer) Refresh() {
	r.img.Image = r.p.img
	r.img.Refresh()
}
func (r *pixRenderer) Objects() []fyne.CanvasObject { return []fyne.CanvasObject{r.img} }
func (r *pixRenderer) Destroy()                     {}

// appState 保存界面状态。
type appState struct {
	src      *image.RGBA
	picked   []color.RGBA
	hit      *Mask
	protect  *Mask
	checker  *image.RGBA
	tool     string
	erase    bool
	brushR   int
	tol      int
	feather  int
	view     string
	pix      *PixCanvas
	status   *widget.Label
	pickLbl  *widget.Label
	scroll   *container.Scroll
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func Run() {
	a := app.New()
	w := a.NewWindow("MMY iconCut · Go+Fyne 原型")

	st := &appState{
		tool:    "eyedropper",
		brushR:  20,
		tol:     32,
		feather: 0,
		view:    "original",
		status:  widget.NewLabel("请先加载一张带背景的图标 PNG"),
		pickLbl: widget.NewLabel("已吸色: 0"),
	}
	st.pix = NewPixCanvas(st.onTap, st.onDrag)

	st.scroll = container.NewScroll(st.pix)

	// ---- 左侧工具栏 ----
	toolSel := widget.NewSelect([]string{"eyedropper", "wand", "brush"}, func(s string) {
		st.tool = s
	})
	toolSel.SetSelected("eyedropper")

	eraseChk := widget.NewCheck("笔刷擦除模式", func(b bool) { st.erase = b })

	tolLbl := widget.NewLabel("容差: 32")
	tol := widget.NewSlider(0, 255)
	tol.Value = 32
	tol.OnChanged = func(f float64) {
		st.tol = int(f)
		tolLbl.SetText("容差: " + itoa(int(f)))
		st.recompute()
	}

	featherLbl := widget.NewLabel("羽化: 0")
	feather := widget.NewSlider(0, 50)
	feather.OnChanged = func(f float64) {
		st.feather = int(f)
		featherLbl.SetText("羽化: " + itoa(int(f)))
		st.recompute()
	}

	brushLbl := widget.NewLabel("笔刷大小: 20")
	brush := widget.NewSlider(2, 80)
	brush.Value = 20
	brush.OnChanged = func(f float64) {
		st.brushR = int(f)
		brushLbl.SetText("笔刷大小: " + itoa(int(f)))
	}

	viewSel := widget.NewSelect([]string{"original", "result", "alpha"}, func(s string) {
		st.view = s
		st.recompute()
	})
	viewSel.SetSelected("original")

	loadBtn := widget.NewButton("加载图片", func() {
		dialog.ShowFileOpen(func(r fyne.URIReadCloser, err error) {
			if err != nil || r == nil {
				return
			}
			path := r.URI().Path()
			img, e := LoadRGBA(path)
			if e != nil {
				st.status.SetText("加载失败: " + e.Error())
				return
			}
			st.src = img
			st.picked = nil
			st.hit = NewMask(img.Bounds().Dx(), img.Bounds().Dy())
			st.protect = NewMask(img.Bounds().Dx(), img.Bounds().Dy())
			st.checker = Checkerboard(img.Bounds().Dx(), img.Bounds().Dy(), 16)
			st.pickLbl.SetText("已吸色: 0")
			st.status.SetText("已加载: " + path)
			st.pix.SetImage(img)
			st.scroll.Refresh()
			st.recompute()
		}, w)
	})

	exportBtn := widget.NewButton("导出 PNG(透明)", func() {
		if st.src == nil {
			st.status.SetText("请先加载图片")
			return
		}
		dialog.ShowFileSave(func(wr fyne.URIWriteCloser, err error) {
			if err != nil || wr == nil {
				return
			}
			alpha := ComposeAlpha(st.hit, st.protect, st.feather)
			out := ApplyAlpha(st.src, alpha)
			if e := SavePNG(wr.URI().Path(), out); e != nil {
				st.status.SetText("导出失败: " + e.Error())
				return
			}
			st.status.SetText("已导出: " + wr.URI().Path())
		}, w)
	})

	resetBtn := widget.NewButton("重置", func() {
		st.picked = nil
		if st.src != nil {
			st.hit = NewMask(st.src.Bounds().Dx(), st.src.Bounds().Dy())
			st.protect = NewMask(st.src.Bounds().Dx(), st.src.Bounds().Dy())
		}
		st.pickLbl.SetText("已吸色: 0")
		st.status.SetText("已重置")
		st.recompute()
	})

	left := container.NewVBox(
		widget.NewLabel("MMY iconCut · Go 原型"),
		loadBtn,
		widget.NewLabel("工具"),
		toolSel,
		eraseChk,
		brushLbl, brush,
		tolLbl, tol,
		featherLbl, feather,
		widget.NewLabel("预览模式"),
		viewSel,
		st.pickLbl,
		exportBtn,
		resetBtn,
		st.status,
	)

	split := container.NewHSplit(left, st.scroll)
	split.Offset = 0.26
	w.SetContent(split)
	w.Resize(fyne.NewSize(960, 640))
	w.ShowAndRun()
}

func itoa(v int) string {
	if v == 0 {
		return "0"
	}
	neg := v < 0
	if neg {
		v = -v
	}
	buf := [12]byte{}
	i := len(buf)
	for v > 0 {
		i--
		buf[i] = byte('0' + v%10)
		v /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}

func (st *appState) onTap(x, y int) {
	if st.src == nil {
		return
	}
	switch st.tool {
	case "eyedropper":
		r, g, b, _ := rgbaAt(st.src, x, y)
		st.picked = append(st.picked, color.RGBA{R: r, G: g, B: b, A: 255})
		st.hit = ColorMask(st.src, st.picked, st.tol)
		st.pickLbl.SetText("已吸色: " + itoa(len(st.picked)))
		st.status.SetText("吸取颜色,已加入扣色列表")
	case "wand":
		st.hit = FloodSelect(st.src, x, y, st.tol)
		st.status.SetText("魔棒选区已生成")
	}
	st.recompute()
}

func (st *appState) onDrag(x, y int) {
	if st.src == nil || st.tool != "brush" {
		return
	}
	if st.protect == nil {
		st.protect = NewMask(st.src.Bounds().Dx(), st.src.Bounds().Dy())
	}
	BrushPaint(st.protect, x, y, st.brushR, st.erase)
	st.recompute()
}

func (st *appState) recompute() {
	if st.src == nil {
		return
	}
	w, h := st.src.Bounds().Dx(), st.src.Bounds().Dy()
	alpha := ComposeAlpha(st.hit, st.protect, st.feather)
	var view image.Image
	switch st.view {
	case "result":
		view = ComposeResult(st.src, alpha, st.checker)
	case "alpha":
		view = AlphaToGrayImg(alpha, w, h)
	default:
		view = st.src
	}
	st.pix.SetImage(view)
}
