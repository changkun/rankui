import './TaskDescription.css'
import { Box } from "@mui/material"
import { Typography } from "@mui/material"
import wordsCount from "words-count"
import TextField from '@mui/material/TextField';

export function TaskDescription(props) {
  const task = props.task
  const origin = task.origin
  const objective = task.objective.split('\n')

  return (
    <Box className="TaskDescription">
      <Box>Provide feedback about the summarized text to achieve these objectives:</Box>
      <Box>
       {objective && objective.map((desc, idx) => {
          return (
            <Typography
              key={idx}
              variant="body1"
              color="text.primary">
              <strong>Objective {idx+1}:</strong> {desc}
            </Typography>
          )
        })}
      </Box>
      <TextField
        sx={{
          marginTop: "20px",
          "& .MuiInputBase-input.Mui-disabled": {
            WebkitTextFillColor: "black",
          },
        }}
        fullWidth
        disabled
        id="outlined-multiline-static"
        label="Original Article"
        multiline
        rows={25}
        value={origin}
      />
      <Typography
        sx={{marginTop: '20px'}}
        variant="body2"
        color="text.secondary">
        <strong>Total: </strong>{wordsCount(origin)} words
      </Typography>
    </Box>
  )
}