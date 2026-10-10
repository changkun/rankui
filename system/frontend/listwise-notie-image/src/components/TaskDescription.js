import './TaskDescription.css'
import { Box, Card } from "@mui/material"
import { Typography } from "@mui/material"
import CardContent from "@mui/material/CardContent"
import CardMedia from '@mui/material/CardMedia';
import { servHost } from '../utils/endpoint';

export function TaskDescription(props) {
  const task = props.task
  const origin = task.origin

  return (
    <Box className="TaskDescription">
      <Card className="TaskDescription-Card">
        <CardMedia
          component="img"
          image={servHost + '/' + origin}
        />
        <CardContent>
          <Typography variant="h6" component="div">
            Original Photo
          </Typography>
          <Typography variant="body2" color="text.primary">
          Please provide feedback about AI-enhanced photos using the ranking
          tool on the right to tell how good the enhanced photo color is,
          compared to the original.

          The AI running in the background will improve the enhanced photos
          iteratively according to your feedback. You can click the "I'm satisfied"
          button to terminate if you think one of the photo fit your preference.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}