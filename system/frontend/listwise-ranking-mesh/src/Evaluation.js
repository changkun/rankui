import './Evaluation.css'
import Box from '@mui/material/Box';
import RankingComponent from './components/Ranking';
import { Card } from '@mui/material';
import { servHost } from './utils/endpoint';
import { RenderComponent } from './components/MeshRenderer';
import { useEffect, useRef, useState } from 'react';

export function EvaluateContent(props) {
  const task = props.task
  const config = props.config
  const form = props.evaluate
  const setForm = props.setEval
  const submitForm = props.submitForm
  const setSatisfy = props.satisfy
  const reset = props.reset
  const setReset = props.setReset
  const alphabet = {0: 'AI Simplified 3D Model A', 1: 'AI Simplified 3D Model B', 2: 'AI Simplified 3D Model C', 3: 'AI Simplified 3D Model D'}
  let loadedCount = 0
  const ref = useRef(null)
  const [dimension, setDimension] = useState({width: 0, height: 0})
  useEffect(() => {
    const dim = ref.current.getBoundingClientRect()
    setDimension({width: dim.width / 3, height: dim.height / 2})
  }, [])

  return (
    <Box className="Evaluation" ref={ref}>
      <Box className="EvaluationContent">
        <Box className="Cards">
          {task.options.map((content, index) => {
            console.log('model: ', servHost + '/' + content)
            return (
              <Card key={index} className="Card">
                {dimension.width > 0 && dimension.height > 0 && (
                  <RenderComponent
                    label={alphabet[index]}
                    dimension={dimension}
                    mesh={servHost + '/' + content}
                    config={config}
                    showMenu={false}
                    onLoad={() => {
                      loadedCount++
                      props.onLoad(loadedCount)
                    }}
                    reset={reset}
                  />
                )}
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