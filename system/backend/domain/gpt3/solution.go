package gpt3

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"changkun.de/x/human-preference-prior/utils"
	"github.com/google/uuid"
)

type SummarizeByTldrCompletionSpace struct {
	// Assume [0, 1]
	ReductionRatio float64 `json:"reduction_ratio"`
	// Assume [0, 1]
	Creativity float64 `json:"creativity"`
	// Assume [0, 1]
	PresencePenalty float64 `json:"presence_penalty"`
	// Assume [0, 1]
	FrequencyPenalty float64 `json:"frequency_penalty"`
}

func SummarizeByTldrCompletion(ctx context.Context, originText string, token int, config *SummarizeByTldrCompletionSpace) (ret string, err error) {
	const (
		maxRetry        = 5
		delay           = 500 * time.Millisecond
		tolerance       = 0.25
		maxAllowedToken = 4000
	)
	remainToken := maxAllowedToken - token
	targetToken := int((1.0 - config.ReductionRatio) * float64(token))
	if targetToken > remainToken { // if we don't have enough token space, let's do our best to summarize.
		targetToken = remainToken
	}

	// Note: We cannot guarantee openAI will give us response immediately.
	// Let's retry maximum 10 times.
	if err := retry(maxRetry, delay, func() error {
		apiInput := &CompletionInput{
			Text: originText,
			// https://beta.openai.com/tokenizer
			MaxTokens:        targetToken,
			Creativity:       config.Creativity,
			PresencePenalty:  config.PresencePenalty*4.0 - 2.0,  // rescale
			FrequencyPenalty: config.FrequencyPenalty*4.0 - 2.0, // rescale
			Alternatives:     1,
		}
		o, err := Completion(ctx, apiInput)
		if err != nil {
			return err
		}

		// Search those that meets the target.
		for _, result := range o.Choices {
			tokens := []string{":", " ", "\n", "-", "–"}
			for i := 0; i < 5; i++ {
				for _, token := range tokens {
					result = strings.TrimPrefix(result, token)
				}
			}
			ret = result
		}
		if ret != "" {
			return nil
		}

		return errors.New("failed to find all results")
	}); err != nil {
		log.Println(err)
	}

	if n, _ := utils.CountWords(ret); n < 5 {
		return "", errors.New("failed")
	}
	return ret, nil
}

type SummarizeByEditSpace struct {
	ReductionRatio float64
	Creativity     float64
	Alternatives   int
}

func SummarizeByEdit(ctx context.Context, originText string, config *SummarizeByEditSpace) (optimized map[string]string, attempts int) {
	const (
		maxRetry  = 5
		delay     = time.Second
		tolerance = 0.25
	)

	softTargetRatio := config.ReductionRatio + tolerance
	if softTargetRatio > 1 {
		softTargetRatio = 1
	}

	originWords, _ := utils.CountWords(originText)
	hardTargetWords := int(float64(originWords) * config.ReductionRatio)
	softTargetWords := int(float64(originWords) * softTargetRatio)
	if softTargetWords < 10 {
		softTargetWords = 10
	}

	log.Println("target: ", hardTargetWords, softTargetWords, originWords)

	prompt := fmt.Sprintf("Summarize the text using %d words", hardTargetWords)

	optimized = map[string]string{}

	// Note: We cannot guarantee openAI will give us response immediately.
	// Let's retry maximum 10 times.
	if err := retry(maxRetry, delay, func() error {
		attempts++

		o, err := Edit(ctx, &EditInput{
			Text:         originText,
			Prompt:       prompt,
			Creativity:   config.Creativity,
			Alternatives: config.Alternatives,
		})
		if err != nil {
			return err
		}

		// Search those that meets the target.
		for _, result := range o.Choices {
			nwords, err := utils.CountWords(result)
			if err != nil {
				continue
			}
			if nwords < originWords {
				id := uuid.Must(uuid.NewUUID()).String()
				result = strings.TrimPrefix(result, ":")
				result = strings.TrimPrefix(result, " ")
				result = strings.TrimPrefix(result, "\n")
				optimized[id] = result
			}

			// If we are able to produce enough alternatives, we return
			// nil error and stop.
			if len(optimized) == config.Alternatives {
				return nil
			}
		}

		return errors.New("failed to find all results")
	}); err != nil {
		log.Println(err)
	}

	log.Println(len(optimized), config.Alternatives)

	// If we tried out best and could not find enough summarized text,
	// we just produce enough text to fill the gap.
	for i := len(optimized); i < config.Alternatives; i++ {
		id := uuid.Must(uuid.NewUUID()).String()
		optimized[id] = "I don't know how to summarize the text."
	}

	return optimized, attempts
}

func retry(attempts int, sleepDuration time.Duration, f func() error) (err error) {
	for i := 0; i < attempts; i++ {
		if i > 0 {
			log.Println("retrying after error:", err)
			time.Sleep(sleepDuration)
		}
		err = f()
		if err == nil {
			return nil
		}
	}
	return fmt.Errorf("after %d attempts, last error: %s", attempts, err)
}
