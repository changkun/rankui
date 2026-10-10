package main

import (
	"context"
	"fmt"
	"math/rand"
	"testing"
	"time"
)

type pairwiseFeedback struct {
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

// TestRandomPairwise simulates a random person who generates random rating.
func TestRandomPairwise(t *testing.T) {
	userID := "random"
	studyID := "pointwise"
	for i := 1; i <= 30; i++ {
		pairwise(userID, studyID, fmt.Sprintf("%d", i))
	}
}

func pairwise(userID, studyID, sessionID string) {
	ctx := context.Background()
	tID, err := begin(ctx, userID, studyID, sessionID, "/prefprior/text/pairwise/begin")
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
			Data: pairwiseFeedback{
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
			in.Data = pairwiseFeedback{
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
