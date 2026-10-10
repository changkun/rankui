import './Evaluation.css'
import CardContent from '@mui/material/CardContent';
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
  const setSatisfy = props.satisfy
  const alphabet = {0: 'A', 1: 'B', 2: 'C', 3: 'D'}
  const [error, setError] = React.useState(0)
  let loadedCount = 0

  return (
    <Box className="Evaluation">
      <Box className="EvaluationContent">
        <Box className="Cards">
        {task.options.map((content, index) => {
          return (
            <Card key={index} className="Card">
              <CardMedia
                component="img"
                image={servHost + '/' + content}
                onLoad={() => {
                  loadedCount++
                  console.log('loaded: ', loadedCount)
                  props.onLoad(loadedCount)
                }}
              />
              <CardContent key={index} sx={{":last-child": {paddingBottom: 0}}}>
              <Box className="Feedback-Rater">
                <Typography
                  variant="body2"
                  color="text.primary">
                  I think AI did an excellent photo enhancement in this image ({alphabet[index]}).
                </Typography>
                <Slider
                  value={form.rating[index]}
                  track={false}
                  onChange={e => {
                    const rating = form.rating
                    rating[index] = e.target.value
                    const timeLastRating = form.timeLastRating
                    timeLastRating[index] = Date.now()

                    setForm(prev => ({...prev,
                      rating: rating,
                      timeLastRating: timeLastRating,
                    }))
                  }}
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
                <Tooltip title="Check it if you are uncertain about this feedback">
                  <Box className='Feedback-Disable'>
                    <FormControlLabel
                      sx={{color: '#777'}}
                      control={<Checkbox />}
                      checked={form.skip[index]}
                      onChange={e => {
                        const check = form.skip
                        check[index] = e.target.checked
                        const timeLastRating = form.timeLastRating
                        timeLastRating[index] = Date.now()
                        setForm(prev => ({...prev,
                          skip: check,
                          timeLastRating: timeLastRating,
                        }))
                      }}
                      label="I don't know"
                    />
                  </Box>
                </Tooltip>
              </Box>
              </CardContent>
            </Card>
          )
        })}
        </Box>

      </Box>
      <Box className="Submit-Controller">
      {error > 0 && <Alert severity="info" sx={{marginTop: '20px', marginBottom: '20px'}}>Please use the slider {alphabet[error-1]} to indicate your evaluation at least once.</Alert>}
        <div className="Comment" >
          <TextField
            onChange={e => setForm(prev => ({...prev, comment: e.target.value}))}
            fullWidth
            label="Explain why did you give this feedback"
            multiline
            maxRows={5}
            rows={5}
            value={form.comment}
          />
        </div>
        <div className="ButtonGroup">
          <Tooltip title={'AI will try to improve itself based on your feedback'}
            disableHoverListener={!(form.completeIteration + form.incompleteIteration < initialSample)}>
            <Box>
              <Button variant="contained" onClick={() => {
                let found = false
                for (let i = 0; i < 4; i++) {
                  if (form.timeLastRating[i] === 0 && !form.skip[i]) {
                    setError(i+1)
                    found = true
                    break
                  } else {
                    setError(0)
                  }
                }
                if (found) {
                  return
                }
                console.log(error)
                setError(0)
                submitForm()
              }}>Submit Feedback</Button>
            </Box>
          </Tooltip>
          <Tooltip title="This button will be available after a few iterations."
            disableHoverListener={!(form.completeIteration + form.incompleteIteration < initialSample)}>
            <Box>
              <Button variant="contained"
                disabled={form.completeIteration + form.incompleteIteration < initialSample}
                onClick={() => {
                  console.log('satisfied: ', form)
                  setSatisfy(true)
                }}
                >I'm satisfied</Button>
            </Box>
          </Tooltip>
        </div>
      </Box>
    </Box>
  );
}