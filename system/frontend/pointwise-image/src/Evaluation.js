import './Evaluation.css'
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { Slider } from '@mui/material';
import { styled } from '@mui/material/styles';
import * as React from 'react';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import { initialSample } from './utils/iterations';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Alert from '@mui/material/Alert';
import { Card, CardMedia } from '@mui/material';
import { servHost } from './utils/endpoint';
import CardActions from '@mui/material/CardActions';

export const TinyText = styled(Typography)({
  fontSize: '0.75rem',
  opacity: 0.38,
  fontWeight: 500,
  letterSpacing: 0.2,
});

export function EvaluateContent(props) {
  const task = props.task
  const form = props.evaluate
  const setForm = props.setEval
  const submitForm = props.submitForm
  const [error, setError] = React.useState(false)
  let loadedCount = 0
  return (
    <Box className="Main-Content">
      <Box className="Content">
        {task && <Card>
          <CardMedia
            component="img"
            image={servHost + '/' + task.options}
            onLoad={() => {
              loadedCount++
              console.log('loaded: ', loadedCount)
              props.onLoad(loadedCount)
            }}
          />
        </Card>}
      </Box>

      <Box>
        <Typography
          variant="body2"
          color="text.secondary">
          I think AI did an excellent color enhancement.
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

      {/* <Box className="Feedbacks">
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
                label="This image (A) is better"
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
                label="This image (B) is better"
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
                label="They have the same enhanced quality"
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
            multiline
            maxRows={4}
            rows={2}
            value={form.comment}
          />
        </Box>
      </Box> */}
    </Box>
  );
}