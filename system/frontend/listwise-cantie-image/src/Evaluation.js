import './Evaluation.css'
import CardContent from '@mui/material/CardContent';
import Box from '@mui/material/Box';
import RankingComponent from './components/Ranking';
import { Card, CardMedia } from '@mui/material';
import Typography from '@mui/material/Typography';
import { servHost } from './utils/endpoint';

export function EvaluateContent(props) {
  const task = props.task
  const form = props.evaluate
  const setForm = props.setEval
  const submitForm = props.submitForm
  const setSatisfy = props.satisfy
  const reset = props.reset
  const setReset = props.setReset
  const alphabet = {0: 'A', 1: 'B', 2: 'C', 3: 'D'}
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
                <CardContent key={index}>
                  <Typography gutterBottom variant="h6" component="div">
                  {"AI Enhanced Photo " + alphabet[index]}
                  </Typography>
                </CardContent>
              </Card>
            )
          })}
        </Box>
      </Box>
      <Box className="Submit-Controller">
        <RankingComponent submitForm={submitForm} form={form} setForm={setForm} satisfy={setSatisfy} reset={reset} setReset={setReset}/>
      </Box>
    </Box>
  );
}