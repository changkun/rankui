import './Evaluation.css'
import * as React from 'react';
import Box from '@mui/material/Box';
import Slider from '@mui/material/Slider';
import Button from '@mui/material/Button';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Tooltip from '@mui/material/Tooltip';
import Alert from '@mui/material/Alert';
import { TinyText } from './components/FinishDialog';

import { initialSample } from './utils/iterations'

export function EvaluateContent(props) {
  const task = props.task
  const form = props.evaluate
  const setForm = props.setEval
  const submitForm = props.submitForm
  const [error, setError] = React.useState(false)

  return (
    <Box className="Main-Content">
      <Box>
      <CardContent>
        {task && <TextField
          sx={{
            "& .MuiInputBase-input.Mui-disabled": {
              WebkitTextFillColor: "black",
            },
          }}
          fullWidth
          disabled
          label="AI Summarized Text"
          multiline
          rows={16}
          value={task.options}
        />}
      </CardContent>
      </Box>
      <Box>
        <Typography
          variant="body2"
          color="text.secondary">
          I think AI did an excellent summarization.
        </Typography>
        <Box className="Feedback-Controller">
          <Box
            className="Feedback-Rater">
            <Slider
              value={form.rating}
              track={false}
              // NOTE: design issue: if we do not disable the slider,
              // we will have to explain to the user why the slider is
              // still interactive.
              // But we still decided to not diable the checkbox if they
              // checked "I don't know".
              // disabled={form.skip}
              onChange={e => setForm(prev => ({...prev,
                rating: e.target.value,
                timeLastRating: Date.now(),
              }))}
            />
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <TinyText>Strongly Disagree</TinyText>
              <TinyText>Strongly Agree</TinyText>
            </Box>
          </Box>
          <Tooltip title="Check it if you are uncertain about this feedback">
            <Box className='Feedback-Disable'>
              <FormControlLabel
                control={<Checkbox />}
                checked={form.skip}
                onChange={e => setForm(prev => ({...prev,
                  skip: e.target.checked,
                  timeLastRating: Date.now(),
                }))}
                label="I don't know"
              />
            </Box>
          </Tooltip>
        </Box>
        <Box className="Feedback-Controller">
          <TextField
            onChange={e => setForm(prev => ({...prev, comment: e.target.value}))}
            fullWidth
            label="Explain why did you give this feedback"
            rows={2}
            value={form.comment}
          />
        </Box>
      </Box>
      {error && <Alert severity="info" sx={{marginTop: '20px', marginBottom: '20px'}}>Please use the slider to indicate your evaluation at least once.</Alert>}
      <CardActions className="Submit-Controller">
        <Tooltip title={'AI will try to improve itself based on your feedback'}
          disableHoverListener={!(form.skip || form.completeIteration + form.incompleteIteration < initialSample)}>
          <Box>
            <Button variant="contained" onClick={() => {
              if (form.timeLastRating === 0) {
                setError(true)
                return
              }
              setError(false)
              submitForm()
            }}>Submit Feedback</Button>
          </Box>
        </Tooltip>
        <Tooltip title="This button will be available after a few iterations."
          disableHoverListener={!(form.skip || form.completeIteration + form.incompleteIteration < initialSample)}>
          <Box>
            <Button variant="contained"
              disabled={form.skip || form.completeIteration + form.incompleteIteration < initialSample}
              onClick={() => props.satisfy(true)}
              >I'm satisfied</Button>
          </Box>
        </Tooltip>
      </CardActions>
    </Box>
  );
}