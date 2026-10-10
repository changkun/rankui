package enhance

import (
	"image"
	"image/draw"
)

func imageToRGBA(src image.Image) *image.RGBA {
	// No conversion needed if image is an *image.RGBA.
	if dst, ok := src.(*image.RGBA); ok {
		return dst
	}

	// Use the image/draw package to convert to *image.RGBA.
	b := src.Bounds()
	dst := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
	draw.Draw(dst, dst.Bounds(), src, b.Min, draw.Src)
	return dst
}

type Params struct {
	Brightness  float64 `json:"brightness"`
	Contrast    float64 `json:"contrast"`
	Saturation  float64 `json:"saturation"`
	Temperature float64 `json:"temperature"`
	Tint        float64 `json:"tint"`
	Quality     float64 `json:"quality"`
}

func (p Params) ToSlice() []float64 {
	return []float64{
		p.Brightness,
		p.Contrast,
		p.Saturation,
		p.Temperature,
		p.Tint,
	}
}

// Image enhances a given image.
// This reproduces https://github.com/yuki-koyama/enhancer.
func Image(img image.Image, params Params) *image.RGBA {
	m := imageToRGBA(img)
	p := params.ToSlice()
	b := m.Bounds()
	for y := b.Min.Y; y < b.Max.Y; y++ {
		for x := b.Min.X; x < b.Max.X; x++ {
			c := ToColor(m.RGBAAt(x, y))
			m.Set(x, y, Enhance(c, p).ToRGBA())
		}
	}
	return m
}
