// This file implements all data requests to three major endpoints.

import { servHost, endpointBegin, endpointFinish, endpointIterate } from "./endpoint"


export async function fetchTextContent(url) {
  const response = await fetch(url, {
    method: 'GET',
    mode: 'cors',
    headers: {
      'Referrer-Policy': 'no-referrer',
      'Access-Control-Allow-Origin': '*',
    }
  })
  return await response.text()
}

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

function mockContent() {
  const all = [
    'This is a test.',
    'This is another test.',
    'This is a third test.',
    'This is a fourth test.',
    'This is a fifth test.',
    'This is a sixth test.',
    'This is a seventh test.',
  ]
  return all[Math.floor(Math.random() * all.length)]
}

export async function requestPairSamples(sessionInfo, data) {
  console.log('request next sample with session info: ', data)
  // FIXME: automatically set this to false after build?
  const mock = false
  if (mock) {
    return {
      mock: true,
      origin: 'Interactive AI systems increasingly employ a human-in-the-loop strategy. This creates new challenges for the HCI community when designing such systems. We reveal and investigate some of these challenges in a case study with an industry partner, and developed a prototype human-in-the-loop system for preference-guided 3D model processing. Two 3D artists used it in their daily work for 3 months. We found that the human-AI loop often did not converge towards a satisfactory result and designed a lab study (N=20) to investigate this further. We analyze interaction data and user feedback through the lens of theories of human judgment to explain the observed human-in-the-loop failures with two key insights: 1) optimization using preferential choices lacks mechanisms to deal with inconsistent and contradictory human judgments; 2) machine outcomes, in turn, influence future user inputs via heuristic biases and loss aversion. To mitigate these problems, we propose descriptive UI design guidelines. Our case study draws attention to challenging and practically relevant imperfections in human-AI loops that need to be considered when designing human-in-the-loop systems.',
      objective: `Summarize the text as much as possible\nPreserve the meaning of the text`,
      options: [mockContent(), mockContent()],
      optionsContent: [mockContent(), mockContent()]
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
  const origin = await fetchTextContent(servHost + '/' + respJSON.origin)
  const objective = await fetchTextContent(servHost + '/' + respJSON.objective)
  const optionsContent = await Promise.all(respJSON.options.map(async (url) => {
    return await fetchTextContent(servHost + '/' + url)
  }))

  return {
    mock: false,
    origin: origin,
    objective: objective,
    options: respJSON.options,
    optionsContent: optionsContent,
    groundTruths: respJSON.ground_truths,
    feedbackID: respJSON.feedback_id,
  }
}