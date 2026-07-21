package main

// Fyne 界面：加载图片(按钮/拖拽)、吸管/魔棒/笔刷三工具(横排按钮)、容差/羽化/笔刷大小、原图/结果/Alpha 预览(横排按钮)、导出 PNG(自动保存到原图同目录)。
// 布局原则：左侧固定宽度窄工具栏(160px) + 右侧自适应画布。
import (
	"image"
	"image/color"
	_ "embed"
	"os"
	"path/filepath"
	"strings"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/canvas"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"
)

//go:embed 图标/MMY-AI-Studio-icon.ico
var appIcon []byte

const leftPanelWidth = 160 // 左侧栏固定像素宽度

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
	img.FillMode = canvas.ImageFillContain
	img.ScaleMode = canvas.ImageScaleSmooth
	return &pixRenderer{p: p, img: img}
}

func (p *PixCanvas) MinSize() fyne.Size {
	return fyne.NewSize(200, 200)
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
	scale := sx
	if sy < scale {
		scale = sy
	}
	dw := float32(b.Dx()) / scale
	dh := float32(b.Dy()) / scale
	ox := (p.curW - dw) / 2
	oy := (p.curH - dh) / 2
	x := int((float64(pos.X) - float64(ox)) * float64(scale))
	y := int((float64(pos.Y) - float64(oy)) * float64(scale))
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

// ---- 固定宽度布局(锁定左栏不随内容膨胀) ----

type fixedWidthLayout struct{}

func (l *fixedWidthLayout) MinSize(objects []fyne.CanvasObject) fyne.Size {
	var h float32
	for _, o := range objects {
		ms := o.MinSize()
		h += ms.Height
	}
	return fyne.NewSize(leftPanelWidth, h)
}

func (l *fixedWidthLayout) Layout(objects []fyne.CanvasObject, size fyne.Size) {
	x, y := float32(0), float32(0)
	for _, o := range objects {
		ms := o.MinSize()
		o.Resize(fyne.NewSize(leftPanelWidth, ms.Height))
		o.Move(fyne.Position{X: x, Y: y})
		y += ms.Height
	}
}

// ---- 可选中按钮组（原生 Button 外观 + 独立选中指示条） ----
//
// 每个选项 = 自定义布局 [widget.Button 占主体 + 底部 2px 指示条]。
// 指示条仅在选中时显示 PrimaryColor。按钮保留 Fyne 原生圆角/主题/hover 效果。

const indicatorHeight = float32(2) // 选中指示条高度(px)

type selectBtnLayout struct {
	btn *widget.Button
	ind *canvas.Rectangle
}

func (l *selectBtnLayout) MinSize(objects []fyne.CanvasObject) fyne.Size {
	return l.btn.MinSize()
}

func (l *selectBtnLayout) Layout(objects []fyne.CanvasObject, size fyne.Size) {
	// 按钮占满除底部指示条外的所有空间
	btnH := size.Height - indicatorHeight
	l.btn.Resize(fyne.NewSize(size.Width, btnH))
	l.btn.Move(fyne.Position{X: 0, Y: 0})
	// 指示条在底部, 贯穿全宽
	l.ind.Resize(fyne.NewSize(size.Width, indicatorHeight))
	l.ind.Move(fyne.Position{X: 0, Y: btnH})
}

// selectBtn 单个选项: 原生 Button + 可控的底部指示条。
type selectBtn struct {
	container *fyne.Container // 用 selectBtnLayout 排布: [button, indicator]
	btn       *widget.Button
	ind       *canvas.Rectangle
	label     string
}

func newSelectBtn(label string, onTapped func()) *selectBtn {
	btn := widget.NewButton(label, onTapped)
	ind := canvas.NewRectangle(color.Transparent)
	layout := &selectBtnLayout{btn: btn, ind: ind}
	c := container.New(layout, btn, ind)
	return &selectBtn{container: c, btn: btn, ind: ind, label: label}
}

// SetSelected 控制底部指示条可见性。
func (b *selectBtn) SetSelected(selected bool) {
	if selected {
		b.ind.FillColor = theme.PrimaryColor()
	} else {
		b.ind.FillColor = color.Transparent
	}
	b.ind.Refresh()
}

// Layout 返回包含按钮和指示条的容器。
func (b *selectBtn) Layout() *fyne.Container { return b.container }

// btnGroup 一排互斥可选中按钮。
type btnGroup struct {
	items   []*selectBtn
	onChange func(string)
}

func newBtnGroup(options []string, onChange func(string)) *btnGroup {
	g := &btnGroup{onChange: onChange}
	for _, opt := range options {
		opt := opt
		item := newSelectBtn(opt, func() {
			g.Select(opt)
		})
		g.items = append(g.items, item)
	}
	return g
}

// Select 选中指定选项: 更新所有指示条 + 触发回调。
func (g *btnGroup) Select(s string) {
	for _, item := range g.items {
		item.SetSelected(item.label == s)
	}
	if g.onChange != nil {
		g.onChange(s)
	}
}

// Layout 返回横排容器, 每个元素是 [Button+底部指示条] 的组合。
func (g *btnGroup) Layout() *fyne.Container {
	objs := make([]fyne.CanvasObject, len(g.items))
	for i, item := range g.items {
		objs[i] = item.Layout()
	}
	return container.NewHBox(objs...)
}

func compactSlider(name string, initVal, min, max float64, onChanged func(int)) (*widget.Label, *widget.Slider) {
	lbl := widget.NewLabel(name + ": " + itoa(int(initVal)))
	sld := widget.NewSlider(min, max)
	sld.Value = initVal
	sld.OnChanged = func(v float64) {
		iv := int(v)
		lbl.SetText(name + ": " + itoa(iv))
		if onChanged != nil {
			onChanged(iv)
		}
	}
	return lbl, sld
}

// ---- 应用状态 ----

type appState struct {
	src      *image.RGBA
	srcPath  string // 当前加载的图片路径(用于导出到同目录)
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
	split    *container.Split
	tools    *btnGroup
	views    *btnGroup
	hintLbl  *widget.Label // 右侧画布底部提示(拖拽图片/已加载)
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

var supportedExts = map[string]bool{
	".png": true, ".jpg": true, ".jpeg": true, ".bmp": true, ".gif": true,
}

func isImageFile(path string) bool {
	return supportedExts[strings.ToLower(filepath.Ext(path))]
}

func findIconDir() string {
	exe, err := os.Executable()
	if err == nil {
		candidate := filepath.Join(filepath.Dir(exe), "..", "图标")
		if fi, e := os.Stat(candidate); e == nil && fi.IsDir() {
			return candidate
		}
		candidate = filepath.Join(filepath.Dir(exe), "图标")
		if fi, e := os.Stat(candidate); e == nil && fi.IsDir() {
			return candidate
		}
	}
	if fi, e := os.Stat("图标"); e == nil && fi.IsDir() {
		return "图标"
	}
	return ""
}

// truncText 截断过长文本(避免 Label 撑宽布局)。
func truncText(text string, maxLen int) string {
	if len(text) <= maxLen {
		return text
	}
	runes := []rune(text)
	if len(runes) <= maxLen {
		return text
	}
	return string(runes[:maxLen-1]) + "…"
}

// Run 启动 Fyne 应用主窗口。
func Run() {
	a := app.New()
	a.SetIcon(fyne.NewStaticResource("icon.ico", appIcon))

	w := a.NewWindow("MMY iconCut")

	st := &appState{
		tool:   "魔棒",
		brushR: 20,
		tol:    32,
		feather: 0,
		view:   "结果",
		status:  widget.NewLabel("请先加载一张带背景的图标"),
		pickLbl: widget.NewLabel("已吸色: 0"),
	}
	st.pix = NewPixCanvas(st.onTap, st.onDrag)
	st.scroll = container.NewScroll(st.pix)

	// ---- 加载/导出按钮 ----
	loadBtn := widget.NewButton("加载图片", func() {
		dialog.ShowFileOpen(func(r fyne.URIReadCloser, err error) {
			if err != nil || r == nil {
				return
			}
			st.loadImage(r.URI().Path())
		}, w)
	})

	exportBtn := widget.NewButton("导出 PNG", func() {
		if st.src == nil || st.srcPath == "" {
			st.status.SetText("请先加载图片")
			return
		}
		dir := filepath.Dir(st.srcPath)
		ext := filepath.Ext(st.srcPath)
		base := strings.TrimSuffix(filepath.Base(st.srcPath), ext)
		outPath := filepath.Join(dir, base+"_cut.png")

		alpha := ComposeAlpha(st.hit, st.protect, st.feather)
		out := ApplyAlpha(st.src, alpha)
		if e := SavePNG(outPath, out); e != nil {
			st.status.SetText("导出失败: " + e.Error())
			return
		}
		st.status.SetText("已导出: " + truncText(base+"_cut", 16))
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

	// ---- 工具选择(横排自绘按钮) ----
	st.tools = newBtnGroup([]string{"吸管", "魔棒", "笔刷"}, func(s string) {
		st.tool = s
	})
	st.tools.Select("魔棒")

	eraseChk := widget.NewCheck("擦除", func(b bool) { st.erase = b })

	tolLbl, tolSld := compactSlider("容差", 32, 0, 255, func(v int) {
		st.tol = v
		st.recompute()
	})

	featherLbl, featherSld := compactSlider("羽化", 0, 0, 50, func(v int) {
		st.feather = v
		st.recompute()
	})

	brushLbl, brushSld := compactSlider("笔刷", 20, 2, 80, func(v int) {
		st.brushR = v
	})

	st.views = newBtnGroup([]string{"原图", "结果", "Alpha"}, func(s string) {
		st.view = s
		st.recompute()
	})
	st.views.Select("结果")

	// ---- 左侧工具栏(用固定宽度布局包裹) ----
	leftInner := container.NewVBox(
		loadBtn,
		widget.NewLabel("工具"),
		st.tools.Layout(),
		eraseChk,
		brushLbl, brushSld,
		tolLbl, tolSld,
		featherLbl, featherSld,
		widget.NewLabel("预览"),
		st.views.Layout(),
		st.pickLbl,
		exportBtn,
		resetBtn,
	)
	left := container.New(&fixedWidthLayout{}, leftInner)

	// ---- 右侧: 画布(无图时底部显示居中提示) ----
	st.hintLbl = widget.NewLabel("拖拽图片到这里")
	st.hintLbl.Alignment = fyne.TextAlignCenter
	st.hintLbl.Hide()

	st.scroll = container.NewScroll(st.pix)
	rightArea := container.NewBorder(nil, st.hintLbl, nil, nil, st.scroll)

	st.split = container.NewHSplit(left, rightArea)
	st.split.Offset = 0.22

	// ---- 全局底部状态栏(横跨整个窗口宽度) ----
	st.status.Alignment = fyne.TextAlignLeading
	statusSep := canvas.NewRectangle(theme.Color(theme.ColorNameSeparator))
	statusSep.SetMinSize(fyne.NewSize(0, 1))
	statusBar := container.NewVBox(statusSep, st.status)

	content := container.NewBorder(nil, statusBar, nil, nil, st.split)
	w.SetContent(content)

	// 初始无图状态：显示拖拽提示
	st.hintLbl.Show()

	// ---- 拖拽接收 ----
	w.SetOnDropped(func(pos fyne.Position, uris []fyne.URI) {
		for _, u := range uris {
			path := u.Path()
			if path != "" && isImageFile(path) {
				st.loadImage(path)
				break
			}
		}
	})

	w.Resize(fyne.NewSize(780, 560))
	w.CenterOnScreen()
	w.ShowAndRun()
}

// loadImage 统一入口：加载图片 -> 重置状态 -> 刷新画布。
func (st *appState) loadImage(path string) {
	img, e := LoadRGBA(path)
	if e != nil {
		st.status.SetText("加载失败: " + e.Error())
		return
	}
	st.src = img
	st.srcPath = path
	st.picked = nil
	st.hit = NewMask(img.Bounds().Dx(), img.Bounds().Dy())
	st.protect = NewMask(img.Bounds().Dx(), img.Bounds().Dy())
	st.checker = Checkerboard(img.Bounds().Dx(), img.Bounds().Dy(), 16)
	st.pickLbl.SetText("已吸色: 0")
	baseName := strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
	st.status.SetText("已加载: " + truncText(baseName, 12))
	st.pix.SetImage(img)
	st.scroll.Refresh()
	st.hintLbl.Hide()

	if st.split != nil {
		st.split.Offset = 0.22
	}
	st.recompute()
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
	case "吸管":
		r, g, b, _ := rgbaAt(st.src, x, y)
		st.picked = append(st.picked, color.RGBA{R: r, G: g, B: b, A: 255})
		st.hit = ColorMask(st.src, st.picked, st.tol)
		st.pickLbl.SetText("已吸色: " + itoa(len(st.picked)))
		st.status.SetText("吸取颜色, 已加入扣色列表")
	case "魔棒":
		st.hit = FloodSelect(st.src, x, y, st.tol)
		st.status.SetText("魔棒选区已生成")
	}
	st.recompute()
}

func (st *appState) onDrag(x, y int) {
	if st.src == nil || st.tool != "笔刷" {
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
	case "结果":
		view = ComposeResult(st.src, alpha, st.checker)
	case "alpha":
		view = AlphaToGrayImg(alpha, w, h)
	default:
		view = st.src
	}
	st.pix.SetImage(view)
}
