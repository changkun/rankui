import glob
import json
import pandas as pd
from pathlib import Path

interfaces = [
    'pointwise',        # UI1
    'pairwise',         # UI2
    'listwise-rating',  # UI3
    'listwise-notie',   # UI4
    'listwise-cantie',  # UI5
    'listwise-ranking', # UI6
]

def load_data_by_domain(domain):
    df_begins = pd.DataFrame()
    df_all = pd.DataFrame()
    df_finishs = pd.DataFrame()

    batches = [1, 2, 3, 4] # text
    if domain == 'image':
        batches = [1]
    for interface in interfaces:
        print(interface)
        for batch in batches:
            df_begin, df_iter, df_finish = get_participants_data(domain, batch, interface)
            df_begin['interface'] = interface
            df_iter['interface'] = interface
            df_finish['interface'] = interface
            df_begins = pd.concat([df_begins, df_begin], ignore_index=True)
            df_all = pd.concat([df_all, df_iter], ignore_index=True)
            df_finishs = pd.concat([df_finishs, df_finish], ignore_index=True)
    return df_begins, df_all, df_finishs

def load_all_data():
    df_begins1, df_all1, df_finishs1 = load_data_by_domain('text')
    df_begins1['domain'] = 'text'
    df_all1['domain'] = 'text'
    df_finishs1['domain'] = 'text'
    df_begins2, df_all2, df_finishs2 = load_data_by_domain('image')
    df_begins2['domain'] = 'image'
    df_all2['domain'] = 'image'
    df_finishs2['domain'] = 'image'

    df_begins = pd.concat([df_begins1, df_begins2], ignore_index=True)
    df_all = pd.concat([df_all1, df_all2], ignore_index=True)
    df_finishs = pd.concat([df_finishs1, df_finishs2], ignore_index=True)

    df_participants = pd.DataFrame()
    for domain in ['text', 'image']:
        batches = [1, 2, 3, 4] # text
        if domain == 'image':
            batches = [1]
        for batch in batches:
            for interface in interfaces:
                df_participant = get_participants_demographics(domain, batch, interface)
                df_participant['domain'] = domain
                df_participants = pd.concat([df_participants, df_participant], ignore_index=True)

    df_participants.rename(columns={
        'domain': 'domain',
        'Participant id': 'user_id',
        'Submission id': 'session_id',
        'Started at': 'started_at',
        'Completed at': 'completed_at',
        'Time taken': 'time_taken',
        'Total approvals': 'total_approvals',
        'Fluent languages': 'fluent_languages',
        'Age': 'age',
        'Sex': 'sex',
        'Ethnicity simplified': 'ethnicity_simplified',
        'Country of birth': 'birth',
        'Country of residence': 'residence',
        'Language': 'language',
        'Student status': 'student',
        'Employment status': 'employment',
    }, inplace=True)
    df_participants
    df_prolific = df_participants[[
        'domain', 'user_id', 'session_id',
        'time_taken', 'total_approvals',
        'age', 'sex', 'fluent_languages',
        'ethnicity_simplified', 'birth',
        'residence', 'language', 'student', 'employment']]
    df_demographic = df_begins.rename(columns={'sessionID': 'session_id', 'userID': 'user_id'}).merge(df_prolific, on=['domain', 'user_id', 'session_id'], how='right')
    df_demographic = df_demographic[['domain', 'user_id', 'session_id', 'time_taken', 'total_approvals', 'age_x', 'age_y', 'sex', 'gender', 'fluent_languages', 'ethnicity_simplified', 'birth', 'residence', 'language', 'student', 'employment', 'interface', 'expertise', 'workExperience', 'lastExperience']]

    return df_begins, df_all, df_finishs, df_demographic

def get_participants_demographics(domain, study_batch, interface):
    df = pd.DataFrame()
    for f in glob.glob(f'{domain}/{study_batch}/{interface}/prolific_export*.csv'):
        df_meta = pd.read_csv(f)
        df = pd.concat([df, df_meta], ignore_index=True)
    df = df[df.Status == 'AWAITING REVIEW']
    return df


def get_participants_data(domain, study_batch, interface):
    loaders = {
        'pointwise': load_pointwise,               # ui1
        'pairwise': load_pairwise,                 # ui2
        'listwise-rating': load_listwise_rating,   # ui3
        'listwise-notie': load_listwise_notie,     # ui4
        'listwise-cantie': load_listwise_cantie,   # ui5
        'listwise-ranking': load_listwise_ranking, # ui6
    }

    participants = get_participants_demographics(
        domain, study_batch, interface)

    df_begin = pd.DataFrame()
    df_iter = pd.DataFrame()
    df_finish = pd.DataFrame()
    for _, p in participants.iterrows():
        user_id = p['Participant id']
        session_id = p['Submission id']
        df_begin2, df_iter2, df_finish2 = loaders[interface](
            domain, study_batch, interface, user_id, session_id)
        df_begin = pd.concat([df_begin, df_begin2], ignore_index=True)
        df_iter = pd.concat([df_iter, df_iter2], ignore_index=True)
        df_finish = pd.concat([df_finish, df_finish2], ignore_index=True)
    return df_begin, df_iter, df_finish


def load_pointwise(domain, study_batch, interface, user_id, session_id):
    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/feedbacks/*.json')
    df_iter = pd.DataFrame(columns=[
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
        'parameters',
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
            'parameters', 'options').replace('.json', '.txt' if domain == 'text' else '.jpg')
        feedback = json.load(open(feedback_file))
        param = json.load(open(param_file))
        feedback['parameters'] = [param]
        feedback['options'] = [option_file]
        df_iter = pd.concat(
            [df_iter, pd.DataFrame([feedback])], ignore_index=True)
    df_iter.sort_values(by='timePresent', inplace=True)
    df_iter.reset_index(drop=True, inplace=True)

    begin_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*begin.json')
    finish_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*finish.json')

    # there is only one begin file
    df_begin = pd.DataFrame([json.load(open(begin_files[0]))])
    df_finish = pd.DataFrame()
    for finish_file in finish_files:
        df_finish = pd.concat([df_finish, pd.DataFrame(
            [json.load(open(finish_file))])], ignore_index=True)
    df_finish.sort_values(by='finishTimestamp', inplace=True)

    return df_begin, df_iter, df_finish


def load_pairwise(domain, study_batch, interface, user_id, session_id):
    files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/feedbacks/*.json')
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
        feedback['parameters'] = [json.load(open(param)) for param in options]
        feedback['options'] = [param.replace(
            'parameters', 'options').replace('.json', '.txt' if domain == 'text' else '.jpg') for param in options]
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timeLastRating', inplace=True)
    df.reset_index(drop=True, inplace=True)

    begin_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*begin.json')
    finish_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*finish.json')

    # there is only one begin file
    df_begin = pd.DataFrame([json.load(open(begin_files[0]))])
    df_finish = pd.DataFrame()
    for finish_file in finish_files:
        df_finish = pd.concat([df_finish, pd.DataFrame(
            [json.load(open(finish_file))])], ignore_index=True)
    df_finish.sort_values(by='finishTimestamp', inplace=True)

    return df_begin, df, df_finish


def load_listwise_rating(domain, study_batch, interface, user_id, session_id):
    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/feedbacks/*.json')
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
        param_files = [param for param in glob.glob(f'{param_folder}/*.json')]
        options_file = [param_file.replace('parameters', 'options').replace(
            '.json', '.txt' if domain == 'text' else '.jpg') for param_file in param_files]
        feedback = json.load(open(feedback_file))
        feedback['parameters'] = [
            json.load(open(param)) for param in param_files]
        feedback['options'] = options_file
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)

    begin_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*begin.json')
    finish_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*finish.json')

    # there is only one begin file
    df_begin = pd.DataFrame([json.load(open(begin_files[0]))])
    df_finish = pd.DataFrame()
    for finish_file in finish_files:
        df_finish = pd.concat([df_finish, pd.DataFrame(
            [json.load(open(finish_file))])], ignore_index=True)
    df_finish.sort_values(by='finishTimestamp', inplace=True)

    return df_begin, df, df_finish


def load_listwise_notie(domain, study_batch, interface, user_id, session_id):
    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/feedbacks/*.json')
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
        param_files = [param for param in glob.glob(f'{param_folder}/*.json')]
        options_file = [param_file.replace('parameters', 'options').replace(
            '.json', '.txt' if domain == 'text' else '.jpg') for param_file in param_files]
        feedback = json.load(open(feedback_file))
        feedback['parameters'] = [
            json.load(open(param)) for param in param_files]
        feedback['options'] = options_file
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)

    begin_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*begin.json')
    finish_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*finish.json')

    # there is only one begin file
    df_begin = pd.DataFrame([json.load(open(begin_files[0]))])
    df_finish = pd.DataFrame()
    for finish_file in finish_files:
        df_finish = pd.concat([df_finish, pd.DataFrame(
            [json.load(open(finish_file))])], ignore_index=True)
    df_finish.sort_values(by='finishTimestamp', inplace=True)

    return df_begin, df, df_finish


def load_listwise_cantie(domain, study_batch, interface, user_id, session_id):
    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/feedbacks/*.json')
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
        param_files = [param for param in glob.glob(f'{param_folder}/*.json')]
        options_file = [param_file.replace('parameters', 'options').replace(
            '.json', '.txt' if domain == 'text' else '.jpg') for param_file in param_files]
        feedback = json.load(open(feedback_file))
        feedback['parameters'] = [
            json.load(open(param)) for param in param_files]
        feedback['options'] = options_file
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)

    begin_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*begin.json')
    finish_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*finish.json')

    # there is only one begin file
    df_begin = pd.DataFrame([json.load(open(begin_files[0]))])
    df_finish = pd.DataFrame()
    for finish_file in finish_files:
        df_finish = pd.concat([df_finish, pd.DataFrame(
            [json.load(open(finish_file))])], ignore_index=True)
    df_finish.sort_values(by='finishTimestamp', inplace=True)

    return df_begin, df, df_finish


def load_listwise_ranking(domain, study_batch, interface, user_id, session_id):
    # load feedbacks, parameters, and options.
    files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/feedbacks/*.json')
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
        param_files = [param for param in glob.glob(f'{param_folder}/*.json')]
        options_file = [param_file.replace('parameters', 'options').replace(
            '.json', '.txt' if domain == 'text' else '.jpg') for param_file in param_files]
        feedback = json.load(open(feedback_file))
        feedback['parameters'] = [
            json.load(open(param)) for param in param_files]
        feedback['options'] = options_file
        df = pd.concat([df, pd.DataFrame([feedback])], ignore_index=True)
    df.sort_values(by='timePresent', inplace=True)
    df.reset_index(drop=True, inplace=True)

    begin_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*begin.json')
    finish_files = glob.glob(
        f'{domain}/{study_batch}/{interface}/{user_id}-{session_id}/*finish.json')

    # there is only one begin file
    df_begin = pd.DataFrame([json.load(open(begin_files[0]))])
    df_finish = pd.DataFrame()
    for finish_file in finish_files:
        df_finish = pd.concat([df_finish, pd.DataFrame(
            [json.load(open(finish_file))])], ignore_index=True)
    df_finish.sort_values(by='finishTimestamp', inplace=True)
    return df_begin, df, df_finish
