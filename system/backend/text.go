package main

import (
	"encoding/json"
	"fmt"
	"image/jpeg"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strings"
	"sync"

	"changkun.de/x/human-preference-prior/domain/bart"
	"changkun.de/x/human-preference-prior/domain/enhance"
	"changkun.de/x/human-preference-prior/domain/gpt3"
	"changkun.de/x/human-preference-prior/domain/mesh"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

func getUnfinishedTaskID(userFolder string) string {
	tasks := []string{"1", "2", "3"} // FIXME: load this from somewhere

	finishedTasks := []string{}
	files, err := os.ReadDir(userFolder)
	check(err)
	for _, file := range files {
		if strings.HasSuffix(file.Name(), "-finish.json") {
			finishedTaskID := strings.TrimSuffix(file.Name(), "-finish.json")
			finishedTasks = append(finishedTasks, finishedTaskID)
		}
	}
	unfinishedTasks := []string{}
	for _, task := range tasks {
		found := false
		for _, finished := range finishedTasks {
			if strings.Compare(task, finished) == 0 {
				found = true
				break
			}
		}
		if !found {
			unfinishedTasks = append(unfinishedTasks, task)
		}
	}
	// If there is no unfinished task, don't return any id.
	if len(unfinishedTasks) == 0 {
		return ""
	}
	// we randomly send unfinished task to participant.
	return unfinishedTasks[rand.Intn(len(unfinishedTasks))]
}

func optmizationBegin(taskContext taskContext, method userInterface) func(ctx *gin.Context) {
	return func(ctx *gin.Context) {
		// 1. parse input
		var input beginInput
		if err := ctx.BindJSON(&input); err != nil {
			ctx.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("cannot parse input: %v", err)})
			return
		}
		log.Printf("session begin: %+#v", input)
		if input.UserID == "" {
			ctx.JSON(http.StatusBadRequest, gin.H{"error": "missing Prolific ID"})
			return
		}

		// 2. create participant folder
		userFolder := fetchUserFolder(taskContext, method, input.UserID, input.SessionID)
		if err := mkdir(userFolder); err != nil {
			log.Printf("failed to create option folder: %v", err)
		}
		optionFolder := fetchFolder(taskContext, method, input.UserID, input.SessionID, "options")
		if err := mkdir(optionFolder); err != nil {
			log.Printf("failed to create option folder: %v", err)
		}
		parameterFolder := fetchFolder(taskContext, method, input.UserID, input.SessionID, "parameters")
		if err := mkdir(parameterFolder); err != nil {
			log.Printf("failed to create parameters folder: %v", err)
		}
		feedbackFolder := fetchFolder(taskContext, method, input.UserID, input.SessionID, "feedbacks")
		if err := mkdir(feedbackFolder); err != nil {
			log.Printf("failed to create feedback folder: %v", err)
		}

		// Figure out which task this participant should do.
		taskID := getUnfinishedTaskID(userFolder)
		begin := fetchBeginPath(taskContext, method, input.UserID, input.SessionID, taskID)

		// 3. store questionnaire data
		check(saveJSON(input.Data, begin))
		ctx.JSON(http.StatusOK, beginOutput{
			TaskID: taskID,
		})
	}
}

type Summarizer string

const (
	GPT3 Summarizer = "gpt3"
	Bart Summarizer = "bart"
)

func defineSolutionSpaceText(summarizer Summarizer, method userInterface) (int, map[string]any) {
	configs := map[string]any{}
	nParams := 4
	switch method {
	case interfacePointwise:
		configID := uuid.Must(uuid.NewUUID()).String()
		switch summarizer {
		case GPT3:
			configs[configID] = &gpt3.SummarizeByTldrCompletionSpace{}
		case Bart:
			configs[configID] = &bart.SummarizeSpace{}
		}
	case interfacePairwise:
		for i := 0; i < 2; i++ {
			configID := uuid.Must(uuid.NewUUID()).String()
			switch summarizer {
			case GPT3:
				configs[configID] = &gpt3.SummarizeByTldrCompletionSpace{}
			case Bart:
				configs[configID] = &bart.SummarizeSpace{}
			}
		}
	case interfaceListwiseRating, interfaceListwiseNoTie, interfaceListwiseCantie, interfaceListwiseRanking:
		for i := 0; i < 4; i++ {
			configID := uuid.Must(uuid.NewUUID()).String()
			switch summarizer {
			case GPT3:
				configs[configID] = &gpt3.SummarizeByTldrCompletionSpace{}
			case Bart:
				configs[configID] = &bart.SummarizeSpace{}
			}
		}
	default:
		panic("unsupported interface!")
	}
	return nParams, configs
}

func defineSolutionSpaceImage(method userInterface) (int, map[string]any) {
	configs := map[string]any{}
	nParams := 5
	switch method {
	case interfacePointwise:
		configID := uuid.Must(uuid.NewUUID()).String()
		configs[configID] = &enhance.Params{}
	case interfacePairwise:
		for i := 0; i < 2; i++ {
			configID := uuid.Must(uuid.NewUUID()).String()
			configs[configID] = &enhance.Params{}
		}
	case interfaceListwiseRating, interfaceListwiseNoTie, interfaceListwiseCantie, interfaceListwiseRanking:
		for i := 0; i < 4; i++ {
			configID := uuid.Must(uuid.NewUUID()).String()
			configs[configID] = &enhance.Params{}
		}
	default:
		panic("unsupported interface!")
	}
	return nParams, configs
}

func defineSolutionSpaceMesh(method userInterface) (int, map[string]any) {
	configs := map[string]any{}
	nParams := 5
	switch method {
	case interfaceListwiseRanking:
		for i := 0; i < 4; i++ {
			configID := uuid.Must(uuid.NewUUID()).String()
			configs[configID] = &mesh.SimplificationSpace{}
		}
	default:
		panic("unsupported interface!")
	}
	return nParams, configs
}

// optimizationBOiter implements the human's objective function.
//
// When a user is requesting the next iteration via POST, it will first check
// if there are any unevaluated instances. If so, then reutrn theose instance.
// If the user is evaluated the instances, the client should PUT these results
// though this interface and generate more instances to evaluate. A PUT request
// will only return if all intances are complete.
//
// If for some reason the evaluation instances are still evaluating, the request
// should wait and
func optimizationIterate(taskContext taskContext, method userInterface) func(ctx *gin.Context) {
	return func(ctx *gin.Context) {
		// 1. parse input, and store feedbacks if there is.
		var input iterateInput
		if err := ctx.BindJSON(&input); err != nil {
			ctx.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("cannot parse input: %v", err)})
			return
		}
		log.Printf("current input: %+#v", input)

		// There was no last feedback, we will need create an iter file.
		iterPath := fetchIterPath(taskContext, method, input.UserID, input.SessionID, input.TaskID)
		type iter struct {
			TaskID string   `json:"task_id"`
			Iters  []string `json:"iters"`
		}

		// Default configuration.
		var (
			nParams int
			configs map[string]any
		)

		switch taskContext {
		case ctxText:
			// FIXME: caution. GPT3 is acutally not supported yet in the BO optimizer.
			nParams, configs = defineSolutionSpaceText(Bart, method)
		case ctxImage:
			nParams, configs = defineSolutionSpaceImage(method)
		case ctxMesh:
			nParams, configs = defineSolutionSpaceMesh(method)
		}

		if input.LastFeedbackID != "" {
			// If feedback is not empty, then this is not the first iteration,
			// we should feedbacks first according to the attached feedback ID.
			check(saveJSON(input.Data, fetchPath(taskContext, method, input.UserID, input.SessionID, "feedbacks", input.LastFeedbackID)))
		} else {
			// Create iteration file to store all feedbackIDs.
			check(saveJSON(iter{TaskID: input.TaskID, Iters: []string{}}, iterPath))
			if input.Stop {
				ctx.JSON(http.StatusOK, nil)
				return
			}
		}

		// Determine parameters using bayesian optimization. The initial samples
		// will use Sobol samples, and subsequent samples will be estimated using
		// corresponding bayesian optimizations.
		params := bayesianOptimization(taskContext, method, nParams, &input)
		i := 0
		for id := range configs {
			switch taskContext {
			case ctxText:
				// FIXME: make it cam also work for GPT3, and other domains.
				configs[id] = &bart.SummarizeSpace{
					ReductionRatio: params[i][0],
					TopP:           params[i][1],
					Temperature:    params[i][2],
					LengthPenalty:  params[i][3],
				}
			case ctxImage:
				configs[id] = &enhance.Params{
					Brightness:  params[i][0],
					Contrast:    params[i][1],
					Saturation:  params[i][2],
					Temperature: params[i][3],
					Tint:        params[i][4],
					// Quality:     params[i][5], // not used.
				}
			case ctxMesh:
				configs[id] = &mesh.SimplificationSpace{
					ReductionRatio: params[i][0],
					KeepBorder:     params[i][1],
					KeepHardEdge:   params[i][2],
					KeepSharpness:  params[i][3],
					KeepQuad:       params[i][4],
				}
			}
			i++
		}

		// We have stored feedbacks for the last return, now generate a new feedback ID.
		feedbackID := uuid.Must(uuid.NewUUID()).String()
		// Store the feedbackID.
		b, err := os.ReadFile(iterPath)
		check(err)
		var iters iter
		check(json.Unmarshal(b, &iters))
		iters.Iters = append(iters.Iters, feedbackID)
		check(saveJSON(iters, iterPath))

		// 3. store all computed parameters
		configPath := fetchParameters(taskContext, method, input.UserID, input.SessionID, feedbackID)
		mkdir(configPath)
		for id := range configs {
			saveJSON(configs[id], configPath+"/"+id+".json")
		}

		// 4. read task from init folder
		taskPath, objectivePath := fetchTask(taskContext, method, input.TaskID)

		switch taskContext {
		case ctxText:
			origin, err := os.ReadFile(strings.Replace(taskPath, ".txt", ".json", -1))
			check(err)
			var taskInfo struct {
				News        string `json:"news"`
				GroundTruth string `json:"ground_truth"`
				Token       int    `json:"token"`
			}
			check(json.Unmarshal(origin, &taskInfo))
			// 5. generate more options according to the computed parameters
			mu := sync.Mutex{}
			optionPaths := []string{}
			groundTruths := []bool{}

			wg := sync.WaitGroup{}
			for id := range configs {
				wg.Add(1)
				go func(id string) {
					defer wg.Done()
					summarizer := Bart
					result := taskInfo.GroundTruth
					groundTruth := true
					switch summarizer {
					case GPT3:
						// FIXME: make it cam also work for GPT3, and other domains.
						result, err = gpt3.SummarizeByTldrCompletion(ctx.Request.Context(), taskInfo.News, taskInfo.Token, configs[id].(*gpt3.SummarizeByTldrCompletionSpace))
					case Bart:
						result, err = bart.Summarizer(ctx.Request.Context(), taskInfo.News, configs[id].(*bart.SummarizeSpace))
					}
					groundTruth = false
					if err != nil {
						// If the model failed, let's present the ground truth.
						result = taskInfo.GroundTruth
						groundTruth = true
					}
					result = strings.TrimSpace(result)

					optionPath := fetchOptions(taskContext, method, input.UserID, input.SessionID, feedbackID)
					mkdir(optionPath)

					optionFile := optionPath + "/" + id + ".txt"
					log.Printf("writing option: %s", optionFile)
					check(os.WriteFile(optionFile, []byte(result), os.ModePerm))

					mu.Lock()
					optionPaths = append(optionPaths, optionFile)
					groundTruths = append(groundTruths, groundTruth)
					mu.Unlock()
				}(id)
			}
			wg.Wait()
			ctx.JSON(http.StatusOK, optionOutput{
				TaskID:       input.TaskID,
				FeedbackID:   feedbackID,
				Origin:       taskPath,
				Objective:    objectivePath,
				Options:      optionPaths,
				GroundTruths: groundTruths,
			})

		case ctxImage:
			origin, err := os.Open(taskPath)
			check(err)
			defer origin.Close()
			img, err := jpeg.Decode(origin)
			check(err)

			// 5. generate more options according to the computed parameters
			mu := sync.Mutex{}
			optionPaths := []string{}

			wg := sync.WaitGroup{}
			for id := range configs {
				wg.Add(1)
				go func(id string) {
					defer wg.Done()
					result := enhance.Image(img, *configs[id].(*enhance.Params))

					optionPath := fetchOptions(taskContext, method, input.UserID, input.SessionID, feedbackID)
					mkdir(optionPath)

					optionFile := optionPath + "/" + id + ".jpg"
					log.Printf("writing option: %s", optionFile)

					f, err := os.Create(optionFile)
					check(err)
					err = jpeg.Encode(f, result, nil)
					check(err)

					mu.Lock()
					optionPaths = append(optionPaths, optionFile)
					mu.Unlock()
				}(id)
			}
			wg.Wait()
			ctx.JSON(http.StatusOK, optionOutput{
				TaskID:     input.TaskID,
				FeedbackID: feedbackID,
				Origin:     taskPath,
				Options:    optionPaths,
			})
		case ctxMesh:
			origin := taskPath

			// 5. generate more options according to the computed parameters
			mu := sync.Mutex{}
			optionPaths := []string{}

			wg := sync.WaitGroup{}
			for id := range configs {
				wg.Add(1)
				go func(id string) {
					defer wg.Done()

					optionPath := fetchOptions(taskContext, method, input.UserID, input.SessionID, feedbackID)
					mkdir(optionPath)

					optionFile := optionPath + "/" + id + ".obj"
					log.Printf("writing option: %s", optionFile)

					err = mesh.Simplify(origin, optionFile, *configs[id].(*mesh.SimplificationSpace))
					check(err)

					mu.Lock()
					optionPaths = append(optionPaths, optionFile)
					mu.Unlock()
				}(id)
			}
			wg.Wait()

			log.Println("all options are ready:", optionPaths)

			ctx.JSON(http.StatusOK, optionOutput{
				TaskID:     input.TaskID,
				FeedbackID: feedbackID,
				Origin:     taskPath,
				Options:    optionPaths,
			})
		}
	}
}

func optimizationFinish(taskContext taskContext, method userInterface) func(ctx *gin.Context) {
	return func(ctx *gin.Context) {
		// 1. parse input
		var input finishInput
		if err := ctx.BindJSON(&input); err != nil {
			ctx.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("cannot parse input: %v", err)})
			return
		}
		if input.UserID == "" || input.TaskID == "" {
			ctx.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("empty user (%s) or task ID (%s)", input.UserID, input.TaskID)})
			return
		}

		finish := fetchFinishPath(taskContext, method, input.UserID, input.SessionID, input.TaskID)

		// 2. store questionnaire data
		err := saveJSON(input.Data, finish)
		if err != nil {
			ctx.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("cannot save finish data: %v", err)})
			return
		}

		userFolder := fetchUserFolder(taskContext, method, input.UserID, input.SessionID)
		taskID := getUnfinishedTaskID(userFolder)
		redirect := terminateURL
		if taskID != "" {
			redirect = "" // if taskID is not empty, don't provide redirect URL.
		}

		// 3. send redirect link.
		ctx.JSON(http.StatusOK, finishOutput{
			TaskID:   taskID,
			Redirect: redirect,
		})
	}
}
