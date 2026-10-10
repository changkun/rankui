import * as React from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';

export function ConfirmDialog(props) {
  return (
    <Dialog open={props.open} sx={{ backdropFilter: "blur(5px)"}}>
      <DialogContent>
        Are you sure you are satisfied with the current results?
      </DialogContent>
      <DialogActions>
        <Button onClick={() => props.cancel()} style={{ fontWeight: "bold" }}>Cancel</Button>
        <Button onClick={() => props.confirm()} style={{ fontWeight: "bold" }}>Confirm</Button>
      </DialogActions>
    </Dialog>
  )
}
