package conv_test

import (
	"path/filepath"
	"runtime"
	"testing"

	"changkun.de/x/human-preference-prior/domain/mesh/conv"
)

func TestFbx2Obj(t *testing.T) {
	err := conv.Fbx2Obj(dir()+"/../testdata/monkey.fbx", dir()+"/../testdata/monkey-meshconv.obj")
	if err != nil {
		t.Fatal(err)
	}
}
func TestObj2Fbx(t *testing.T) {
	err := conv.Obj2Fbx(dir()+"/../testdata/monkey.obj", dir()+"/../testdata/monkey-meshconv.fbx")
	if err != nil {
		t.Fatal(err)
	}
}

func dir() (fn string) {
	_, fn, _, _ = runtime.Caller(0)
	return filepath.Dir(fn)
}
