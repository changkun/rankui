import './Evaluation.css'
import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Alert from '@mui/material/Alert';

import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';

import { initialSample } from './utils/iterations'

export function EvaluateContent(props) {
  const task = props.task
  const form = props.evaluate
  const setForm = props.setEval
  const submitForm = props.submitForm
  const [error, setError] = React.useState(false)

  return (
    <Box className="Main-Content">
      <Box className="Content">
        {task.optionsContent.map((content, index) => {
          return (
            <CardContent className="PairContent" key={index}>
              <TextField
                sx={{
                  "& .MuiInputBase-input.Mui-disabled": {
                    WebkitTextFillColor: "black",
                  },
                }}
                fullWidth
                disabled
                label={"AI Summarized Text " + (index+1)}
                multiline
                rows={14}
                value={content}
              />
            </CardContent>
          )
        })}
      </Box>
      <Box className="Feedbacks">
        <RadioGroup row className="Checkbox" value={form.rating} onClick={(e) => {
          if (form.rating === e.target.value && form.rating !== 0) {
            setForm({ ...form, rating: 0 })
          }
        }} onChange={e => {
          setForm(prev => ({...prev, rating: parseInt(e.target.value), timeLastRating: Date.now()}))
        }}>
          <Box className="ExclusiveCheckboxGroup">
            <Box className="ExclusiveCheckbox1">
              <FormControlLabel
                // we decided to not diable the checkbox if they checked "I don't know".
                // disabled={form.skip}
                control={<Radio />}
                onChange={e => {
                  setError(false)
                }}
                label="Text 1 is better"
                value={1}
                sx={{width: '50%'}}
              />
              <FormControlLabel
                // we decided to not diable the checkbox if they checked "I don't know".
                // disabled={form.skip}
                control={<Radio />}
                onChange={e => {
                  setError(false)
                }}
                label="Text 2 is better"
                value={2}
              />
            </Box>
            <Box className="ExclusiveCheckbox2">
              <FormControlLabel
                // we decided to not diable the checkbox if they checked "I don't know".
                // disabled={form.skip}
                control={<Radio />}
                onChange={e => {
                  setError(false)
                }}
                label="They have the same quality"
                value={3}
              />
            </Box>
          </Box>
        </RadioGroup>
        <Box className="Feedback-Controller">
          <Tooltip title="Check it if you are uncertain about this feedback" placement="top">
            <Box className='Feedback-Disable'>
              <FormControlLabel
                control={<Checkbox />}
                checked={form.skip}
                onChange={e => {
                  setError(false)
                  setForm(prev => ({...prev,
                    skip: e.target.checked,
                    timeLastRating: Date.now(),
                  }))
                }}
                label="I don't know which is better"
              />
            </Box>
          </Tooltip>
          {error && <Alert severity="info" sx={{marginTop: '20px', marginBottom: '20px'}}>Please indicate your feedback.</Alert>}
          <TextField
            onChange={e => setForm(prev => ({...prev, comment: e.target.value}))}
            fullWidth
            label="Explain why did you give this feedback"
            rows={2}
            value={form.comment}
          />
        </Box>
      </Box>

      <CardActions className="Submit-Controller">
        <Tooltip title={'AI will try to improve itself based on your feedback'}
          disableHoverListener={!(form.skip || form.completeIteration + form.incompleteIteration < initialSample)}>
          <Box>
            <Button variant="contained" onClick={() => {
              if (form.rating === 0 && !form.skip) {
                setError(true)
                return
              }
              submitForm()
            }}>Submit Feedback</Button>
          </Box>
        </Tooltip>
        <Tooltip title="This button will be available after a few iterations."
          disableHoverListener={!(form.skip || form.completeIteration + form.incompleteIteration < initialSample)}>
          <Box>
            <Button variant="contained"
              disabled={form.skip || form.completeIteration + form.incompleteIteration < initialSample}
              onClick={() => {
                if (form.rating === 0 && !form.skip) {
                  setError(true)
                  return
                }
                props.satisfy(true)
              }}
              >I'm satisfied</Button>
          </Box>
        </Tooltip>
      </CardActions>
    </Box>
  );
}