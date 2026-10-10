import './Dialog.css';
import * as React from 'react';
import Box from '@mui/material/Box';
import Slider from '@mui/material/Slider';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import { styled } from '@mui/material/styles';
import { submitFinishForm } from '../utils/submit';

export const TinyText = styled(Typography)({
  fontSize: '0.75rem',
  opacity: 0.38,
  fontWeight: 500,
  letterSpacing: 0.2,
});

export function FinishDialog(props) {
  const defaultForm = {
    userID: props.sessionInfo.userID,
    studyID: props.sessionInfo.studyID,
    sessionID: props.sessionInfo.sessionID,
    taskID: props.taskID,

    // collect final questionnaire data.
    expectation: 50,
    satisfaction: 50,
    confidence: 50,
    regret: 50,
    improvement: 50,
    incompletePreference: 50,
    feedback: '',

    // collect choice time
    finishTimestamp: 0,
    expectationTimestamp: 0,
    satisfactionTimestamp: 0,
    confidenceTimestamp: 0,
    regretTimestamp: 0,
    improvementTimestamp: 0,
    incompletePreferenceTimestamp: 0,
  }
  const [finishForm, setFinishForm] = React.useState(defaultForm)
  const numTask = React.useRef(0)

  const handleFinish = () => {
    (async () => {
      const form = {...finishForm, taskID: props.taskID, finishTimestamp: Date.now()}
      const resp = await submitFinishForm(form)
      if (!resp.ok) {
        // TODO: still do something here.
        console.log('session cannot be finished')
        return
      }
      console.log(resp)
      const nextTaskID = resp.data.task_id
      if (nextTaskID !== '') {
        setFinishForm(defaultForm)
        props.nextTask(nextTaskID)
        return
      }

      const redirect = resp.data.redirect
      console.log('redirect to: ', redirect)

      window.location.href = redirect
    })()
  }

  const updateExpectation = (e) => {
    setFinishForm(prevForm => ({
      ...prevForm, expectation: e, expectationTimestamp: Date.now()}))
  }
  const updateSatisfaction = (e) => {
    setFinishForm(prevForm => ({
      ...prevForm, satisfaction: e, satisfactionTimestamp: Date.now()}))
  }
  const updateConfidence = (e) => {
    setFinishForm(prevForm => ({
      ...prevForm, confidence: e, confidenceTimestamp: Date.now()}))
  }
  const updateRegret = (e) => {
    setFinishForm(prevForm => ({
      ...prevForm, regret: e, regretTimestamp: Date.now()}))
  }
  const updateImprovement = (e) => {
    setFinishForm(prevForm => ({
      ...prevForm, improvement: e, improvementTimestamp: Date.now()}))
  }

  const updateIncompletePreference = (e) => {
    setFinishForm(prevForm => ({
      ...prevForm, incompletePreference: e, incompletePreferenceTimestamp: Date.now()}))
  }

  return (
    <Dialog open={props.open} sx={{backdropFilter: "blur(5px)"}} fullWidth maxWidth="md">
      <DialogTitle sx={{display: 'flex', alignItems: 'center', marginRight: '5px'}}>
          <strong>Final Questions</strong>
      </DialogTitle>
      <DialogContent>
        <Box className="Questionnaire">
          <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
            {/* Does the final indicated result match your expectation? */}
            <strong>I strongly agree the final result matches my <em>expectation</em> of color enhanced photo(s).</strong>
          </Typography>
          <Slider
            track={false}
            value={finishForm.expectation}
            onChange={(e) => updateExpectation(e.target.value)}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <TinyText>Strongly disagree</TinyText>
            <TinyText>Strongly agree</TinyText>
          </Box>
          <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
            {/* How much are you satisfied with the final indicated result? */}
            <strong>I am strongly <em>satisfied</em> with the final indicated photo(s).</strong>
          </Typography>
          <Slider
            track={false}
            value={finishForm.satisfaction}
            onChange={(e) => updateSatisfaction(e.target.value)}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <TinyText>Strongly dissatisfied</TinyText>
            <TinyText>Strongly satisfied</TinyText>
          </Box>
          <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
            {/* Do you think that you can do the summarization better than AI? */}
            <strong>I firmly believe I can do a better color enhancement <em>manually</em> using a software than this AI for this photo.</strong>
          </Typography>
          <Slider
            track={false}
            value={finishForm.confidence}
            onChange={(e) => updateConfidence(e.target.value)}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <TinyText>Strongly disbelieve</TinyText>
            <TinyText>Strongly believe</TinyText>
          </Box>
          <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
            {/* How much do you regret any of your indicated ratings? */}
            <strong>I believe I had given <em>clear rating feedback</em> to the AI.</strong>
          </Typography>
          <Slider
            track={false}
            value={finishForm.regret}
            onChange={(e) => updateRegret(e.target.value)}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <TinyText>Strongly disagree</TinyText>
            <TinyText>Strongly agree</TinyText>
          </Box>
          <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
            <strong>I strongly believe the AI <em>indeed improved</em> itself on color enhancement based on my feedback.</strong>
          </Typography>
          <Slider
            track={false}
            value={finishForm.improvement}
            onChange={(e) => updateImprovement(e.target.value)}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <TinyText>Strongly disagree</TinyText>
            <TinyText>Strongly agree</TinyText>
          </Box>
          <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
            <strong>I think the "I don't know" option helped me to express my feedback to the AI more precisely.</strong>
          </Typography>
          <Slider
            track={false}
            value={finishForm.incompletePreference}
            onChange={(e) => updateIncompletePreference(e.target.value)}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <TinyText>Strongly disagree</TinyText>
            <TinyText>Strongly agree</TinyText>
          </Box>
          <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
            <strong>Describe your experience while working with this AI.</strong>
          </Typography>
          <TextField
            multiline
            rows={2}
            variant="outlined"
            value={finishForm.feedback}
            onChange={(e) => setFinishForm({...finishForm, feedback: e.target.value})}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button  variant="contained" onClick={() => {
          numTask.current += 1
          handleFinish()
        }} style={{ fontWeight: "bold" }}>{numTask.current < 2 ? 'Submit' : 'Finish'}</Button>
      </DialogActions>
    </Dialog>
  )
}