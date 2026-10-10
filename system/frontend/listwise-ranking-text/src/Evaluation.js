import './Evaluation.css'
import TextField from '@mui/material/TextField';
import CardContent from '@mui/material/CardContent';
import Box from '@mui/material/Box';
import RankingComponent from './components/Ranking';

export function EvaluateContent(props) {
  const task = props.task
  const form = props.evaluate
  const setForm = props.setEval
  const submitForm = props.submitForm
  const setSatisfy = props.satisfy
  const reset = props.reset
  const setReset = props.setReset
  const alphabet = {0: 'A', 1: 'B', 2: 'C', 3: 'D'}

  return (
    <Box className="Evaluation">
      <Box className="Content">
        {task.optionsContent.map((content, index) => {
          return (
            <CardContent key={index}>
              <TextField
                sx={{
                  "& .MuiInputBase-input.Mui-disabled": {
                    WebkitTextFillColor: "black",
                  },
                }}
                fullWidth
                disabled
                label={"AI Summarized Text " + alphabet[index]}
                multiline
                rows={6}
                value={content}
              />
            </CardContent>
          )
        })}
      </Box>
      <Box className="Submit-Controller">
        <RankingComponent submitForm={submitForm} form={form} setForm={setForm} satisfy={setSatisfy} reset={reset} setReset={setReset}/>
      </Box>
    </Box>
  );
}