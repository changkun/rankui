import './TaskDescription.css'
import { Box, Card } from "@mui/material"
import { Typography } from "@mui/material"
import CardContent from "@mui/material/CardContent"
import { servHost } from '../utils/endpoint';
import { useEffect, useRef, useState } from "react";
import { RenderComponent } from './MeshRenderer';

export function TaskDescription(props) {
  const task = props.task
  const config = props.config
  const reset = props.reset
  const origin = task.origin
  console.log('origin: ', origin)

  const ref = useRef(null)
  const [dimension, setDimension] = useState({width: 0, height: 400})
  useEffect(() => {
    const dim = ref.current.getBoundingClientRect()
    setDimension({width: dim.width, height: 400})
  }, [])
  console.log('description mesh: ', servHost + '/' + origin)
  return (
    <Box className="TaskDescription">
      <Card className="TaskDescription-Card" ref={ref}>
        {dimension.width > 0 && dimension.height > 0 && (
          <RenderComponent
            label={""}
            dimension={dimension}
            reset={reset}
            config={config}
            mesh={servHost + '/' + origin}
            showMenu={true}
            onLoad={() => {}}
          />
        )}<br/>
        <CardContent>
          <Typography variant="h6" component="div">
            Original 3D Model
          </Typography>
          <Typography variant="body2" color="text.primary">Please provide feedback about AI simplified 3D model using the ranking tool on the right to tell how good the simplification is, compared to the original. The AI running in the background will improve the simplification of 3D models iteratively, according to your feedback. You can click the "I'm satisfied" button to terminate if you think one of the simplified 3D models (mesh) fits your preference.
          </Typography><br/>
          <Typography variant="body2" color="text.primary">
          <strong>A good simplified 3D model means 1) reducing the number of polygons as much as possible; 2) keeping the important details and the overall shape of the original model; 3) the wireframe preserves the curvature flow.</strong>
          </Typography><br/>
          <Typography variant="body2" color="text.primary">
          You can change the view of the 3D model by dragging the mouse and zooming in/out by scrolling the mouse wheel. To change the visual assists, click the "wireframe" or "flat shading" to activate/deactivate different rendering modes.
          </Typography><br/>
          <Typography variant="body2" color="text.primary">
          <strong>Please keep your network stable and fast during the process.</strong>
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}