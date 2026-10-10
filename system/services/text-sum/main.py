from flask import request
from waitress import serve
from flask import Flask
from transformers import pipeline
from transformers import BartTokenizer, BartForConditionalGeneration, BartConfig
import torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model_name = 'sshleifer/distilbart-cnn-12-6'

# Disable model loading for testing.
enable_model = True

if enable_model:
    # Load the model to memory, and send the device to GPU if possible.
    # https://github.com/huggingface/transformers/blob/main/examples/research_projects/seq2seq-distillation/README.md
    model = BartForConditionalGeneration.from_pretrained(model_name).to(device)
    tokenizer = BartTokenizer.from_pretrained(model_name)

# Create a flask app to run the summarization service.
app = Flask(__name__)


# Greedy search and Beam search are known to not generate text well.
# Top-K sampling and Top-p sampling seems better performed.
#
# In Hugging face model generate, there are multiple modes:
#   - `is_greedy_gen_mode` stands for Greedy Search.
#     Require:
#        + num_beams == 1
#        + num_beam_groups == 1
#        + do_sample == False
#
#   - `is_beam_gen_mode` stands for Beam Search.
#     Require:
#        + num_beams > 1
#        + num_beam_groups == 1
#        + do_sample == False
#
#   - is_sample_gen_mode stands for Multinomial Sampling (with top_k and top_p).
# https://huggingface.co/blog/how-to-generate
# https://huggingface.co/blog/constrained-beam-search
# https://github.com/huggingface/transformers/issues/2704
def summarizer(text,
               reduction_ratio=0.5,
               top_p=1.0,
               temperature=1.0,
               repetition_penalty=1.0,
               length_penalty=1.0,
               num_return_sequences=1):
    inputs = tokenizer([text], return_tensors='pt', truncation=True).to(device)

    # determine min and max length based on the input text length
    # and reduction_ratio.
    input_ids_seq_length = inputs['input_ids'].shape[-1]

    # compute target token based on reduction ratio:
    max_new_tokens = input_ids_seq_length * (1 - reduction_ratio)
    if max_new_tokens + input_ids_seq_length <= 10:
        max_new_tokens = 10

    print('computed max_new_tokens: {}'.format(max_new_tokens))

    summary_ids = model.generate(inputs['input_ids'],
                                 # Define stopping criteria.
                                 # allow maximum 5 seconds of inference.
                                 max_time=5,

                                 # Set these parameters to use TopP sampling.
                                 do_sample=True,
                                 num_beams=1,
                                 num_beam_groups=1,
                                 # The number of highest probability vocabulary tokens to keep for
                                 # top-k-filtering. Default 1.0, and no upper bound.
                                 # We want to disable this because limiting the sample pool to a
                                 # fixed size K could endanger the model to produce gibberish for
                                 # sharp distributions and limit the model's creativity for flat
                                 # distribution. See https://arxiv.org/abs/1904.09751.
                                 top_k=0,

                                 # determine length
                                 min_length=10,
                                 max_length=None,
                                 max_new_tokens=max_new_tokens,

                                 # If set to float < 1, only the most probable tokens with
                                 # probabilities that add up to `top_p` or higher are kept for
                                 # generation. Default 1.0, from 0 to 1.
                                 top_p=top_p,
                                 # The value used to module the next token probabilities.
                                 # Default 1.0, from 0 to 1.
                                 temperature=temperature,
                                 # The parameter for repetition penalty. 1.0 means no penalty.
                                 # See https://arxiv.org/pdf/1909.05858.pdf for more details.
                                 # Default 1.0.
                                 repetition_penalty=repetition_penalty,
                                 # Exponential penalty to the length. 1.0 means that the beam
                                 # score is penalized by the sequence length. 0.0 means no penalty.
                                 # Set to values < 0.0 in order to encourage the model to generate
                                 # longer sequences, to a value > 0.0 in order to encourage the
                                 # model to produce shorter sequences. Default 1.0.
                                 length_penalty=length_penalty,

                                 # We desire one outcome per parameter set.
                                 num_return_sequences=num_return_sequences,
                                 )
    return [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=True) for g in summary_ids]


@app.before_request
def log_the_request():
    print(request)


@app.route("/summarize", methods=['GET', 'POST'])
def summarize():
    text = ''
    reduction_ratio = 0.5
    top_p = 1.0
    temperature = 1.0
    # repetition_penalty = 1.0
    length_penalty = 1.0
    # check if this is a GET request
    if request.method == 'GET':
        text = request.args.get('text', default='', type=str)
        reduction_ratio = request.args.get(
            'reduction_ratio', default=0.5, type=float)
        top_p = request.args.get('top_p', default=1.0, type=float)
        temperature = request.args.get('temperature', default=1.0, type=float)
        # repetition_penalty = request.args.get(
        #     'repetition_penalty', default=1.0, type=float)
        length_penalty = request.args.get(
            'length_penalty', default=1.0, type=float)
        num_return_sequences = request.args.get(
            'alternatives', default=1, type=int)
    elif request.method == 'POST':
        # parse query parameters
        text = request.json['text'] if 'text' in request.json else None
        reduction_ratio = request.json['reduction_ratio'] if 'reduction_ratio' in request.json else 0.5
        top_p = request.json['top_p'] if 'top_p' in request.json else 1.0
        temperature = request.json['temperature'] if 'temperature' in request.json else 1.0
        # repetition_penalty = request.json['repetition_penalty'] if 'repetition_penalty' in request.json else 1.0
        length_penalty = request.json['length_penalty'] if 'length_penalty' in request.json else 1.0
        num_return_sequences = request.json['alternatives'] if 'alternatives' in request.json else 1

    # let's guarantee reduction ratio it not going to be bigger than 0.9
    if reduction_ratio > 0.9:
        reduction_ratio = 0.9
    # temperature must be strictly positive
    if temperature < 0.0001:
        temperature = 0.0001

    print('received parameters:', reduction_ratio, top_p,
          temperature, length_penalty, num_return_sequences)
    print('input text:', text)
    # summarize the text
    if enable_model:
        summary = summarizer(text, reduction_ratio,
                             top_p=top_p,
                             temperature=temperature,
                             #  repetition_penalty=repetition_penalty,
                             length_penalty=length_penalty,
                             num_return_sequences=num_return_sequences)
    else:
        summary = ['model is not activated']
    print('current: ', summary)
    return {'text': summary}


print('text summarization service is running at: http://localhost:4563')
serve(app, listen='*:4563')
