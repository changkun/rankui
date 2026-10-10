package main

import "fmt"

type taskContext string

const (
	ctxText  taskContext = "text"
	ctxImage taskContext = "image"
	ctxMesh  taskContext = "mesh"
)

type userInterface string

const (
	interfacePointwise       userInterface = "pointwise"
	interfacePairwise        userInterface = "pairwise"
	interfaceListwiseRating  userInterface = "listwise-rating"
	interfaceListwiseNoTie   userInterface = "listwise-notie"
	interfaceListwiseCantie  userInterface = "listwise-cantie"
	interfaceListwiseRanking userInterface = "listwise-ranking"
)

// fetchTask returns the file paths to task instance and objective descriptions
// according to the given context, and task ID.
func fetchTask(context taskContext, method userInterface, taskID string) (task, objective string) {
	switch context {
	case ctxText:
		task = fmt.Sprintf("data/%s-%s/tasks/%s.txt", context, method, taskID)
		objective = fmt.Sprintf("data/%s-%s/tasks/objective.txt", context, method)
		return
	case ctxImage:
		task = fmt.Sprintf("data/%s-%s/tasks/%s.jpg", context, method, taskID)
		objective = fmt.Sprintf("data/%s-%s/tasks/objective.txt", context, method)
		return
	case ctxMesh:
		task = fmt.Sprintf("data/%s-%s/tasks/%s.obj", context, method, taskID)
		objective = fmt.Sprintf("data/%s-%s/tasks/objective.txt", context, method)
		return
	}
	panic("unsupported")
}

// fetchOptions returns the file path to the task instance according
// to the given context, user ID, and option ID.
func fetchOptions(context taskContext, method userInterface, userID, sessionID, feedbackID string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s/options/%s", context, method, userID, sessionID, feedbackID)
	}
	panic("unsupported")
}

// fetchParameters returns the file path to parameters according.
func fetchParameters(context taskContext, method userInterface, userID, sessionID, feedbackID string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s/parameters/%s", context, method, userID, sessionID, feedbackID)
	}
	panic("unsupported")
}

// fetchUserFolder returns the corresponding user folder
// regarding a given context and user ID.
func fetchUserFolder(context taskContext, method userInterface, userID, sessionID string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s", context, method, userID, sessionID)
	}
	panic("unsupported")
}

// fetchFolder returns the corresponding choice
// alternatives folder regarding a given context and userID.
func fetchFolder(context taskContext, method userInterface, userID, sessionID, folderName string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s/%s", context, method, userID, sessionID, folderName)
	}
	panic("unsupported")
}

// fetchPath returns the corresponding human feedback folder.
func fetchPath(context taskContext, method userInterface, userID, sessionID, folderName, feedbackID string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s/%s/%s.json", context, method, userID, sessionID, folderName, feedbackID)
	}
	panic("unsupported")
}

// fetchBeginPath returns the stroing file path for the begin
// questoinnaire.
func fetchBeginPath(context taskContext, method userInterface, userID, sessionID, taskID string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s/%s-begin.json", context, method, userID, sessionID, taskID)
	}
	panic("unsupported")
}

// fetchIterPath returns the stroing file path for the begin
// questoinnaire.
func fetchIterPath(context taskContext, method userInterface, userID, sessionID, taskID string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s/%s-iter.json", context, method, userID, sessionID, taskID)
	}
	panic("unsupported")
}

// fetchFinishPath returns the stroing file path for the finishing
// questoinnaire.
func fetchFinishPath(context taskContext, method userInterface, userID, sessionID, taskID string) string {
	switch context {
	case ctxText, ctxImage, ctxMesh:
		return fmt.Sprintf("data/%s-%s/%s-%s/%s-finish.json", context, method, userID, sessionID, taskID)
	}
	panic("unsupported")
}
