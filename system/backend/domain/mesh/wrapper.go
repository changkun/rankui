package mesh

import "fmt"

type SimplificationSpace struct {
	// This value is transformed to represent 80% to 100% of reduction ratio.
	// Meaning [0, 1] * 0.8 + 0.2 => [0.8, 1.0].
	ReductionRatio float64 `json:"reduction_ratio"`
	KeepBorder     float64 `json:"keep_border"`
	KeepHardEdge   float64 `json:"keep_hardedge"`
	KeepSharpness  float64 `json:"keep_sharpness"`
	KeepQuad       float64 `json:"keep_quad"`
}

func Simplify(in, out string, s SimplificationSpace) error {
	mc, err := NewMeshConfig(
		Input(in),
		Output(out),
		ReductionRatio(s.ReductionRatio*0.8+0.2),
		KeepBorder(s.KeepBorder),
		KeepHardEdge(s.KeepHardEdge),
		KeepSharpness(s.KeepSharpness),
		QuadPreservation(s.KeepQuad),
	)
	if err != nil {
		return fmt.Errorf("failed to construct mesh configuration: %w", err)
	}

	return mc.Simplify()
}
