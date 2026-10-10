package main

import (
	"context"
	"fmt"
	"math/rand"
	"testing"
	"time"
)

type listwiseRatingFeedback struct {
	UserID              string  `json:"userID"`
	StudyID             string  `json:"studyID"`
	SessionID           string  `json:"sessionID"`
	TaskID              string  `json:"taskID"`
	FeedbackID          string  `json:"feedbackID"`
	Rating              []int   `json:"rating"`
	GroundTruth         []bool  `json:"groundTruth"`
	Skip                []bool  `json:"skip"`
	Stop                bool    `json:"stop"`
	Iteration           int     `json:"iteration"`
	CompleteIteration   int     `json:"completeIteration"`
	IncompleteIteration int     `json:"incompleteIteration"`
	Comment             string  `json:"comment"`
	TimePresent         int64   `json:"timePresent"`
	TimeLastRating      []int64 `json:"timeLastRating"`
	TimeSubmit          int64   `json:"timeSubmit"`
}

func TestRandomListwiseRating(t *testing.T) {
	userID := "random"
	studyID := "pointwise"
	for i := 22; i <= 30; i++ {
		listwiseRating(userID, studyID, fmt.Sprintf("%d", i))
	}
}

func listwiseRating(userID, studyID, sessionID string) {
	ctx := context.Background()
	tID, err := begin(ctx, userID, studyID, sessionID, "/prefprior/text/listwise/rating/begin")
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
			Data: listwiseRatingFeedback{
				UserID:              userID,
				StudyID:             studyID,
				SessionID:           sessionID,
				TaskID:              tID,
				FeedbackID:          "",
				Rating:              []int{rand.Intn(101), rand.Intn(101), rand.Intn(101), rand.Intn(101)},
				GroundTruth:         []bool{false, false, false, false},
				Skip:                []bool{false, false, false, false},
				Stop:                false,
				Iteration:           1,
				CompleteIteration:   1,
				IncompleteIteration: 0,
				Comment:             "",
				TimePresent:         time.Now().Unix(),
				TimeLastRating:      []int64{time.Now().Unix(), time.Now().Unix(), time.Now().Unix(), time.Now().Unix()},
				TimeSubmit:          time.Now().Unix(),
			},
		}

		o, err := iterate(ctx, "/prefprior/text/listwise/rating/iterate", in)
		if err != nil {
			panic(err)
		}

		for i := 0; i < 20; i++ {
			in.LastFeedbackID = o.FeedbackID
			in.CurrentIteration += 1
			in.Data = listwiseRatingFeedback{
				UserID:              userID,
				StudyID:             studyID,
				SessionID:           sessionID,
				TaskID:              tID,
				FeedbackID:          in.LastFeedbackID,
				Rating:              []int{rand.Intn(101), rand.Intn(101), rand.Intn(101), rand.Intn(101)},
				GroundTruth:         []bool{false, false, false, false},
				Skip:                []bool{false, false, false, false},
				Stop:                false,
				Iteration:           in.CurrentIteration,
				CompleteIteration:   in.CurrentIteration,
				IncompleteIteration: 0,
				Comment:             "",
				TimePresent:         time.Now().Unix(),
				TimeLastRating:      []int64{time.Now().Unix(), time.Now().Unix(), time.Now().Unix(), time.Now().Unix()},
				TimeSubmit:          time.Now().Unix(),
			}
			o, err = iterate(ctx, "/prefprior/text/listwise/rating/iterate", in)
			if err != nil {
				panic(err)
			}
		}
		tID, err = finish(ctx, userID, studyID, sessionID, tID, "/prefprior/text/listwise/rating/finish")
		if err != nil {
			panic(err)
		}
	}
	if tID != "" {
		panic("task did not finish")
	}
}
