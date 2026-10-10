package conv

import (
	"errors"
	"fmt"
	"log"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

func Fbx2Obj(in, out string) error {
	if !strings.HasSuffix(in, ".fbx") {
		return errors.New("input file must has .fbx suffix")
	}
	if !strings.HasSuffix(out, ".obj") {
		return errors.New("output file must has .obj suffix")
	}

	cmd := exec.Command("blender", "--background", "--python", dir()+"/conv.py", "--", "fbx2obj", in, out)
	b, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%w: %s", err, string(b))
	}
	log.Println(string(b))
	return nil
}

func Obj2Fbx(in, out string) error {
	if !strings.HasSuffix(in, ".obj") {
		return errors.New("input file must has .fbx suffix")
	}
	if !strings.HasSuffix(out, ".fbx") {
		return errors.New("output file must has .obj suffix")
	}

	cmd := exec.Command("blender", "--background", "--python", dir()+"/conv.py", "--", "obj2fbx", in, out)
	b, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%w: %s", err, string(b))
	}
	log.Println(string(b))
	return nil
}

func dir() (fn string) {
	_, fn, _, _ = runtime.Caller(0)
	return filepath.Dir(fn)
}
