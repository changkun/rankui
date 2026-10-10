package optimizers

import (
	"fmt"
	"log"
	"math/rand"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
)

// Note: must synched with front end UI.
const (
	maxIteration  = 20
	initialSample = 4
)

func init() {
	// Initialize random samples at booting for reproducibility.

	rand.Seed(42) // for reproducibility
	PointwiseSamples[4] = RandomSampling(4, initialSample, 1)
	PointwiseSamples[5] = RandomSampling(5, initialSample, 1)
	PairwiseSamples[4] = RandomSampling(4, initialSample, 2)
	PairwiseSamples[5] = RandomSampling(5, initialSample, 2)
	ListwiseSamples[4] = RandomSampling(4, initialSample, 4)
	ListwiseSamples[5] = RandomSampling(5, initialSample, 4)
}

var (
	PointwiseSamples = map[int][][][]float64{}
	PairwiseSamples  = map[int][][][]float64{}
	ListwiseSamples  = map[int][][][]float64{}
)

// RandomSampling is a Go internal random sampling.
func RandomSampling(dim, batch, candidates int) [][][]float64 {
	ret := [][][]float64{}
	for b := 0; b < batch; b++ {
		candidate := [][]float64{}
		for i := 0; i < candidates; i++ {
			param := []float64{}
			for i := 0; i < dim; i++ {
				param = append(param, rand.Float64())
			}
			candidate = append(candidate, param)
		}
		ret = append(ret, candidate)
	}
	return ret
}

// SolbolPointSampling is a wrapper of BoTorch's draw_sobol_samples.
func SobolPointSampling(ui string, dim, samples int) [][][]float64 {
	// Example:
	// python optimizers.py --ui pointwise --action sample --num_samples 5 --seed 42
	cmd := exec.Command("python", dir()+"/../optimizers/optimizers.py",
		"--action", "sample",
		"--ui", ui,
		"--dim", fmt.Sprintf("%d", dim),
		"--num_samples", fmt.Sprintf("%d", samples))
	b, err := cmd.CombinedOutput()
	if err != nil {
		// for unknown reason failed to sample the data, use fixed random samples.
		log.Printf("sampling using BoTorch failed: %v, output: %s", err, string(b))
		return PointwiseSamples[dim]
	}

	// Parse outputs from BoTorch. This only works as a happy path at the moment.
	lines := strings.Split(strings.TrimSuffix(string(b), "\n"), "\n")
	ret := [][][]float64{}
	for _, line := range lines {
		candidates := strings.Split(strings.TrimSuffix(strings.TrimPrefix(line, "["), "]"), "], [")

		points := [][]float64{}
		for _, candidate := range candidates {
			params := strings.Split(strings.TrimSuffix(strings.TrimPrefix(candidate, "["), "]"), ", ")
			ps := []float64{}
			for _, p := range params {
				pp, _ := strconv.ParseFloat(p, 64)
				ps = append(ps, pp)
			}
			points = append(points, ps)
		}
		ret = append(ret, points)
	}
	return ret
}

func PointwiseBO(domain, userID, sessionID, taskID string, dim int) []float64 {
	log.Println("using pointwise BO: ", domain, userID, sessionID, taskID)
	// Example:
	// python optimizers.py --ui pointwise --action estimate --domain text
	// 		--user_id changkun --session_id testsession --task_id 3
	cmd := exec.Command("python", dir()+"/../optimizers/optimizers.py",
		"--ui", "pointwise",
		"--action", "estimate",
		"--domain", domain,
		"--user_id", userID,
		"--session_id", sessionID,
		"--task_id", taskID,
		"--dim", fmt.Sprintf("%d", dim),
	)
	log.Println("exec: ", cmd.String())
	b, err := cmd.CombinedOutput()
	if err != nil {
		// for unknown reason failed to sample the data, use fixed random samples.
		log.Printf("sampling using BoTorch failed: %v, output: %s", err, string(b))
		// FIXME:
		return []float64{0, 0, 0, 0, 0}
	}
	log.Println("estimation: ", string(b))

	params := strings.Split(strings.TrimSuffix(strings.TrimPrefix(string(b), "["), "]\n"), ", ")
	ps := []float64{}
	for _, p := range params {
		pp, err := strconv.ParseFloat(p, 64)
		if err != nil {
			panic(err)
		}
		ps = append(ps, pp)
	}
	return ps
}

func PairwiseBO(domain, userID, sessionID, taskID string, dim int) [][]float64 {
	log.Println("using pairwise BO: ", domain, userID, sessionID, taskID)
	// Example:
	// python optimizers.py --ui pairwise --action estimate --domain text
	// 		--user_id changkun --session_id testsession --task_id 3
	cmd := exec.Command("python", dir()+"/../optimizers/optimizers.py",
		"--ui", "pairwise",
		"--action", "estimate",
		"--domain", domain,
		"--user_id", userID,
		"--session_id", sessionID,
		"--task_id", taskID,
		"--dim", fmt.Sprintf("%d", dim),
	)
	log.Println("exec: ", cmd.String())
	b, err := cmd.CombinedOutput()
	if err != nil {
		// for unknown reason failed to sample the data, use fixed random samples.
		log.Printf("sampling using BoTorch failed: %v, output: %s", err, string(b))
		// FIXME:
		return [][]float64{{0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}}
	}
	log.Println("estimation: ", string(b))

	outputs := strings.Split(strings.TrimSuffix(string(b), "\n"), "\n")
	ret := [][]float64{}
	for _, o := range outputs {
		params := strings.Split(strings.TrimSuffix(strings.TrimPrefix(o, "["), "]"), ", ")
		ps := []float64{}
		for _, p := range params {
			pp, err := strconv.ParseFloat(p, 64)
			if err != nil {
				panic(err)
			}
			ps = append(ps, pp)
		}
		ret = append(ret, ps)
	}
	return ret
}

func ListwiseBOrating(domain, userID, sessionID, taskID string, dim int) [][]float64 {
	log.Println("using listwise-rating BO: ", domain, userID, sessionID, taskID)
	// Example:
	// python optimizers.py --ui listwise-rating --action estimate --domain text
	// 		--user_id changkun --session_id testsession --task_id 3
	cmd := exec.Command("python", dir()+"/../optimizers/optimizers.py",
		"--ui", "listwise-rating",
		"--action", "estimate",
		"--domain", domain,
		"--user_id", userID,
		"--session_id", sessionID,
		"--task_id", taskID,
		"--dim", fmt.Sprintf("%d", dim),
	)
	log.Println("exec: ", cmd.String())
	b, err := cmd.CombinedOutput()
	if err != nil {
		// for unknown reason failed to sample the data, use fixed random samples.
		log.Printf("sampling using BoTorch failed: %v, output: %s", err, string(b))
		// FIXME:
		return [][]float64{{0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}}
	}
	log.Println("estimation: ", string(b))

	outputs := strings.Split(strings.TrimSuffix(string(b), "\n"), "\n")
	ret := [][]float64{}
	for _, o := range outputs {
		params := strings.Split(strings.TrimSuffix(strings.TrimPrefix(o, "["), "]"), ", ")
		ps := []float64{}
		for _, p := range params {
			pp, err := strconv.ParseFloat(p, 64)
			if err != nil {
				panic(err)
			}
			ps = append(ps, pp)
		}
		ret = append(ret, ps)
	}
	return ret
}

func ListwiseBOnotie(domain, userID, sessionID, taskID string, dim int) [][]float64 {
	log.Println("using listwise-notie BO: ", domain, userID, sessionID, taskID)
	// Example:
	// python optimizers.py --ui listwise-rating --action estimate --domain text
	// 		--user_id changkun --session_id testsession --task_id 3
	cmd := exec.Command("python", dir()+"/../optimizers/optimizers.py",
		"--ui", "listwise-notie",
		"--action", "estimate",
		"--domain", domain,
		"--user_id", userID,
		"--session_id", sessionID,
		"--task_id", taskID,
		"--dim", fmt.Sprintf("%d", dim),
	)
	log.Println("exec: ", cmd.String())
	b, err := cmd.CombinedOutput()
	if err != nil {
		// for unknown reason failed to sample the data, use fixed random samples.
		log.Printf("sampling using BoTorch failed: %v, output: %s", err, string(b))
		// FIXME:
		return [][]float64{{0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}}
	}
	log.Println("estimation: ", string(b))

	outputs := strings.Split(strings.TrimSuffix(string(b), "\n"), "\n")
	ret := [][]float64{}
	for _, o := range outputs {
		params := strings.Split(strings.TrimSuffix(strings.TrimPrefix(o, "["), "]"), ", ")
		ps := []float64{}
		for _, p := range params {
			pp, err := strconv.ParseFloat(p, 64)
			if err != nil {
				panic(err)
			}
			ps = append(ps, pp)
		}
		ret = append(ret, ps)
	}
	return ret
}

func ListwiseBOcantie(domain, userID, sessionID, taskID string, dim int) [][]float64 {
	log.Println("using listwise-cantie BO: ", domain, userID, sessionID, taskID)
	// Example:
	// python optimizers.py --ui listwise-rating --action estimate --domain text --user_id changkun --session_id testsession --task_id 3
	cmd := exec.Command("python", dir()+"/../optimizers/optimizers.py",
		"--ui", "listwise-cantie",
		"--action", "estimate",
		"--domain", domain,
		"--user_id", userID,
		"--session_id", sessionID,
		"--task_id", taskID,
		"--dim", fmt.Sprintf("%d", dim),
	)
	log.Println("exec: ", cmd.String())
	b, err := cmd.CombinedOutput()
	if err != nil {
		// for unknown reason failed to sample the data, use fixed random samples.
		log.Printf("sampling using BoTorch failed: %v, output: %s", err, string(b))
		// FIXME:
		return [][]float64{{0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}}
	}
	log.Println("estimation: ", string(b))

	outputs := strings.Split(strings.TrimSuffix(string(b), "\n"), "\n")
	ret := [][]float64{}
	for _, o := range outputs {
		params := strings.Split(strings.TrimSuffix(strings.TrimPrefix(o, "["), "]"), ", ")
		ps := []float64{}
		for _, p := range params {
			pp, err := strconv.ParseFloat(p, 64)
			if err != nil {
				panic(err)
			}
			ps = append(ps, pp)
		}
		ret = append(ret, ps)
	}
	return ret
}

func ListwiseBOranking(domain, userID, sessionID, taskID string, dim int) [][]float64 {
	log.Println("using listwise-ranking BO: ", domain, userID, sessionID, taskID)
	// Example:
	// python optimizers.py --ui listwise-rating --action estimate --domain text
	// 		--user_id changkun --session_id testsession --task_id 3
	cmd := exec.Command("python", dir()+"/../optimizers/optimizers.py",
		"--ui", "listwise-ranking",
		"--action", "estimate",
		"--domain", domain,
		"--user_id", userID,
		"--session_id", sessionID,
		"--task_id", taskID,
		"--dim", fmt.Sprintf("%d", dim),
	)
	log.Println("exec: ", cmd.String())
	b, err := cmd.CombinedOutput()
	if err != nil {
		// for unknown reason failed to sample the data, use fixed random samples.
		log.Printf("sampling using BoTorch failed: %v, output: %s", err, string(b))
		// FIXME:
		return [][]float64{{0, 0, 0, 0, 0}, {0, 0, 0, 0, 0}}
	}
	log.Println("estimation: ", string(b))

	outputs := strings.Split(strings.TrimSuffix(string(b), "\n"), "\n")
	ret := [][]float64{}
	for _, o := range outputs {
		params := strings.Split(strings.TrimSuffix(strings.TrimPrefix(o, "["), "]"), ", ")
		ps := []float64{}
		for _, p := range params {
			pp, err := strconv.ParseFloat(p, 64)
			if err != nil {
				panic(err)
			}
			ps = append(ps, pp)
		}
		ret = append(ret, ps)
	}
	return ret
}

func dir() (fn string) {
	_, fn, _, _ = runtime.Caller(0)
	return filepath.Dir(fn)
}
