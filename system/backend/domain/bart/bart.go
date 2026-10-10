package bart

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

const endpoint = "https://research.poly.red/summarize"

type SummarizeSpace struct {
	// Assume [0, 1]
	ReductionRatio float64 `json:"reduction_ratio"`
	// Assume [0, 1], default 1.0
	TopP float64 `json:"top_p"`
	// Assume [0, 1], default 1.0
	Temperature float64 `json:"temperature"`
	// Assume [0, 1], default 1.0 (1 means no penalty)
	// RepetitionPenalty float64 `json:"repetition_penalty"`  // we easily observe setting this to 1 is the best way to do it.
	// Assume [0, 1], default 1.0 (0 means no penalty)
	LengthPenalty float64 `json:"length_penalty"`
}

func Summarizer(ctx context.Context, text string, config *SummarizeSpace) (ret string, err error) {
	d := struct {
		Text string `json:"text"`
		SummarizeSpace
	}{
		text, SummarizeSpace{
			ReductionRatio: config.ReductionRatio,
			TopP:           config.TopP,
			Temperature:    config.Temperature,
			LengthPenalty:  config.LengthPenalty,
		},
	}

	b, _ := json.Marshal(d)
	r, err := http.NewRequest(http.MethodPost, endpoint, bytes.NewReader(b))
	if err != nil {
		return "", fmt.Errorf("failed to create the request: %w", err)
	}
	r.Header.Set("Content-Type", "application/json; charset=UTF-8")
	resp, err := http.DefaultClient.Do(r.WithContext(ctx))
	if err != nil {
		return "", fmt.Errorf("failed to do the request: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read the response body: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("unexpected response code %v: %v", resp.StatusCode, string(data))
	}

	var out struct {
		Text []string `json:"text"`
	}
	err = json.Unmarshal(data, &out)
	if err != nil {
		return "", fmt.Errorf("failed to parse edit response: %w", err)
	}

	return out.Text[0], nil
}
