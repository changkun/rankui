package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
)

// mkdir creates a folder if not exists;
// otherwise, it does nothing.
func mkdir(p string) error {
	if _, err := os.Stat(p); errors.Is(err, fs.ErrExist) {
		return nil
	}
	if err := os.Mkdir(p, os.ModePerm); err != nil {
		return err
	}
	return nil
}

func saveJSON(data any, path string) error {
	b, err := json.MarshalIndent(data, "", "    ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(path, b, os.ModePerm); err != nil {
		return err
	}
	return nil
}

// check checks the given error is nil or not, if not, it panics.
func check(err error) {
	if err != nil {
		panic(fmt.Sprintf("unexpected error: %v", err))
	}
}
