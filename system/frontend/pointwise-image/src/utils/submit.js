// This file implements all data requests to three major endpoints.

import { endpointBegin, endpointFinish, endpointIterate } from "./endpoint"

export async function submitBeginForm(form) {
  try {
    const response = await fetch(endpointBegin, {
      method: 'POST',
      redirect: 'follow',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: form.userID,
        study_id: form.studyID,
        session_id: form.sessionID,
        data: form,
      })
    })
    // check if response is ok
    if (!response.ok) {
      return {ok: false, data: 'server error'}
    }
    const data = await response.json()
    return {ok: true, data: data}
  } catch {
    return {ok: false, data: 'server error'}
  }
}

export async function submitFinishForm(form) {
  const response = await fetch(endpointFinish, {
    method: 'POST',
    redirect: 'follow',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_id: form.userID,
      study_id: form.studyID,
      session_id: form.sessionID,
      task_id: form.taskID,
      data: form,
    })
  })
  // check if response is ok
  if (!response.ok) {
    return {ok: false, data: 'server error'}
  }
  const data = await response.json()
  return {ok: true, data: data}
}

export async function requestSamples(sessionInfo, data) {
  console.log('request next sample with session info: ', data)
  // FIXME: automatically set this to false after build?
  const mock = false
  if (mock) {
    return {
      mock: true,
      origin: 'https://research.poly.red/data/image-pointwise/tasks/1.jpg',
      options: [
        'https://research.poly.red/data/image-pointwise/tasks/1.jpg',
        'https://research.poly.red/data/image-pointwise/tasks/1.jpg',
        'https://research.poly.red/data/image-pointwise/tasks/1.jpg',
        'https://research.poly.red/data/image-pointwise/tasks/1.jpg']
    }
  }

  const response = await fetch(endpointIterate, {
    method: 'POST',
    redirect: 'follow',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_id: sessionInfo.userID,
      study_id: sessionInfo.studyID,
      session_id: sessionInfo.sessionID,
      task_id: sessionInfo.taskID,
      current_iteration: sessionInfo.currentIteration,
      last_feedback_id: sessionInfo.feedbackID,
      data: data,
    })
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  const respJSON = await response.json()

  console.log(respJSON)

  return {
    mock: false,
    origin: respJSON.origin,
    options: respJSON.options,
    feedbackID: respJSON.feedback_id,
  }
}