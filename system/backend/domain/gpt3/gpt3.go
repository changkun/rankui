package gpt3

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

var (
	apiKey             = os.Getenv("OPENAI_API_KEY")
	completionEndpoint = "https://api.openai.com/v1/completions"
	editEndpoint       = "https://api.openai.com/v1/edits"
)

type EditInput struct {
	Text         string  `json:"text"`
	Prompt       string  `json:"prompt"`
	Creativity   float64 `json:"creativity"`
	Alternatives int     `json:"alternatives"`
}

type EditOutput struct {
	Choices []string
	Created time.Time
}

func Edit(ctx context.Context, in *EditInput) (*EditOutput, error) {
	type EditRequest struct {
		Model       string  `json:"model"`
		Input       string  `json:"input"`
		Instruction string  `json:"instruction"`
		Temperature float64 `json:"temperature"`
		N           int     `json:"n"`
	}
	type EditResponse struct {
		Object  string `json:"object"`
		Created int64  `json:"created"`
		Choices []struct {
			Text  string `json:"text"`
			Index int    `json:"index"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int64 `json:"prompt_tokens"`
			CompletionTokens int64 `json:"completion_tokens"`
			TotalTokens      int64 `json:"total_tokens"`
		} `json:"usage"`
	}

	d := EditRequest{
		Model:       "text-davinci-edit-001",
		Input:       in.Text,
		Instruction: in.Prompt,
		Temperature: in.Creativity,
		N:           in.Alternatives,
	}

	b, _ := json.Marshal(d)

	r, err := http.NewRequest(http.MethodPost, editEndpoint, bytes.NewReader(b))
	if err != nil {
		return nil, fmt.Errorf("failed to create the request: %w", err)
	}

	r.Header.Set("Content-Type", "application/json; charset=UTF-8")
	r.Header.Set("Authorization", fmt.Sprintf("Bearer %s", apiKey))
	resp, err := http.DefaultClient.Do(r.WithContext(ctx))
	if err != nil {
		return nil, fmt.Errorf("failed to do the request: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read the response body: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected response code %v: %v", resp.StatusCode, string(data))
	}

	var out EditResponse
	err = json.Unmarshal(data, &out)
	if err != nil {
		return nil, fmt.Errorf("failed to parse edit response: %w", err)
	}

	o := &EditOutput{
		Created: time.Unix(out.Created, 0),
		Choices: make([]string, len(out.Choices)),
	}
	for i, c := range out.Choices {
		o.Choices[i] = c.Text
	}
	return o, nil
}

type CompletionInput struct {
	Text             string
	MaxTokens        int
	Creativity       float64
	PresencePenalty  float64
	FrequencyPenalty float64
	Alternatives     int
}
type CompletionOutput struct {
	Choices []string
	Created time.Time
}

func Completion(ctx context.Context, in *CompletionInput) (*CompletionOutput, error) {
	type CompletionRequest struct {
		// ID of the model to use. You can use the List models API to see
		// all of your available models, or see our Model overview for
		// descriptions of them.
		Model string `json:"model,omitempty"`
		// The prompt(s) to generate completions for, encoded as a string,
		// array of strings, array of tokens, or array of token arrays.
		Prompt string `json:"prompt,omitempty"` // tune
		// The maximum number of tokens to generate in the completion.
		// Most models have a context length of 2048 tokens (except for
		// the newest models, which support 4096).
		MaxTokens int `json:"max_tokens,omitempty"` // tune
		// What sampling temperature to use. Higher values means the model
		// will take more risks.
		Temperature float64 `json:"temperature,omitempty"` // tune
		// An alternative to sampling with temperature, called nucleus
		// sampling, where the model considers the results of the tokens
		// with top_p probability mass.
		TopP float64 `json:"top_p,omitempty"`
		// How many completions to generate for each prompt.
		N int `json:"n,omitempty"`
		// Whether to stream back partial progress.
		Stream bool `json:"stream,omitempty"`

		// Up to 4 sequences where the API will stop generating further
		// tokens. The returned text will not contain the stop sequence.
		Stop string `json:"stop,omitempty"`

		// Number between -2.0 and 2.0. Positive values penalize new tokens
		// based on whether they appear in the text so far, increasing the
		// model's likelihood to talk about new topics.
		//
		// https://beta.openai.com/docs/api-reference/parameter-details
		PresencePenalty float64 `json:"presence_penalty,omitempty"` // tune
		// Number between -2.0 and 2.0. Positive values penalize new tokens
		// based on their existing frequency in the text so far, decreasing
		// the model's likelihood to repeat the same line verbatim.
		FrequencyPenalty float64 `json:"frequency_penalty,omitempty"` // tune

		// Generates best_of completions server-side and returns the
		// "best" (the one with the highest log probability per token).
		// Results cannot be streamed.
		BestOf int `json:"best_of,omitempty"`
	}
	type CompletionResponse struct {
		ID      string `json:"id"`
		Object  string `json:"object"`
		Created int64  `json:"created"`
		Model   string `json:"model"`
		Choices []struct {
			Text         string `json:"text"`
			Index        int    `json:"index"`
			LogProbs     int    `json:"logprobs"`
			FinishReason string `json:"finish_reason"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int64 `json:"prompt_tokens"`
			CompletionTokens int64 `json:"completion_tokens"`
			TotalTokens      int64 `json:"total_tokens"`
		} `json:"usage"`
	}

	// TLDR summarization: https://beta.openai.com/examples/default-tldr-summary
	d := CompletionRequest{
		// Parameters we are not searching.
		Model: "text-davinci-002",
		// Model:  "text-ada-001",
		Stream: false,
		Prompt: in.Text + "\n\nTl;dr", // Summarization
		Stop:   "\n",

		// Parameters we are searching for.
		MaxTokens:        in.MaxTokens,
		Temperature:      in.Creativity,
		PresencePenalty:  in.PresencePenalty,
		FrequencyPenalty: in.FrequencyPenalty,
		N:                in.Alternatives,
	}
	b, _ := json.Marshal(d)

	r, err := http.NewRequest(http.MethodPost, completionEndpoint, bytes.NewReader(b))
	if err != nil {
		return nil, fmt.Errorf("failed to create the request: %w", err)
	}

	r.Header.Set("Content-Type", "application/json; charset=UTF-8")
	r.Header.Set("Authorization", fmt.Sprintf("Bearer %s", apiKey))
	resp, err := http.DefaultClient.Do(r.WithContext(ctx))
	if err != nil {
		return nil, fmt.Errorf("failed to do the request: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read the response body: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected response code %v: %v", resp.StatusCode, string(data))
	}

	var out CompletionResponse
	err = json.Unmarshal(data, &out)
	if err != nil {
		return nil, fmt.Errorf("failed to parse edit response: %w", err)
	}

	o := &CompletionOutput{
		Created: time.Unix(out.Created, 0),
		Choices: make([]string, len(out.Choices)),
	}
	for i, c := range out.Choices {
		o.Choices[i] = c.Text
	}
	return o, nil
}
