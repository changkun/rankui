package mesh

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"changkun.de/x/human-preference-prior/domain/mesh/conv"
)

type Option func(mc *MeshConfig) error

func Input(path string) Option {
	return func(mc *MeshConfig) error {
		if strings.HasSuffix(path, ".obj") ||
			strings.HasSuffix(path, ".fbx") {
			mc.Input = path
			return nil
		}

		return fmt.Errorf("field: only support .obj and .fbx files, got: %s", path)
	}
}

func Output(path string) Option {
	return func(mc *MeshConfig) error {
		if strings.HasSuffix(path, ".obj") ||
			strings.HasSuffix(path, ".fbx") {
			mc.Output = path
			return nil
		}

		return fmt.Errorf("field: only support .obj and .fbx files")
	}
}

func ReductionRatio(ratio float64) Option {
	return func(mc *MeshConfig) error {
		mc.ReductionRatio = ratio
		return nil
	}
}

func KeepBorder(f float64) Option {
	return func(mc *MeshConfig) error {
		mc.KeepBorder = f
		return nil
	}
}

func KeepCreaseEdge(f float64) Option {
	return func(mc *MeshConfig) error {
		mc.KeepCreaseEdge = f
		return nil
	}
}

func KeepHardEdge(f float64) Option {
	return func(mc *MeshConfig) error {
		mc.KeepHardEdge = f
		return nil
	}
}

func KeepSharpness(f float64) Option {
	return func(mc *MeshConfig) error {
		mc.KeepSharpness = f
		return nil
	}
}

func QuadPreservation(f float64) Option {
	return func(mc *MeshConfig) error {
		mc.KeepQuad = f
		return nil
	}
}

func Symmetry(f float64) Option {
	return func(mc *MeshConfig) error {
		mc.Symmetry = f
		return nil
	}
}

// MeshConfig is the configuration for FlowLine preservation simplification.
type MeshConfig struct {
	Input  string
	Output string

	// ReductionRatio specifies the number of percentage of reduced polygons.
	ReductionRatio float64

	// If keepBorder is on, this flag specifies the weight to assign
	// to borders. Setting this value to 0 will disable border
	// preservation and a value of 1 will exactly preserve all border
	// vertices which is useful for matching adjacent meshes.
	// Default is 0.5.
	KeepBorder float64

	// If keepCreaseEdge is on, this flag specifies the weight to
	// assign to crease edges. Setting this value to 0 will
	// disable crease edge preservation and a value of 1 will
	// exactly preserve all crease edges. Default is 0.5.
	KeepCreaseEdge float64

	// If keepHardEdge is on, this flag specifies the weight to assign
	// to hard edges. Setting this value to 0 will disable hard edge
	// preservation and a value of 1 will exactly preserve all hard edges.
	KeepHardEdge float64

	// KeepSharpness controls the balance between preserving
	// small, sharp details versus larger shapes. At
	// low values, details that are small relative to
	// the general shape of the object are more likely
	// to be collapsed. At high values, they are more
	// likely to be kept. Default is 0.
	KeepSharpness float64

	// This flag controls how much consideration is
	// given to oreserving quad faces during reduction.
	// A higher weight means the reduction will try
	// harder to keep quad faces and avoid creation
	// of triangles. If the keepQuadsWeight flag is
	// set to 1.0 then a special quad reduction algorithm
	// is used that does a better job of preserving
	// quads. Howver, this special quad reduction
	// algorithm does not support symmetry so those
	// flags will be ignored when the keepQuadsWeight
	// flag is set to 1.0. Default is 0.
	KeepQuad float64

	// Tolerance to use when applying symmetry. For
	// each vertex of the mesh, we find its exact
	// symmetric point, then we look for the closest
	// vertex to the exact symmetry up to the tolerance
	// distance. Higher values risk finding more
	// spurious symmetries, lower values might miss
	// symmetries. The value is distance in object
	// space. This flag only applies when the
	// useVirtualSymmetry flag is not set to 0. Default is 0.
	Symmetry float64
}

func NewMeshConfig(opts ...Option) (*MeshConfig, error) {
	mc := &MeshConfig{
		ReductionRatio: 0.95,
		KeepBorder:     0.5,
		KeepCreaseEdge: 0.5,
		KeepHardEdge:   0.5,
		KeepSharpness:  0.5,
		KeepQuad:       0.5,
		Symmetry:       0.5,
	}
	for _, opt := range opts {
		if err := opt(mc); err != nil {
			return nil, err
		}
	}
	return mc, nil
}

func (mc *MeshConfig) BuildConfigs() string {
	type config struct {
		ReductionRatio float64 `json:"reduction_ratio"`
		KeepBorder     float64 `json:"keep_border"`
		KeepCreaseEdge float64 `json:"keep_crease"`
		KeepHardEdge   float64 `json:"keep_hardedge"`
		KeepSharpness  float64 `json:"keep_sharpness"`
		KeepQuad       float64 `json:"keep_quad"`
		Symmetry       float64 `json:"symmetry"`
	}

	c := &config{
		ReductionRatio: mc.ReductionRatio,
		KeepBorder:     mc.KeepBorder,
		KeepCreaseEdge: mc.KeepCreaseEdge,
		KeepHardEdge:   mc.KeepHardEdge,
		KeepSharpness:  mc.KeepSharpness,
		KeepQuad:       mc.KeepQuad,
		Symmetry:       mc.Symmetry,
	}
	b, _ := json.Marshal(c)
	return string(b)
}

func (mc *MeshConfig) Simplify() error {
	d, err := os.MkdirTemp("", "polyred_flowline-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(d)

	conf := filepath.Join(d, "config.json")
	log.Println("config wrote to: ", conf)
	confContent := mc.BuildConfigs()
	log.Println("config content: ", string(confContent))
	if err := os.WriteFile(conf, []byte(confContent), os.ModePerm); err != nil {
		return fmt.Errorf("flowline: failed to simplify: %w", err)
	}

	inputModel := mc.Input // by default, we assume an FBX input model.
	switch {
	// If the input is not in FBX but in OBJ or PLY, we should convert
	// it to an FBX.
	case strings.HasSuffix(mc.Input, ".obj"):
		inputModel = filepath.Join(d, "in.fbx")
		conv.Obj2Fbx(mc.Input, inputModel)
	}
	outputModel := mc.Output
	switch {
	case strings.HasSuffix(mc.Output, ".obj"):
		outputModel = filepath.Join(d, "out.fbx")
	}

	mayapy, err := getMayaPyInterpreter()
	if err != nil {
		return fmt.Errorf("flowline: cannot find maya interpreter: %w", err)
	}

	cmd := exec.Command(mayapy, dir()+"/flow.py", inputModel, outputModel, conf)
	out, err := cmd.CombinedOutput()
	if err != nil {
		if runtime.GOOS != "linux" {
			return fmt.Errorf("flowline: failed with error: %w", err)
		}
		if runtime.GOOS == "linux" && !strings.Contains(err.Error(), "core dump") {
			return fmt.Errorf("flowline: failed with error %w: %v", err, string(out))
		}
	}
	log.Println(string(out))
	if strings.Compare(outputModel, mc.Output) != 0 {
		log.Println("converting from fbx to obj output: ")
		log.Println(outputModel)
		log.Println(mc.Output)
		return conv.Fbx2Obj(outputModel, mc.Output)
	}

	return nil
}

func getMayaPyInterpreter() (string, error) {
	path := ""
	if runtime.GOOS == "darwin" {
		path = "/Applications/Autodesk/maya%s/Maya.app/Contents/bin/mayapy"
	} else if runtime.GOOS == "linux" {
		path = "/usr/autodesk/maya%s/bin/mayapy"
	} else if runtime.GOOS == "windows" { // windows
		path = "C:\\Program Files\\Autodesk\\maya%s\\bin\\mayapy.exe"
	} else {
		return "", errors.New("flowline: unsupported platform")
	}

	year := []string{"2019", "2020", "2021", "2022"}
	for _, y := range year {
		p := fmt.Sprintf(path, y)
		if _, err := os.Stat(p); errors.Is(err, os.ErrNotExist) {
			continue
		}
		return p, nil
	}

	return "", errors.New("flowline: missing interpreter")
}

func dir() (fn string) {
	_, fn, _, _ = runtime.Caller(0)
	return filepath.Dir(fn)
}
