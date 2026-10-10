package main

const terminateURL = "https://app.prolific.co/submissions/complete?cc=C1C4106X"

type beginInput struct {
	UserID    string `json:"user_id"`
	StudyID   string `json:"study_id"`
	SessionID string `json:"session_id"`
	Data      any    `json:"data"`
}

type beginOutput struct {
	TaskID string `json:"task_id"`
}

type finishInput struct {
	UserID    string `json:"user_id"`
	StudyID   string `json:"study_id"`
	SessionID string `json:"session_id"`
	TaskID    string `json:"task_id"`
	Data      any    `json:"data"`
}

type finishOutput struct {
	// When a task is finished. The finish request is responsible
	// to tell the client if there is a new task or not.
	// If the response has no given task ID, then the finish task
	// can redirect to the final finish page. Otherwise, the client
	// should redirect to the finish page, according to the given
	// redirect URL.
	TaskID   string `json:"task_id"`
	Redirect string `json:"redirect"`
}

type iterateInput struct {
	UserID    string `json:"user_id"`
	StudyID   string `json:"study_id"`
	SessionID string `json:"session_id"`
	// Request an iteration should explicitly tell the server
	// which task is requesting. This ID is usually assigned
	// after receiving the response of begin request, or a
	// finish request.
	TaskID           string `json:"task_id"`
	Stop             bool   `json:"stop"`
	CurrentIteration int    `json:"current_iteration"`
	LastFeedbackID   string `json:"last_feedback_id"`
	Data             any    `json:"data"`
}

// optionOutput is a stateless abstraction to a decision-making task.
// the struct contains:
//
// 1) original option;
// 2) optimization objectives;
// 3) choice options.
//
// The backend can always control what kind of task for users to evaluate.
// Except TaskID, the Origin, Objective, and Options field contains
// an server address for user to fetch the actual instance.
//
// For example, the response data would be:
//
//	{
//		"task_id": "aop83209f2jqfij1",
//		"origin": "https://research.changkun.de/data/{task_context}/tasks/{task_id}.txt",
//		"objective": "https://research.changkun.de/data/{task_context}/tasks/objective.txt",
//		"options": [
//			"https://research.changkun.de/data/{task_context}/{user_id}/options/{option_id}.txt",
//		]
//	}
//
//	{
//		"task_id": "aop83209f2jqfij1",
//		"origin": "https://research.changkun.de/data/{task_context}/tasks/{task_id}.png",
//		"objective": "https://research.changkun.de/data/{task_context}/tasks/objective.png",
//		"options": [
//			"https://research.changkun.de/data/{task_context}/{user_id}/options/{option_id}.png",
//		]
//	}
//
//	{
//		"task_id": "aop83209f2jqfij1",
//		"origin": "https://research.changkun.de/data/{task_context}/tasks/{task_id}.obj",
//		"objective": "https://research.changkun.de/data/{task_context}/tasks/objective.obj",
//		"options": [
//			"https://research.changkun.de/data/{task_context}/{user_id}/options/{option_id}.obj",
//		]
//	}
type optionOutput struct {
	TaskID       string   `json:"task_id"`
	FeedbackID   string   `json:"feedback_id"`
	Origin       string   `json:"origin"`
	Objective    string   `json:"objective"`
	Options      []string `json:"options"`
	GroundTruths []bool   `json:"ground_truths"`
}
