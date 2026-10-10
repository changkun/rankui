from typing import List
import warnings
from botorch.exceptions import BadInitialCandidatesWarning
import glob
import os
import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

import torch
from botorch.fit import fit_gpytorch_model
from botorch.optim import optimize_acqf
from botorch.acquisition.preference import AnalyticExpectedUtilityOfBestOption
from botorch.models import SingleTaskGP
from gpytorch.mlls import ExactMarginalLogLikelihood
from botorch.models.pairwise_gp import PairwiseGP, PairwiseLaplaceMarginalLogLikelihood
from botorch.acquisition.monte_carlo import qNoisyExpectedImprovement
from botorch.utils import manual_seed, draw_sobol_samples
from gpytorch.kernels.matern_kernel import MaternKernel
from gpytorch.kernels.scale_kernel import ScaleKernel
from gpytorch.priors.torch_priors import GammaPrior

torch.set_printoptions(precision=10)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=BadInitialCandidatesWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

seed = 42  # for reproducibility


def load_pointwise(domain, user_id, session_id):
    # load tasks
    tasks = glob.glob(
        f'{os.path.dirname(__file__)}/../data/text-pointwise/tasks/*.json')

    tasks_info = {}
    for task in tasks:
        obj = json.load(open(task))
        tasks_info[Path(task).stem] = obj['ground_truth']

    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{os.path.dirname(__file__)}/../data/{domain}-pointwise/{user_id}-{session_id}/feedbacks/*.json')
    df = pd.DataFrame(columns=[
        'userID',
        'studyID',
        'sessionID',
        'taskID',
        'feedbackID',
        'groundTruth',
        'iteration',
        'completeIteration',
        'incompleteIteration',
        'rating',
        'skip',
        'timePresent',
        'timeLastRating',
        'timeSubmit',
        'comment'
    ])
    for feedback_file in files:
        param_folder = feedback_file.replace(
            'feedbacks', 'parameters').removesuffix('.json')
        param_file = [param for param in glob.glob(
            f'{param_folder}/*.json')][0]
        option_file = param_file.replace(
            'parameters', 'options').replace('.json', '.txt')
        feedback = json.load(open(feedback_file))
        param = json.load(open(param_file))

        if domain == 'text':
            option = open(option_file).read()
            feedback.update(param)
            feedback['option'] = option
            feedback['ground_truth'] = tasks_info[feedback['taskID']]
        elif domain == 'image':
            feedback.update(param)
            feedback['option'] = option_file
            feedback['ground_truth'] = tasks_info[feedback['taskID']]
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_pointwise_data(domain: str, user_id: str, session_id: str, task_id: str):
    df = load_pointwise(domain, user_id, session_id)
    df = df[df['taskID'] == task_id].reset_index(drop=True)
    X, y = [], []
    for _, row in df.iterrows():
        if domain == 'text':
            if row.skip or row.groundTruth[0] == True:
                continue
            X.append([
                row['reduction_ratio'],
                row['top_p'],
                row['temperature'],
                # row['repetition_penalty'],
                row['length_penalty'],
            ])
        elif domain == 'image':
            if row.skip:
                continue
            X.append([
                row['brightness'],
                row['contrast'],
                row['saturation'],
                row['temperature'],
                row['tint'],
            ])
        y = np.append(y, [row['rating']])
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32).reshape(-1, 1)


def load_pairwise(domain, user_id, session_id):
    files = glob.glob(
        f'{os.path.dirname(__file__)}/../data/{domain}-pairwise/{user_id}-{session_id}/feedbacks/*.json')
    df = pd.DataFrame(columns=[
        'userID',
        'studyID',
        'sessionID',
        'taskID',
        'feedbackID',
        'groundTruth',
        'iteration',
        'completeIteration',
        'incompleteIteration',
        'rating',
        'selection',
        'skip',
        'stop',
        'timePresent',
        'timeLastRating',
        'timeSubmit',
        'comment'
    ])
    for feedback_file in files:
        # load the feedback
        feedback = json.load(open(feedback_file))

        # load corresponding parameters
        param_folder = feedback_file.replace(
            'feedbacks', 'parameters').removesuffix('.json')
        options = [param for param in glob.glob(f'{param_folder}/*.json')]
        selection = feedback['selection']
        selection_id = feedback['rating']

        # if selection id is either 1 or 2 then this means users indicated
        # their preference; if selection id is 3 then it means selected
        # selected both. Otherwise, it means "I don't know".
        if selection_id < 3:
            if Path(options[selection_id-1]).stem != Path(selection).stem:
                options[1], options[0] = options[0], options[1]
        elif selection_id == 3 or selection_id == 0:
            if Path(options[0]).stem != Path(selection).stem:
                options[1], options[0] = options[0], options[1]
        feedback['options'] = options
        feedback['parameters'] = [
            json.load(open(param)) for param in options]
        if domain == 'text':
            feedback['optionsContent'] = [open(param.replace(
                'parameters', 'options').replace('.json', '.txt')).read() for param in options]
        elif domain == 'image':
            feedback['optionsContent'] = [param.replace(
                'parameters', 'options').replace('.json', '.jpg') for param in options]

        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timeLastRating', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_pairwise_data(domain: str, user_id: str, session_id: str, task_id: str):
    df = load_pairwise(domain, user_id, session_id)
    df = df[df['taskID'] == task_id].reset_index(drop=True)
    X, y = [], []

    i = 0
    for _, row in df[['taskID', 'parameters', 'rating', 'optionsContent', 'groundTruth']].iterrows():
        params = row['parameters']
        if domain == 'text':
            option1 = [
                params[0]['reduction_ratio'],
                params[0]['top_p'],
                params[0]['temperature'],
                # params[0]['repetition_penalty'],
                params[0]['length_penalty'],
            ]
            option2 = [
                params[1]['reduction_ratio'],
                params[1]['top_p'],
                params[1]['temperature'],
                # params[1]['repetition_penalty'],
                params[1]['length_penalty'],
            ]
        elif domain == 'image':
            option1 = [
                params[0]['brightness'],
                params[0]['contrast'],
                params[0]['saturation'],
                params[0]['temperature'],
                params[0]['tint'],
            ]
            option2 = [
                params[1]['brightness'],
                params[1]['contrast'],
                params[1]['saturation'],
                params[1]['temperature'],
                params[1]['tint'],
            ]
        if row['rating'] == 1 or row['rating'] == 2:
            if domain != 'text' or (row['groundTruth'][0] == False and row['groundTruth'][1] == False):
                X.append(option1)
                X.append(option2)
                if row['rating'] == 1:
                    y.append([i, i+1])
                elif row['rating'] == 2:
                    y.append([i+1, i])
                i += 2
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def load_listwise_rating(domain, user_id, session_id):
    # load tasks
    if domain == 'text':
        tasks = glob.glob(
            f'{os.path.dirname(__file__)}/../data/{domain}-listwise-rating/tasks/*.json')
        tasks_info = {}
        for task in tasks:
            obj = json.load(open(task))
            tasks_info[Path(task).stem] = obj['ground_truth']

    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{os.path.dirname(__file__)}/../data/{domain}-listwise-rating/{user_id}-{session_id}/feedbacks/*.json')
    df = pd.DataFrame(columns=[
        'userID',
        'studyID',
        'sessionID',
        'taskID',
        'feedbackID',
        'groundTruth',
        'iteration',
        'completeIteration',
        'incompleteIteration',
        'rating',
        'skip',
        'timePresent',
        'timeLastRating',
        'timeSubmit',
        'comment'
    ])
    for feedback_file in files:
        if domain == 'text':
            param_folder = feedback_file.replace(
                'feedbacks', 'parameters').removesuffix('.json')
            param_files = [param for param in glob.glob(
                f'{param_folder}/*.json')]
            options_file = [param_file.replace('parameters', 'options').replace(
                '.json', '.txt') for param_file in param_files]
            feedback = json.load(open(feedback_file))
            feedback['parameters'] = [
                json.load(open(param)) for param in param_files]
            feedback['option'] = [open(option_file).read()
                                  for option_file in options_file]
            feedback['ground_truth'] = tasks_info[feedback['taskID']]
        elif domain == 'image':
            feedback = json.load(open(feedback_file))
            options = feedback['options']
            parameters = [option_file.replace(
                'options', 'parameters') for option_file in options]
            parameters = [json.load(open(option_file.replace(
                '.jpg', '.json'))) for option_file in parameters]
            feedback['parameters'] = parameters
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_listwise_rating_data(domain: str, user_id: str, session_id: str, task_id: str):
    df = load_listwise_rating(domain, user_id, session_id)
    df = df[df['taskID'] == task_id].reset_index(drop=True)

    X, y = [], []
    for _, row in df.iterrows():
        for i in range(len(row.skip)):
            if domain == 'text':
                if row.skip[i] or row.groundTruth[i] == True:
                    continue
                params = row['parameters']
                param = [
                    params[i]['reduction_ratio'],
                    params[i]['top_p'],
                    params[i]['temperature'],
                    # params[i]['repetition_penalty'],
                    params[i]['length_penalty'],
                ]
            elif domain == 'image':
                if row.skip[i]:
                    continue
                params = row['parameters']
                param = [
                    params[i]['brightness'],
                    params[i]['contrast'],
                    params[i]['saturation'],
                    params[i]['temperature'],
                    params[i]['tint'],
                ]
            X.append(param)
            y.append(row['rating'][i])
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32).reshape(-1, 1)


def load_listwise_notie(domain, user_id, session_id):
    # load tasks
    if domain == 'text':
        tasks = glob.glob(
            f'{os.path.dirname(__file__)}/../data/{domain}-listwise-notie/tasks/*.json')
        tasks_info = {}
        for task in tasks:
            obj = json.load(open(task))
            tasks_info[Path(task).stem] = obj['ground_truth']

    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{os.path.dirname(__file__)}/../data/{domain}-listwise-notie/{user_id}-{session_id}/feedbacks/*.json')
    df = pd.DataFrame(columns=[
        'userID',
        'studyID',
        'sessionID',
        'taskID',
        'feedbackID',
        'groundTruth',
        'iteration',
        'completeIteration',
        'incompleteIteration',
        'rating',
        'skip',
        'timePresent',
        'timeLastRating',
        'timeSubmit',
        'comment'
    ])
    for feedback_file in files:
        if domain == 'text':
            param_folder = feedback_file.replace(
                'feedbacks', 'parameters').removesuffix('.json')
            param_files = [param for param in glob.glob(
                f'{param_folder}/*.json')]
            options_file = [param_file.replace('parameters', 'options').replace(
                '.json', '.txt') for param_file in param_files]
            feedback = json.load(open(feedback_file))
            feedback['parameters'] = [
                json.load(open(param)) for param in param_files]
            feedback['option'] = [open(option_file).read()
                                  for option_file in options_file]
            feedback['ground_truth'] = tasks_info[feedback['taskID']]
        elif domain == 'image':
            feedback = json.load(open(feedback_file))
            options = feedback['options']
            parameters = [option_file.replace(
                'options', 'parameters') for option_file in options]
            parameters = [json.load(open(option_file.replace(
                '.jpg', '.json'))) for option_file in parameters]
            feedback['parameters'] = parameters
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_listwise_notie_data(domain, user_id, session_id, task_id):
    df = load_listwise_notie(domain, user_id, session_id)
    df = df[df['taskID'] == task_id]

    X, y = [], []
    k = 0
    for _, row in df.iterrows():
        # infer ranking orders
        ranking = [-1, -1, -1, -1]
        for op in row.rating:
            if op['rating'] == '1st Choice':
                ranking[0] = op['id']
            elif op['rating'] == '2nd Choice':
                ranking[1] = op['id']
            elif op['rating'] == '3rd Choice':
                ranking[2] = op['id']
            elif op['rating'] == '4th Choice':
                ranking[3] = op['id']
            else:  # I don't know, incomplete preference, we don't use these data for training
                pass

        comparisons = []
        if ranking[0] != -1 and ranking[1] != -1:
            comparisons.append([ranking[0]+k, ranking[1]+k])
        if ranking[0] != -1 and ranking[2] != -1:
            comparisons.append([ranking[0]+k, ranking[2]+k])
        if ranking[0] != -1 and ranking[3] != -1:
            comparisons.append([ranking[0]+k, ranking[3]+k])
        if ranking[1] != -1 and ranking[2] != -1:
            comparisons.append([ranking[1]+k, ranking[2]+k])
        if ranking[1] != -1 and ranking[3] != -1:
            comparisons.append([ranking[1]+k, ranking[3]+k])
        if ranking[2] != -1 and ranking[3] != -1:
            comparisons.append([ranking[2]+k, ranking[3]+k])

        params = []
        for param in row.parameters:
            if domain == 'text':
                params.append([
                    param['reduction_ratio'],
                    param['top_p'],
                    param['temperature'],
                    # param['repetition_penalty'],
                    param['length_penalty'],
                ])
            elif domain == 'image':
                params.append([
                    param['brightness'],
                    param['contrast'],
                    param['saturation'],
                    param['temperature'],
                    param['tint'],
                ])
            elif domain == 'mesh':
                params.append([
                    param['reduction_ratio'],
                    param['keep_border'],
                    param['keep_hardedge'],
                    param['keep_sharpness'],
                    param['keep_quad'],
                ])

        X += params
        y += comparisons

        k += 4

    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def load_listwise_cantie(domain, user_id, session_id):
    # load tasks

    if domain == 'text':
        tasks = glob.glob(
            f'{os.path.dirname(__file__)}/../data/{domain}-listwise-cantie/tasks/*.json')
        tasks_info = {}
        for task in tasks:
            obj = json.load(open(task))
            tasks_info[Path(task).stem] = obj['ground_truth']

    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{os.path.dirname(__file__)}/../data/{domain}-listwise-cantie/{user_id}-{session_id}/feedbacks/*.json')
    df = pd.DataFrame(columns=[
        'userID',
        'studyID',
        'sessionID',
        'taskID',
        'feedbackID',
        'iteration',
        'rating',
        'skip',
        'timePresent',
        'timeLastRating',
        'timeSubmit',
        'comment'
    ])
    for feedback_file in files:
        if domain == 'text':
            param_folder = feedback_file.replace(
                'feedbacks', 'parameters').removesuffix('.json')
            param_files = [param for param in glob.glob(
                f'{param_folder}/*.json')]
            options_file = [param_file.replace('parameters', 'options').replace(
                '.json', '.txt') for param_file in param_files]
            feedback = json.load(open(feedback_file))
            feedback['parameters'] = [
                json.load(open(param)) for param in param_files]
            feedback['option'] = [open(option_file).read()
                                  for option_file in options_file]
            feedback['ground_truth'] = tasks_info[feedback['taskID']]
        elif domain == 'image':
            feedback = json.load(open(feedback_file))
            options = feedback['options']
            parameters = [option_file.replace(
                'options', 'parameters') for option_file in options]
            parameters = [json.load(open(option_file.replace(
                '.jpg', '.json'))) for option_file in parameters]
            feedback['parameters'] = parameters
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_listwise_cantie_data(domain, user_id, session_id, task_id):
    df = load_listwise_cantie(domain, user_id, session_id)
    df = df[df['taskID'] == task_id]

    X, y = [], []
    k = 0
    for _, row in df.iterrows():
        # infer rating position
        rating = ['', '', '', '']
        for op in row.rating:
            rating[op['id']] = op['rating']
        rating_map = {
            '1st Choice': 5,
            '2nd Choice': 4,
            '3rd Choice': 3,
            '4th Choice': 2,
            "I don't know": -1,
        }

        # convert rating to pairwise comparisons.
        # TODO: sadly we don't know how to utilize the ranking distance.
        # and the underlying PairwiseGP model does not handle ties.
        # So we just add two possible ranking pairs to simulate two
        # random choice. This maybe a bit over-simplified.
        ranking = [rating_map[r] for r in rating]
        comparisons = []
        if ranking[0] != -1 and ranking[1] != -1:
            if ranking[0] > ranking[1]:
                comparisons.append([0+k, 1+k])
            elif ranking[0] < ranking[1]:
                comparisons.append([1+k, 0+k])
            else:
                # Handling ties.
                pass
                comparisons.append([0+k, 1+k])
                comparisons.append([1+k, 0+k])

        if ranking[0] != -1 and ranking[2] != -1:
            if ranking[0] > ranking[2]:
                comparisons.append([0+k, 2+k])
            elif ranking[0] < ranking[2]:
                comparisons.append([2+k, 0+k])
            else:
                # Handling ties.
                pass
                comparisons.append([0+k, 2+k])
                comparisons.append([2+k, 0+k])

        if ranking[0] != -1 and ranking[3] != -1:
            if ranking[0] > ranking[3]:
                comparisons.append([0+k, 3+k])
            elif ranking[0] < ranking[3]:
                comparisons.append([3+k, 0+k])
            else:
                # Handling ties.
                pass
                comparisons.append([0+k, 3+k])
                comparisons.append([3+k, 0+k])

        if ranking[1] != -1 and ranking[2] != -1:
            if ranking[1] > ranking[2]:
                comparisons.append([1+k, 2+k])
            elif ranking[1] < ranking[2]:
                comparisons.append([2+k, 1+k])
            else:
                # Handling ties.
                pass
                comparisons.append([1+k, 2+k])
                comparisons.append([2+k, 1+k])

        if ranking[1] != -1 and ranking[3] != -1:
            if ranking[1] > ranking[3]:
                comparisons.append([1+k, 3+k])
            elif ranking[1] < ranking[3]:
                comparisons.append([3+k, 1+k])
            else:
                # Handling ties.
                pass
                comparisons.append([1+k, 3+k])
                comparisons.append([3+k, 1+k])

        if ranking[2] != -1 and ranking[3] != -1:
            if ranking[2] > ranking[3]:
                comparisons.append([2+k, 3+k])
            elif ranking[2] < ranking[3]:
                comparisons.append([3+k, 2+k])
            else:
                # Handling ties.
                pass
                comparisons.append([2+k, 3+k])
                comparisons.append([3+k, 2+k])

        params = []
        for param in row.parameters:
            if domain == 'text':
                params.append([
                    param['reduction_ratio'],
                    param['top_p'],
                    param['temperature'],
                    # param['repetition_penalty'],
                    param['length_penalty'],
                ])
            elif domain == 'image':
                params.append([
                    param['brightness'],
                    param['contrast'],
                    param['saturation'],
                    param['temperature'],
                    param['tint'],
                ])
            elif domain == 'mesh':
                params.append([
                    param['reduction_ratio'],
                    param['keep_border'],
                    param['keep_hardedge'],
                    param['keep_sharpness'],
                    param['keep_quad'],
                ])

        X += params
        y += comparisons
        k += 4

    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def load_listwise_ranking(domain, user_id, session_id):
    if domain == 'mesh':
        return load_listwise_ranking_mesh(user_id, session_id)

    if domain == 'text':
        # load tasks
        tasks = glob.glob(
            f'{os.path.dirname(__file__)}/../data/{domain}-listwise-ranking/tasks/*.json')
        tasks_info = {}
        for task in tasks:
            obj = json.load(open(task))
            tasks_info[Path(task).stem] = obj['ground_truth']

    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{os.path.dirname(__file__)}/../data/{domain}-listwise-ranking/{user_id}-{session_id}/feedbacks/*.json')
    df = pd.DataFrame(columns=[
        'userID',
        'studyID',
        'sessionID',
        'taskID',
        'feedbackID',
        'iteration',
        'rating',
        'skip',
        'timePresent',
        'timeLastRating',
        'timeSubmit',
        'comment'
    ])
    for feedback_file in files:
        if domain == 'text':
            param_folder = feedback_file.replace(
                'feedbacks', 'parameters').removesuffix('.json')
            param_files = [param for param in glob.glob(
                f'{param_folder}/*.json')]
            options_file = [param_file.replace('parameters', 'options').replace(
                '.json', '.txt') for param_file in param_files]
            feedback = json.load(open(feedback_file))
            feedback['parameters'] = [
                json.load(open(param)) for param in param_files]
            feedback['option'] = [open(option_file).read()
                                  for option_file in options_file]
            feedback['ground_truth'] = tasks_info[feedback['taskID']]
        elif domain == 'image':
            feedback = json.load(open(feedback_file))
            options = feedback['options']
            parameters = [option_file.replace(
                'options', 'parameters') for option_file in options]
            parameters = [json.load(open(option_file.replace(
                '.jpg', '.json'))) for option_file in parameters]
            feedback['parameters'] = parameters
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_listwise_ranking_mesh(user_id, session_id):
    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{os.path.dirname(__file__)}/../data/mesh-listwise-ranking/{user_id}-{session_id}/feedbacks/*.json')
    df = pd.DataFrame(columns=[
        'userID',
        'studyID',
        'sessionID',
        'taskID',
        'feedbackID',
        'iteration',
        'rating',
        'skip',
        'timePresent',
        'timeLastRating',
        'timeSubmit',
        'comment'
    ])
    for feedback_file in files:
        feedback = json.load(open(feedback_file))
        options = feedback['options']
        parameters = [option_file.replace(
            'options', 'parameters') for option_file in options]
        parameters = [json.load(open(option_file.replace(
            '.obj', '.json'))) for option_file in parameters]
        feedback['parameters'] = parameters
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_listwise_ranking_data(domain, user_id, session_id, task_id):
    df = load_listwise_ranking(domain, user_id, session_id)
    df = df[df['taskID'] == task_id]

    X, y = [], []
    k = 0
    for _, row in df.iterrows():
        # infer rating position
        rating = ['', '', '', '']
        for op in row.rating:
            rating[op['id']] = op['rating']
        rating_map = {
            'Excellent': 5,
            'Good': 4,
            'Fair': 3,
            'Poor': 2,
            'Terrible': 1,
            "I don't know": -1,
        }
        # convert rating to pairwise comparisons.
        # TODO: sadly we don't know how to utilize the ranking distance.
        # and the underlying PairwiseGP model does not handle ties.
        # So we just add two possible ranking pairs to simulate two
        # random choice. This maybe a bit over-simplified.
        ranking = [rating_map[r] for r in rating]
        comparisons = []
        if ranking[0] != -1 and ranking[1] != -1:
            if ranking[0] > ranking[1]:
                comparisons.append([0+k, 1+k])
            elif ranking[0] < ranking[1]:
                comparisons.append([1+k, 0+k])
            else:
                # Handling ties.
                pass
                comparisons.append([0+k, 1+k])
                comparisons.append([1+k, 0+k])

        if ranking[0] != -1 and ranking[2] != -1:
            if ranking[0] > ranking[2]:
                comparisons.append([0+k, 2+k])
            elif ranking[0] < ranking[2]:
                comparisons.append([2+k, 0+k])
            else:
                # Handling ties.
                pass
                comparisons.append([0+k, 2+k])
                comparisons.append([2+k, 0+k])

        if ranking[0] != -1 and ranking[3] != -1:
            if ranking[0] > ranking[3]:
                comparisons.append([0+k, 3+k])
            elif ranking[0] < ranking[3]:
                comparisons.append([3+k, 0+k])
            else:
                # Handling ties.
                pass
                comparisons.append([0+k, 3+k])
                comparisons.append([3+k, 0+k])

        if ranking[1] != -1 and ranking[2] != -1:
            if ranking[1] > ranking[2]:
                comparisons.append([1+k, 2+k])
            elif ranking[1] < ranking[2]:
                comparisons.append([2+k, 1+k])
            else:
                # Handling ties.
                pass
                comparisons.append([1+k, 2+k])
                comparisons.append([2+k, 1+k])

        if ranking[1] != -1 and ranking[3] != -1:
            if ranking[1] > ranking[3]:
                comparisons.append([1+k, 3+k])
            elif ranking[1] < ranking[3]:
                comparisons.append([3+k, 1+k])
            else:
                # Handling ties.
                pass
                comparisons.append([1+k, 3+k])
                comparisons.append([3+k, 1+k])

        if ranking[2] != -1 and ranking[3] != -1:
            if ranking[2] > ranking[3]:
                comparisons.append([2+k, 3+k])
            elif ranking[2] < ranking[3]:
                comparisons.append([3+k, 2+k])
            else:
                # Handling ties.
                pass
                comparisons.append([2+k, 3+k])
                comparisons.append([3+k, 2+k])

        params = []
        for param in row.parameters:
            if domain == 'text':
                params.append([
                    param['reduction_ratio'],
                    param['top_p'],
                    param['temperature'],
                    # param['repetition_penalty'],
                    param['length_penalty'],
                ])
            elif domain == 'image':
                params.append([
                    param['brightness'],
                    param['contrast'],
                    param['saturation'],
                    param['temperature'],
                    param['tint'],
                ])
            elif domain == 'mesh':
                params.append([
                    param['reduction_ratio'],
                    param['keep_border'],
                    param['keep_hardedge'],
                    param['keep_sharpness'],
                    param['keep_quad'],
                ])

        X += params
        y += comparisons
        k += 4
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def utility_bo(X: torch.tensor, y: torch.tensor, dim: int, q: int = 1, seed: int = seed):
    """Utility-based Bayesian Optimization: this function fits the input data to a
    GP model and returns the optimal hyperparameters for the next iteration of evaluation.

    This function can be used when the input interface is a single value slider.
    If the input interface contains multiple candidates and multiple corresponding sliders,
    set q > 1 to generate multiple candidates for the next evaluation.
    Args:
        X (torch.tensor): n x dim matrix of input points.
        y (torch.tensor): n x 1 vector of utility values.
        dim (int): number of hyperparameters.
        q (int, optional): number of next evaluation candidates. Defaults to 1.
    Returns:
        torch.tensor: q x dim matrix of optimal hyperparameters.
    """
    # with manual_seed(seed=seed):
    gp = SingleTaskGP(X, y)
    mll = ExactMarginalLogLikelihood(gp.likelihood, gp)
    fit_gpytorch_model(mll)

    # We use noisy expected improvements as we know that humans are not
    # well in doing absolute ratings. They will produce noise evaluations.
    qNEI = qNoisyExpectedImprovement(gp, X)
    candidates, acq_val = optimize_acqf(
        qNEI,
        bounds=torch.stack([torch.zeros(dim), torch.ones(dim)]),
        q=q,
        num_restarts=5,
        raw_samples=20,
    )
    return candidates, acq_val


def pairwise_bo(X: torch.tensor, y: torch.tensor, dim: int, seed=seed):
    """Pairwise Bayesian Optimization: this function fits the input data to a
    GP model and returns the optimal hyperparameters for the next iteration of
    evaluation. This function can only be used for paired user interface.

    Args:
        X (torch.tensor): n x dim matrix of input points.
        y (torch.tensor): n x 2 vector of preferential pairs. The first column
            is the index of the preferred candidate, the second column is the
            index of the less preferred candidate compared to the first candidate.
        dim (int): number of hyperparameters.
        seed (_type_, optional): random seed for reproducibility. Defaults to seed.

    Returns:
        _type_: _description_
    """
    # with manual_seed(seed=seed):
    bounds = torch.stack([torch.zeros(dim), torch.ones(dim)])
    gp = PairwiseGP(X, y,
                    covar_module=ScaleKernel(
                        MaternKernel(
                            nu=2.5,
                            lengthscale_prior=GammaPrior(3.0, 6.0),
                        ),
                        outputscale_prior=GammaPrior(2.0, 0.15),
                    ))
    mll = PairwiseLaplaceMarginalLogLikelihood(gp.likelihood, gp)
    fit_gpytorch_model(mll)

    candidates, acq_val = optimize_acqf(
        acq_function=AnalyticExpectedUtilityOfBestOption(pref_model=gp),
        bounds=bounds,
        q=2,
        num_restarts=5,
        raw_samples=20,
    )
    return candidates, acq_val


def mixed_bo(X: torch.tensor, y: torch.tensor, dim: int, q=2, seed=seed):
    """Listwise Bayesian Optimization: this function fits the input data to a
    GP model and returns the optimal hyperparameters for the next iteration of
    evaluation. This function can be used for ranking user interface.

    This model mixes a PairseGP and a SingleTaskGP model for learning the ranking.
    The provided X, and y are the data for pairwise training. When the training
    completes, we will use the trained utility to train another SingleTaskGP model.
    The acquisition function is a noisy EI function.
    """
    # with manual_seed(seed=seed):
    # Infer ranking utility from data.
    rankGP = PairwiseGP(X, y, covar_module=ScaleKernel(
                        MaternKernel(
                            nu=2.5,
                            lengthscale_prior=GammaPrior(3.0, 6.0),
                        ),
                        outputscale_prior=GammaPrior(2.0, 0.15),
                        ))
    mll = PairwiseLaplaceMarginalLogLikelihood(rankGP.likelihood, rankGP)
    fit_gpytorch_model(mll)
    if rankGP.utility is not None:
        y_utility = rankGP.utility.detach().clone().requires_grad_(True).reshape(-1, 1)
    else:
        # Retry another trianing and see if the utility will converge.
        maxRetry = 10
        for i in range(maxRetry):
            rankGP = PairwiseGP(X, y, covar_module=ScaleKernel(
                MaternKernel(
                    nu=2.5,
                    lengthscale_prior=GammaPrior(3.0, 6.0),
                ),
                outputscale_prior=GammaPrior(2.0, 0.15),
            ))
            mll = PairwiseLaplaceMarginalLogLikelihood(
                rankGP.likelihood, rankGP)
            fit_gpytorch_model(mll)
            if rankGP.utility is not None:
                y_utility = rankGP.utility.detach().clone().requires_grad_(True).reshape(-1, 1)
                break
        # If the utility does not converge, we will randomly remove the y and do more training
        if rankGP.utility is None:
            # Randomly remove half of the ranks.
            y_sample = y[torch.randperm(y.size(0))[:y.size(0)//2]]
            rankGP = PairwiseGP(X, y_sample, covar_module=ScaleKernel(
                MaternKernel(
                    nu=2.5,
                    lengthscale_prior=GammaPrior(3.0, 6.0),
                ),
                outputscale_prior=GammaPrior(2.0, 0.15),
            ))
            mll = PairwiseLaplaceMarginalLogLikelihood(
                rankGP.likelihood, rankGP)
            fit_gpytorch_model(mll)
            if rankGP.utility is not None:
                y_utility = rankGP.utility.detach().clone().requires_grad_(True).reshape(-1, 1)
            else:
                # We have done our best effort. Let's just set the utility to be zero.
                y_utility = torch.tensor(
                    [[0.0] * y.size(0)], dtype=torch.float32)

    # Train model with ranking utility.
    bounds = torch.stack([torch.zeros(dim), torch.ones(dim)])
    utilityGP = SingleTaskGP(X, y_utility)
    fit_gpytorch_model(ExactMarginalLogLikelihood(
        utilityGP.likelihood, utilityGP))
    qNEI = qNoisyExpectedImprovement(utilityGP, X)
    next_X, acq_val = optimize_acqf(
        qNEI,
        bounds=bounds,
        q=q,
        num_restarts=5,
        raw_samples=20,
    )
    return next_X, acq_val  # this is not a paired candidates


def sampling(ui: str, num_parameters: int, num_samples: int = 1, seed: int = seed) -> None:
    # with manual_seed(seed):
    if ui == 'pointwise':
        num_candidates = 1
    elif ui == 'pairwise':
        num_candidates = 2
    elif 'listwise' in ui:
        num_candidates = 4

    bounds = torch.stack(
        [torch.zeros(num_parameters), torch.ones(num_parameters)])
    candidates = draw_sobol_samples(bounds, num_samples, num_candidates)
    for candidate in candidates:
        print(candidate.tolist())


def estimate(ui: str, domain: str, user_id: str, session_id: str, task_id: str, num_parameters: int, seed: int = seed):
    if ui == 'pointwise':
        X, y = load_pointwise_data(domain, user_id, session_id, task_id)

        # pointwise only need to estimat one candidate
        candidates, _ = utility_bo(X, y, num_parameters, q=1, seed=seed)
        for candidate in candidates:
            print(candidate.tolist())

    elif ui == 'pairwise':
        X, y = load_pairwise_data(domain, user_id, session_id, task_id)

        # pairwise need to estimat two candidates for paired comparison
        candidates, _ = pairwise_bo(X, y, num_parameters, seed=seed)
        for candidate in candidates:
            print(candidate.tolist())

    elif ui == 'listwise-rating':
        X, y = load_listwise_rating_data(domain, user_id, session_id, task_id)

        # listwise-rating interface require 4 candidates for rating comparison
        # this is a fixed number to collaborate with the frontend
        candidates, _ = utility_bo(X, y, num_parameters, 4)
        for candidate in candidates:
            print(candidate.tolist())

    elif ui == 'listwise-ranking':
        X, y = load_listwise_ranking_data(domain, user_id, session_id, task_id)

        # listwise-ranking interface require 4 candidates for ranking comparison.
        # We use Mixed BO to estimate the next candidate.
        candidates, _ = mixed_bo(X, y, num_parameters, q=4)
        for candidate in candidates:
            print(candidate.tolist())

    elif ui == 'listwise-notie':
        X, y = load_listwise_notie_data(domain, user_id, session_id, task_id)

        # listwise-notie interface require 4 candidates therefore we cannot use
        # Pairwise BO directly. We use Mixed BO to train and infer the next
        # candidates.
        candidates, _ = mixed_bo(X, y, num_parameters, q=4, seed=seed)
        for candidate in candidates:
            print(candidate.tolist())

    elif ui == 'listwise-cantie':
        X, y = load_listwise_cantie_data(domain, user_id, session_id, task_id)

        # listwise-notie interface require 4 candidates therefore we cannot use
        # Pairwise BO directly. We use Mixed BO to train and infer the next
        # candidates.
        candidates, _ = mixed_bo(X, y, num_parameters, q=4, seed=seed)
        for candidate in candidates:
            print(candidate.tolist())
    return


def main():
    parser = argparse.ArgumentParser(description='bo_optimizers')
    pp = parser.add_argument
    pp('--action', type=str, default='estimate')  # or 'sample'
    pp('--ui', type=str, default='pointwise')

    pp('--domain', type=str, default='text')
    pp('--user_id', type=str, default='user_id')
    pp('--session_id', type=str, default='session_id')
    pp('--task_id', type=str, default='task_id')

    pp('--dim', type=int, default=4)
    pp('--num_samples', type=int, default=4)

    pp('--seed', type=int, default=seed)
    args = parser.parse_args()

    if args.action == 'sample':
        return sampling(args.ui, args.dim, num_samples=args.num_samples, seed=seed)
    elif args.action == 'estimate':
        return estimate(args.ui, args.domain, args.user_id, args.session_id, args.task_id, args.dim, seed=seed)
    else:
        raise ValueError('Invalid action')


if __name__ == '__main__':
    main()
