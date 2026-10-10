import './App.css';
import * as React from 'react';
import Box from '@mui/material/Box';
import Backdrop from '@mui/material/Backdrop';
import CircularProgress from '@mui/material/CircularProgress';

import { requestPairSamples } from './utils/submit';

import { TaskDescription } from './TaskDescription';
import { BeginDialog } from './components/BeginDialog';
import { ConfirmDialog } from './components/ConfirmDialog'
import { FinishDialog } from './components/FinishDialog';

import { maxIteration } from './utils/iterations'
import { EvaluateContent } from './Evaluation';

function App() {
  // Receive prolific information from query parameter.
  // ?user_id=changkun&study_id=prefprior-text-pointwise-0&session_id=wefoiwejfoij
  const urlSearchParams = new URLSearchParams(window.location.search);
  const params = Object.fromEntries(urlSearchParams.entries());
  const userID = params['user_id']
  const studyID = params['study_id']
  const sessionID = params['session_id']

  // FIXME: store the information to storage and resume the task if broken.

  // session management
  const sessionInfo = React.useRef({
    userID: userID,
    studyID: studyID,
    sessionID: sessionID
  })
  const [taskID, setTaskID] = React.useState()
  const [feedbackID, setFeedbackID] = React.useState()
  const [task, setTask] = React.useState(null)
  const [waiting, setWaiting] = React.useState(false)
  const [satisfy, setSatisfy] = React.useState(false)
  const [terminate, setTerminate] = React.useState(false)

  // iteration management
  const defaultEvalValue = {
    iteration: 0,
    completeIteration: 0,
    incompleteIteration: 0,
    rating: 0,
    skip: false,
    comment: '',
    timePresent: 0,
    timeLastRating: 0,
  }
  const [evaluate, setEval] = React.useState(defaultEvalValue);

  const presentNextTask = (data) => {
    const wait = t => new Promise(s => setTimeout(s, t));
    console.log('current feedbackid: ', feedbackID)
    const showTask = async () => {
      const info = await requestPairSamples({
        userID: sessionInfo.current.userID,
        studyID: sessionInfo.current.studyID,
        sessionID: sessionInfo.current.sessionID,
        taskID: data.taskID,
        currentIteration: data.iteration,
        feedbackID: data.feedbackID,
      }, data)

      if (data.stop) {
        console.log('terminated')
        return
      }

      console.log("task info: ", info)

      // randomly wait for 1 second to slow human behavior
      await wait(Math.floor(Math.random() * 1000))

      setFeedbackID(info.feedbackID)
      setTask(info)
      setEval(form => ({...form, timePresent: Date.now()}))
      setWaiting(false)
    }
    showTask()
  }

  const submitEvaluations = (stop) => {
    setWaiting(true)

    setEval(e => {
      const newIteration = e.iteration + 1
      let newCompleteIteration = e.completeIteration
      let newIncompleteIteration = e.incompleteIteration
      if (e.skip) {
        newIncompleteIteration += 1
      } else {
        newCompleteIteration += 1
      }
      let selection = ''
      if (e.rating === 0) {
        // nothing
      } else if (e.rating > 0 && e.rating <= 2) {
        selection = task.options[e.rating-1]
      } else if (e.rating > 2) {
        selection = 'same'
      }

      const data = {
        userID: sessionInfo.current.userID,
        studyID: sessionInfo.current.studyID,
        sessionID: sessionInfo.current.sessionID,
        taskID: taskID,
        stop: stop,
        iteration: newIteration,
        completeIteration: newCompleteIteration,
        incompleteIteration: newIncompleteIteration,
        rating: e.rating,
        selection: selection,
        skip: e.skip,
        comment: e.comment,
        timePresent: e.timePresent,
        // if participant did not touch the slider, then timeLastRating is 0.
        timeLastRating: e.timeLastRating,
        timeSubmit: Date.now()
      }

      if (newIteration < maxIteration && !stop) {
        presentNextTask({...data, groundTruth: task.groundTruths, feedbackID: feedbackID})

        return {...e,
          iteration: newIteration,
          completeIteration: newCompleteIteration,
          incompleteIteration: newIncompleteIteration,
          rating: 0,
          skip: false,
          timePresent: Date.now(),
          timeLastRating: 0,
          comment: '',
        }
      } else if (stop) {
        presentNextTask({...data, groundTruth: task.groundTruths, feedbackID: feedbackID, stop: true})
      } else if (newIteration >= maxIteration) {
        console.log('stopp as I am done')
        presentNextTask({...data, groundTruth: task.groundTruths, feedbackID: feedbackID, stop: true})
      }

      // There is no more new iterations, let's stop.
      setTerminate(true)
      return defaultEvalValue
    })
  }

  return (
    <div className="App">
      <div className="App-Header">
        {/* Human-in-the-Loop Optimizations: Text Summarization (Pairwise) */}
        <strong>Help AI to Summarize News Articles</strong>
      </div>
      <Box>
        <Box className="Content-Container">
          {task && <TaskDescription task={task}/>}
          {task && <EvaluateContent
            task={task}
            evaluate={evaluate}
            setEval={setEval}
            satisfy={(v) => setSatisfy(v)}
            submitForm={() => submitEvaluations(false)}
          />}
        </Box>
        <BeginDialog sessionInfo={sessionInfo.current}
          sessionBegin={(data) => {
            setWaiting(true)
            // store the task ID for requesting the next task.
            setTaskID(data.taskID)
            presentNextTask({...data, feedbackID: null})
          }}/>
        <FinishDialog
          taskID={taskID}
          sessionInfo={sessionInfo.current}
          open={terminate}
          nextTask={(nextTaskID) => {
            setWaiting(true)
            setTaskID(nextTaskID)
            presentNextTask({taskID: nextTaskID, feedbackID: null})
            setTerminate(false)
          }}
        />
        <ConfirmDialog
          open={satisfy}
          cancel={() => setSatisfy(false)}
          confirm={() => {
            submitEvaluations(true)
            setEval(defaultEvalValue)
            setSatisfy(false)
            setTerminate(true)
          }}
        />
        <Backdrop
          sx={{ backdropFilter: "blur(5px)", color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }}
          open={waiting}
        >
          <CircularProgress color="inherit" />
        </Backdrop>
      </Box>
    </div>
  );
}


export default App;
