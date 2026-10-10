package gpt3_test

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"testing"
	"time"

	"changkun.de/x/human-preference-prior/domain/gpt3"
	"changkun.de/x/human-preference-prior/utils"
)

func TestOptimize(t *testing.T) {
	origin, err := os.ReadFile("../../data/text/init/1.text.txt")
	if err != nil {
		t.Fatal(err)
	}
	ratio := 0.5
	nwords, _ := utils.CountWords(string(origin))
	targetWords := int(float64(nwords) * ratio)
	t.Log(nwords, targetWords)

	start := time.Now()
	o, err := gpt3.Edit(context.Background(), &gpt3.EditInput{
		Text:         string(origin),
		Prompt:       fmt.Sprintf("Summarize the text using %d words", int(float64(nwords)*ratio)),
		Creativity:   0.9,
		Alternatives: 4,
	})
	if err != nil {
		t.Fatal(err)
	}
	dur := time.Since(start)
	t.Log("spend: ", dur.Seconds(), " seconds")
	for _, alternative := range o.Choices {
		n, _ := utils.CountWords(alternative)
		t.Log(n)
	}
}

func TestSummarize(t *testing.T) {
	origin, err := os.ReadFile("../../data/text/tasks/1.txt")
	if err != nil {
		t.Fatal(err)
	}

	optimized, attempts := gpt3.SummarizeByEdit(context.Background(), string(origin), &gpt3.SummarizeByEditSpace{
		ReductionRatio: 0.5,
		Creativity:     0.9,
		Alternatives:   4,
	})

	t.Log("total attempts: ", attempts)
	for id, o := range optimized {
		n, _ := utils.CountWords(o)
		t.Log(id, n, o)
	}
}

func TestTLDR(t *testing.T) {
	type task struct {
		News        string `json:"news"`
		Token       int    `json:"token"`
		GroundTruth string `json:"ground_truth"`
		ID          string `json:"id"`
	}
	origin, err := os.ReadFile("../../data/text/tasks/2.json")
	if err != nil {
		t.Fatal(err)
	}
	var tt task
	err = json.Unmarshal(origin, &tt)
	if err != nil {
		t.Fatal(err)
	}

	start := time.Now()
	o, err := gpt3.SummarizeByTldrCompletion(context.Background(), string(origin), tt.Token, &gpt3.SummarizeByTldrCompletionSpace{
		ReductionRatio:   0.9,
		Creativity:       0.9,
		PresencePenalty:  0.5,
		FrequencyPenalty: 0.5,
	})
	if err != nil {
		t.Fatal(err)
	}
	log.Println(time.Since(start))
	n, _ := utils.CountWords(o)
	t.Log(n, o)
}
