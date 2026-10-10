package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"testing"
	"time"
)

const endpoint = "http://localhost:8088"

type pointwiseFeedback struct {
	UserID              string `json:"userID"`
	StudyID             string `json:"studyID"`
	SessionID           string `json:"sessionID"`
	TaskID              string `json:"taskID"`
	FeedbackID          string `json:"feedbackID"`
	Rating              int    `json:"rating"`
	GroundTruth         []bool `json:"groundTruth"`
	Skip                bool   `json:"skip"`
	Stop                bool   `json:"stop"`
	Iteration           int    `json:"iteration"`
	CompleteIteration   int    `json:"completeIteration"`
	IncompleteIteration int    `json:"incompleteIteration"`
	Comment             string `json:"comment"`
	TimePresent         int64  `json:"timePresent"`
	TimeLastRating      int64  `json:"timeLastRating"`
	TimeSubmit          int64  `json:"timeSubmit"`
}

func TestRandomPointwise(t *testing.T) {
	userID := "random"
	studyID := "pointwise"
	for i := 6; i <= 30; i++ {
		pointwise(userID, studyID, fmt.Sprintf("%d", i))
	}
}

func pointwise(userID, studyID, sessionID string) {
	ctx := context.Background()
	tID, err := begin(ctx, userID, studyID, sessionID, "/prefprior/text/pointwise/begin")
	if err != nil {
		panic(err)
	}

	for t := 0; t < 3; t++ {
		in := &iterateInput{
			UserID:           userID,
			StudyID:          studyID,
			SessionID:        sessionID,
			TaskID:           tID,
			Stop:             false,
			CurrentIteration: 1,
			LastFeedbackID:   "",
			Data: pointwiseFeedback{
				UserID:              userID,
				StudyID:             studyID,
				SessionID:           sessionID,
				TaskID:              tID,
				FeedbackID:          "",
				Rating:              0,
				GroundTruth:         []bool{},
				Skip:                false,
				Stop:                false,
				Iteration:           1,
				CompleteIteration:   1,
				IncompleteIteration: 0,
				Comment:             "",
				TimePresent:         time.Now().Unix(),
				TimeLastRating:      time.Now().Unix(),
				TimeSubmit:          time.Now().Unix(),
			},
		}

		o, err := iterate(ctx, "/prefprior/text/pointwise/iterate", in)
		if err != nil {
			panic(err)
		}

		for i := 0; i < 20; i++ {
			in.LastFeedbackID = o.FeedbackID
			in.CurrentIteration += 1
			in.Data = pointwiseFeedback{
				UserID:              userID,
				StudyID:             studyID,
				SessionID:           sessionID,
				TaskID:              tID,
				FeedbackID:          in.LastFeedbackID,
				Rating:              rand.Intn(101),
				GroundTruth:         []bool{false},
				Skip:                false,
				Stop:                false,
				Iteration:           in.CurrentIteration,
				CompleteIteration:   in.CurrentIteration,
				IncompleteIteration: 0,
				Comment:             "",
				TimePresent:         time.Now().Unix(),
				TimeLastRating:      time.Now().Unix(),
				TimeSubmit:          time.Now().Unix(),
			}
			o, err = iterate(ctx, "/prefprior/text/pointwise/iterate", in)
			if err != nil {
				panic(err)
			}
		}
		tID, err = finish(ctx, userID, studyID, sessionID, tID, "/prefprior/text/pointwise/finish")
		if err != nil {
			panic(err)
		}
	}
	if tID != "" {
		panic("task did not finish")
	}
}

func begin(ctx context.Context, userID, studyID, sessionID, path string) (string, error) {
	d := beginInput{UserID: userID, StudyID: studyID, SessionID: sessionID}
	b, _ := json.Marshal(d)
	r, err := http.NewRequest(
		http.MethodPost, endpoint+path, bytes.NewReader(b))
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
	o := beginOutput{}
	err = json.Unmarshal(data, &o)
	if err != nil {
		return "", fmt.Errorf("failed to parse edit response: %w", err)
	}

	return o.TaskID, nil
}

func finish(ctx context.Context, userID, studyID, sessionID, taskID, path string) (string, error) {
	d := finishInput{UserID: userID, StudyID: studyID, SessionID: sessionID, TaskID: taskID}
	b, _ := json.Marshal(d)
	r, err := http.NewRequest(
		http.MethodPost, endpoint+path, bytes.NewReader(b))
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
	o := finishOutput{}
	err = json.Unmarshal(data, &o)
	if err != nil {
		return "", fmt.Errorf("failed to parse edit response: %w", err)
	}

	return o.TaskID, nil
}

func iterate(ctx context.Context, path string, input *iterateInput) (*optionOutput, error) {
	b, _ := json.Marshal(input)
	r, err := http.NewRequest(
		http.MethodPost, endpoint+path, bytes.NewReader(b))
	if err != nil {
		return nil, fmt.Errorf("failed to create the request: %w", err)
	}
	r.Header.Set("Content-Type", "application/json; charset=UTF-8")
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
	o := &optionOutput{}
	err = json.Unmarshal(data, o)
	if err != nil {
		return nil, fmt.Errorf("failed to parse edit response: %w", err)
	}
	return o, nil
}
