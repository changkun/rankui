import * as React from 'react';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import { Typography } from '@mui/material';
import Box from '@mui/material/Box';
import { DragDropContext, Draggable, Droppable } from "react-beautiful-dnd";
import classes from "./Ranking.module.scss";
import classnames from "classnames";
import Tooltip from '@mui/material/Tooltip';
import { initialSample } from '../utils/iterations';
import Alert from '@mui/material/Alert';

const ids = ["A", "B", "C", "D"];
const ratings = ["Excellent", "Good", "Fair", "Poor", "Terrible", "I don't know"];
const getDroppableItemContainerId = (draggableItemId) =>
  `droppable-${draggableItemId}`;

const getInitDraggableItems = (ids) =>
  ids.map((id, index) => ({
    draggableId: id,
    index,
    currentDroppedContainerId: getDroppableItemContainerId(id),
  }));

const DraggableItem = ({
  draggableId,
  index,
  isVisible,
}) => {
  return isVisible ? (
    <Draggable draggableId={draggableId} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={classnames(classes.DraggableBox, {
            [classes.DraggableBox_isDragging]: snapshot.isDragging,
          })}
        >
          <hr />
          <hr />
          <hr />
          <p>{draggableId}</p>
        </div>
      )}
    </Draggable>
  ) : null;
};
const ItemContainer = ({
  id,
  draggableItemId,
  draggableItemIndex,
  draggableItemCurrentDroppedContainerId,
}) => (
  <Droppable droppableId={id} isDropDisabled={true}>
    {(provided) => (
      <div
        {...provided.droppableProps}
        ref={provided.innerRef}
        className={classnames(classes.ContainerOption, classes.ItemContainer)}
      >
        <DraggableItem
          draggableId={draggableItemId}
          index={draggableItemIndex}
          isVisible={id === draggableItemCurrentDroppedContainerId}
        />
        {provided.placeholder}
      </div>
    )}
  </Droppable>
);

const RankingContainer = ({ id, items }) => {
  let boxname = classes.ContainerBox
  if (id === "I don't know") {
    boxname = classes.ContainerBoxWarning
  }
  return (
    <div className={classnames(boxname, classes.DroppableRankingContainer)}>
      <div className={classes.Text}>{id}</div>
      <Droppable droppableId={id} direction="horizontal">
        {(provided, snapshot) => (
          <div
            {...provided.droppableProps}
            ref={provided.innerRef}
            className={classnames(classes.DroppableArea, {
              [classes.DroppableArea_isDraggingOver]: snapshot.isDraggingOver,
            })}
          >
            {items.map((item) =>
              id === item.currentDroppedContainerId ? (
                <div className={classes.DroppedItem} key={item.draggableId}>
                  <DraggableItem
                    className={classes.DroppedItem}
                    draggableId={item.draggableId}
                    index={item.index}
                    isVisible={id === item.currentDroppedContainerId}
                  />
                </div>
              ) : null
            )}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </div>
  )
};

function DragAndDrop({ onRatingChange, reset, setReset }) {
  const [items, setItems] = React.useState(getInitDraggableItems(ids));

  const resetItems = () => setItems(getInitDraggableItems(ids))
  React.useEffect(() => {
    resetItems()
    setReset(false)
  }, [reset, setReset])

  const handleDragEnd = (result) => {
    // dropped outside the list
    if (!result.destination) {
      return;
    }

    const draggedItem = items.find((item) => item.draggableId === result.draggableId);
    const droppableId = result.destination.droppableId;

    draggedItem.currentDroppedContainerId = droppableId;
    setItems([...items]);

    onRatingChange(draggedItem.draggableId, droppableId);
  };

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <div className={classes.Container}>
        <div className={classes.ItemsContainer}>
          {items.map((item) => (
            <ItemContainer
              key={getDroppableItemContainerId(item.draggableId)}
              id={getDroppableItemContainerId(item.draggableId)}
              draggableItemId={item.draggableId}
              draggableItemIndex={item.index}
              draggableItemCurrentDroppedContainerId={item.currentDroppedContainerId}
            />
          ))}
        </div>
        {ratings.map((rating) => (
          <RankingContainer id={rating} key={rating} items={items} />
        ))}
      </div>
    </DragDropContext>
  );
};

export default function RankingComponent(props) {
  const submitForm = props.submitForm
  const form = props.form
  const setForm = props.setForm
  const setSatisfy = props.satisfy
  const reset = props.reset
  const setReset = props.setReset

  const [error, setError] = React.useState(false);
  const [state, setState] = React.useState({});
  const rankingSequence = React.useRef([])

  const id2index = {
    'A': 0,
    'B': 1,
    'C': 2,
    'D': 3,
  }
  const handleRatingChange = (id, rating) => {
    rankingSequence.current.push({
      id: id2index[id],
      rating: rating,
      timestamp: Date.now() })
    setForm({ ...form, rating: rankingSequence.current })
    setState({ ...state, [id]: rating });
  };
  return (
    <>
      <Box className={classes.RankingBox}>
        <Typography className={classes.Usage}>
          Drag and drop the following boxes to <strong>rank</strong> AI enhanced results.
        </Typography>
        <div className={classes.DragDropGroup}>
          <DragAndDrop onRatingChange={handleRatingChange} reset={reset} setReset={setReset} />
        </div>
      </Box>
      <Box>
        <div className={classes.Comment}>
          <TextField
            onChange={e => setForm(prev => ({...prev, comment: e.target.value}))}
            fullWidth
            label="Explain why did you give this feedback"
            rows={2}
            value={form.comment}
          />
        </div>
        {error && <Alert severity="info" sx={{marginTop: '20px', marginBottom: '20px'}}>Please indicate feedback to all results.</Alert>}
        <div className={classes.ButtonGroup}>
          <Tooltip title={'AI will try to improve itself based on your feedback'}
            disableHoverListener={!(form.skip || form.completeIteration + form.incompleteIteration < initialSample)}>
            <Box>
              <Button variant="contained" onClick={() => {
                console.log('submit: ', rankingSequence.current)
                const boxes = {}
                for (const seq of rankingSequence.current) {
                  console.log(seq, seq.id)
                  boxes[seq.id] = true
                }
                console.log(boxes, Object.keys(boxes).length)
                if (Object.keys(boxes).length < 4) {
                  setError(true)
                  return
                }
                setError(false)
                rankingSequence.current = []
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
                  const boxes = {}
                  for (const seq of rankingSequence.current) {
                    console.log(seq, seq.id)
                    boxes[seq.id] = true
                  }
                  console.log(boxes, Object.keys(boxes).length)
                  if (Object.keys(boxes).length < 4) {
                    setError(true)
                    return
                  }
                  setError(false)
                  setSatisfy(true)
                }}
                >I'm satisfied</Button>
            </Box>
          </Tooltip>
        </div>
      </Box>
    </>
  );
};