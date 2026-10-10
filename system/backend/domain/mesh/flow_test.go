package mesh_test

import (
	"path/filepath"
	"runtime"
	"testing"

	"changkun.de/x/human-preference-prior/domain/mesh"
)

func TestFlowline(t *testing.T) {
	tests := []struct {
		Input  string
		Output string
	}{
		{
			Input:  "/./testdata/monkey.obj",
			Output: "/./testdata/monkey-flowline-obj2obj.obj",
		},
		{
			Input:  "/./testdata/monkey.obj",
			Output: "/./testdata/monkey-flowline-obj2fbx.fbx",
		},
		{
			Input:  "/./testdata/monkey.fbx",
			Output: "/./testdata/monkey-flowline-fbx2obj.obj",
		},
		{
			Input:  "/./testdata/monkey.fbx",
			Output: "/./testdata/monkey-flowline-fbx2fbx.fbx",
		},
	}

	for _, tt := range tests {
		mc, err := mesh.NewMeshConfig(
			mesh.Input(dir()+tt.Input),
			mesh.Output(dir()+tt.Output),
			mesh.ReductionRatio(0.95),
		)
		if err != nil {
			t.Fatal(err)
		}

		err = mc.Simplify()
		if err != nil {
			t.Fatal(err)
		}
	}
}

func dir() (fn string) {
	_, fn, _, _ = runtime.Caller(0)
	return filepath.Dir(fn)
}
