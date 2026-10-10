import './Dialog.css';
import { useState } from 'react';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import FaceIcon from '@mui/icons-material/Face';
import Typography from '@mui/material/Typography';
import FormControl from '@mui/material/FormControl';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Alert from '@mui/material/Alert';
import { submitBeginForm } from "../utils/submit";

export function BeginDialog(props) {
  const defaultBeginFormValue = {
    userID: props.sessionInfo.userID,
    studyID: props.sessionInfo.studyID,
    sessionID: props.sessionInfo.sessionID,

    // collect user background.
    age: '',
    gender: -1,
    expertise: '',
    workExperience: '',
    lastExperience: '',

    // collect choice time.
    beginTimstamp: Date.now(),
    ageTimestamp: 0,
    genderTimestamp: 0,
    expertiseTimestamp: 0,
    workExperienceTimestamp: 0,
    lastExperienceTimestamp: 0,
  }
  const [beginForm, setBeginForm] = useState(defaultBeginFormValue)
  const [beginHint, setBeginHint] = useState({
    userID: false,
    age: false,
    gender: false,
    expertise: false,
    workExperience: false,
    lastExperience: false,
  })

  const [open, setOpen] = useState(true);
  const [error, setError] = useState(false);
  const handleUserID = (e) => {setBeginForm(prevForm => ({
    ...prevForm, userID: e.target.value, timestamp: Date.now()}))}
  const handleClose = () => {
    if (beginForm.userID === '' || beginForm.userID === undefined) {
      setBeginHint(prevHint => ({...prevHint, userID: true}))
      return
    } else {
      setBeginHint(prevHint => ({...prevHint, userID: false}))
    }

    if (beginForm.age === '' || beginForm.age === undefined) {
      setBeginHint(prevHint => ({...prevHint, age: true}))
      return
    } else {
      setBeginHint(prevHint => ({...prevHint, age: false}))
    }

    if (beginForm.gender === -1 || beginForm.gender === undefined) {
      setBeginHint(prevHint => ({...prevHint, gender: true}))
      return
    } else {
      setBeginHint(prevHint => ({...prevHint, gender: false}))
    }

    if (beginForm.expertise === '' || beginForm.expertise === undefined) {
      setBeginHint(prevHint => ({...prevHint, expertise: true}))
      return
    } else {
      setBeginHint(prevHint => ({...prevHint, expertise: false}))
    }

    if (beginForm.workExperience === '' || beginForm.workExperience === undefined) {
      setBeginHint(prevHint => ({...prevHint, workExperience: true}))
      return
    } else {
      setBeginHint(prevHint => ({...prevHint, workExperience: false}))
    }


    if (beginForm.lastExperience === '' || beginForm.lastExperience === undefined) {
      setBeginHint(prevHint => ({...prevHint, lastExperience: true}))
      return
    } else {
      setBeginHint(prevHint => ({...prevHint, lastExperience: false}))
    }

    // check if userID, sessionID, and studyID are valid.
    if (beginForm.userID === '' || beginForm.userID === undefined) {
      setError(true)
      return
    }
    if (beginForm.sessionID === '' || beginForm.sessionID === undefined) {
      setError(true)
      return
    }
    if (beginForm.studyID === '' || beginForm.studyID === undefined) {
      setError(true)
      return
    }

    (async () => {

      const resp = await submitBeginForm(beginForm)
      if (!resp.ok) {
        console.log('session cannot be started')
        setError(true)
        return
      }
      props.sessionBegin({taskID: resp.data.task_id})
      setOpen(false)
    })()
  };

  const months = []
  for (let i = 0; i <= 121; i++) {
    months.push(i)
  }

  return (
      <Dialog open={open} scroll={'paper'} sx={{backdropFilter: "blur(5px)"}} fullWidth maxWidth="md">
        <DialogTitle sx={{display: 'flex', alignItems: 'center', marginRight: '5px'}}>
          <FaceIcon fontSize="large" sx={{marginRight: '5px'}}/>
          <span>Help AI to Summarize News Articles</span>
        </DialogTitle>
        <DialogContent>
          <Typography><strong>Task Description</strong></Typography>
          <DialogContentText>
          In this study, imagine you, as a press editor, must produce a summary of 3 news articles. Instead of summarizing the text manually, an AI running in the background will help you to do the summarization automatically.
          <strong>Your main objective is to give feedback to the AI and let it summarize the article as much as possible while preserving its meaning.</strong><br/><br/>

          The user interfaces will show you some of the AI summarized text iteratively, including an original news article and an AI-summarized version of the given article. In each iteration, you will need to indicate your feedback to the AI using the provided interface, then the AI will try to improve itself progressively based on your feedback.<br/><br/>

          To indicate your feedback, you can:<br/>
          1) use the sliders to give your ratings, then click the "<strong>SUBMIT FEEDBACK</strong>" button; or<br/>
          2) click the "<strong>I DON'T KNOW</strong>" checkbox if you don't know how good the result was.<br/>
          3) When satisfied with the current result, use the "<strong>I'M SATISFIED</strong>" button to terminate the iteration. Otherwise, try to give more feedback to the AI until you are really satisfied, or terminate automatically if exceeded the maximum allowed attempts.<br/><br/>

          You will be redirected to a finish page that contains a <strong>completion code</strong> when all tasks are finished. If you give a considerable amount of feedback and also explain your ratings clearly, we will consider give <strong>bonus</strong> payments to the top 5% participants.<br/><br/>
          </DialogContentText>

          <Typography><strong>Basic Information</strong></Typography>
          <TextField
            required
            label="Prolific ID"
            type="text"
            fullWidth
            variant="standard"
            error={beginHint.userID}
            onChange={handleUserID}
            defaultValue={beginForm.userID}
          />
          <FormControl fullWidth variant="standard">
            <Typography className="QuestionnaireQuestion"><strong>How old are you?</strong></Typography>
            <TextField
              required
              label="Age"
              type="text"
              fullWidth
              variant="standard"
              error={beginHint.age}
              defaultValue={beginForm.age}
              onChange={(e) => setBeginForm(prevForm => ({...prevForm, age: e.target.value, ageTimestamp: Date.now()}))}
            />
          </FormControl>
          <FormControl fullWidth variant="standard">
            <Typography className="QuestionnaireQuestion"><strong>What is your gender?</strong></Typography>
            <Select
              required
              error={beginHint.gender}
              value={beginForm.gender}
              onChange={(e) => setBeginForm(prevForm => ({...prevForm, gender: e.target.value, genderTimestamp: Date.now()}))}
            >
              <MenuItem value={0}>Female</MenuItem>
              <MenuItem value={1}>Male</MenuItem>
              <MenuItem value={2}>Diverse</MenuItem>
              <MenuItem value={3}>Prefer not to say</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth variant="standard">
            <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
              <strong>
                Please self rate English proficiency (under
                the <a target="_blank" rel="noreferrer" href="https://www.coe.int/en/web/common-european-framework-reference-languages/table-1-cefr-3.3-common-reference-levels-global-scale">CEFR 3.3</a> framework)
              </strong>
            </Typography>
            <Select
              required
              error={beginHint.expertise}
              value={beginForm.expertise}
              onChange={(e) => setBeginForm(prevForm => ({...prevForm, expertise: e.target.value, expertiseTimestamp: Date.now()}))}
            >
              <MenuItem value={0}>Basic (A1 - Breakthrough or beginner)</MenuItem>
              <MenuItem value={1}>Basic (A2 - Waystage or elementary)</MenuItem>
              <MenuItem value={2}>Independent (B1 - Waystage or elementary)</MenuItem>
              <MenuItem value={3}>Independent (B2 - Vantage or upper intermediate)</MenuItem>
              <MenuItem value={4}>Proficient (C1 - Effective operational proficiency or advanced)</MenuItem>
              <MenuItem value={5}>Proficient (C2 - Mastery or proficiency)</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth variant="standard">
            <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
              <strong>How many months of work experience do you have in English writing (e.g. as clerk, press editor, etc.)</strong>
            </Typography>
            <Select
              required
              error={beginHint.workExperience}
              value={beginForm.workExperience}
              onChange={(e) => setBeginForm(prevForm => ({...prevForm, workExperience: e.target.value, workExperienceTimestamp: Date.now()}))}
            >
              {months.map(m => {
                let label = 'None'
                let years = Math.floor(m / 12)
                let month = m % 12
                if (years === 0 && month === 0) {
                  label = 'None'
                } else if (years > 0 && years < 10) {
                  if (month < 1) {
                    label = `${years} year${years > 1 ? 's' : ''}`
                  } else {
                    label = `${years} year${years > 1 ? 's' : ''} ${month} month${month > 1 ? 's' : ''}`
                  }
                } else if (years < 1) {
                  label = `${month} month${month > 1 ? 's' : ''}`
                } else if (years === 10 && month === 0) {
                  label = '10 years'
                } else {
                  label = 'more than 10 years'
                }
                return <MenuItem key={m} value={m}>{label}</MenuItem>
              })}
              {/* What about native speakers? */}
              {/* "Years" or this */}
              {/* NOTE: design decision, we want users to indicate more information. */}
              {/* <MenuItem value={0}>None</MenuItem>
              <MenuItem value={1}>1-3 months</MenuItem>
              <MenuItem value={2}>4-12 months</MenuItem>
              <MenuItem value={3}>13-36 months</MenuItem>
              <MenuItem value={4}>more than 36 months</MenuItem> */}
            </Select>
          </FormControl>
          <FormControl fullWidth variant="standard">
            <Typography className="QuestionnaireQuestion" variant="body1" gutterBottom component="div">
              <strong>When was your last time of writing academic texts in English?</strong>
            </Typography>
            <Select
              required
              error={beginHint.lastExperience}
              value={beginForm.lastExperience}
              onChange={(e) => setBeginForm(prevForm => ({...prevForm, lastExperience: e.target.value, lastExperienceTimestamp: Date.now()}))}

            >
              <MenuItem value={0}>Never</MenuItem>
              <MenuItem value={1}>In recent 2 weeks</MenuItem>
              <MenuItem value={2}>2 weeks to 3 months ago</MenuItem>
              <MenuItem value={3}>3 to 6 months ago</MenuItem>
              <MenuItem value={4}>6 to 12 months ago</MenuItem>
              <MenuItem value={5}>13 to 36 months ago</MenuItem>
              <MenuItem value={6}>more than 36 months ago</MenuItem>
            </Select>
          </FormControl>
          {error && <Alert severity="error" sx={{marginTop: '20px'}}>We cannot start this session. Please join the study later.</Alert>}


          <Typography sx={{marginTop: '20px'}}><strong>Consent Form</strong></Typography>
          <Typography variant="overline"><strong>Information about study participation and data processing</strong></Typography>
          <DialogContentText>
          I am aware that the collection, processing, and use of my data takes place on a voluntary basis. The participation in the study can be cancelled by me at any time without stating reasons, without this resulting in any disadvantages for me. In the event of termination, all data recorded by me up to that point will be irrevocably deleted after the data collection phase.<br/><br/>
          I agree that my data including my demographics and my feedbacks to the AI may be collected, stored and processed in anonymized form. No personal data is processed.<br/><br/>
          I agree that my data will be collected, processed, used and stored by the University of Munich for the following purposes:<br/><br/>
          The results and original data of this study may be published as a scientific publication. This is done in a completely anonymous form, i.e. the data cannot be assigned to the respective participants in the study. The completely anonymized data of this study will be made available as "open data" in two secure, internet-based repositories: Open Science Framework (https://osf.io/), and GitHub (https://github.com/).<br/><br/>
          The anonymized data is stored for an indefinite period of time.<br/><br/>
          Furthermore, I have been informed that I can amend the given consent without stating any reasons with effect for the future or revoke it completely. I can send my declaration of cancellation by stating the study title "Help AI Summarize" and my Prolific ID by post or e-mail to<br/><br/>

          Changkun Ou<br/>
          Frauenlobstr. 7a<br/>
          Media Informatics Group<br/>
          80337 Munich, Germany<br/>
          changkun.ou@ifi.lmu.de<br/><br/>

          I hereby confirm that I have read and understood the above declaration of consent. I confirm that I voluntarily participate in the study and agree to the processing of my data by the University of Munich, Germany (GDPR info).
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} style={{fontWeight: "bold"}}>Consent and Start</Button>
        </DialogActions>
      </Dialog>
  );
}