'''
This code exploits large language models (LLMs) as annotators.
Given an annotation task defined by a set of input texts, a set of possible labels,
and an instruction for the LLM, the code generates a prompt matching the input text and the instruction,
and uses an LLM to generate a label prediction for text. 
The text annotations produced by the LLM are then evaluated against the gold labels using accuracy and the Cohen's kappa metric.

Example usage:

python main.py \
    --data_file data/human_annotation/dim1_test.csv \
    --instruction_file instructions/pappa/dim1/nodesc_zeroshot.txt \
    --task_file tasks/pappa/dim1.json \
    --prompt_suffix "\\nLabel:" \
    --model_name google/flan-t5-small \
    --max_len_model 512 \
    --output_dir tmp \
    --cache_dir ~/.cache/huggingface/hub/ \
    --evaluation_only False
'''

import os
import fire
from utils import incremental_path, setup_logging

from lm_classifiers import HFClassifier, GPTClassifier
from task_manager import TaskManager

from logging import getLogger
logger = getLogger(__name__)

OPENAI_MODELS = [
    "gpt-4",
    "gpt-4-0613",
    "gpt-4-32k",
    "gpt-4-32k-0613",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo-16k-0613",
    "code-davinci-002",
    "text-davinci-003",
    "text-davinci-002",
    "text-davinci-001",
    "text-davinci",
    "text-curie-003",
    "text-curie-002",
    "text-curie-001",
    "text-curie",
    "davinci-codex",
    "curie-codex",
]

def classify_and_evaluate(
        data_file,
        task_file,
        instruction_file,
        prompt_suffix,
        model_name,
        max_len_model,
        output_dir,
        cache_dir=None,
        evaluation_only=False,
        only_dim=None,
        gpt_system_role="You are a helpful assistant.",
        sleep_after_step=0,
        aggregated_gold_name="agg"
        ):

    # Duplicate the output to stdout and a log file
    # strip points and slashes from the model name
    model_name_short = model_name.split("/")[-1].replace(".", "") # remove "username/" in case of HF models
    instruction_name = "/".join(instruction_file.split("/")[1:]).split(".")[0] # remove "instruction/"" and ".txt" from the instruction path
    output_base_dir = f"{output_dir}/{instruction_name}_{model_name_short}"
    output_dir = incremental_path(output_base_dir) if not evaluation_only else output_base_dir

    setup_logging(os.path.basename(__file__).split('.')[0], logger, output_dir)

    logger.info(f'Working on {output_dir}')

    # Define task and load data
    tm = TaskManager(task_file)
    input_texts, gold_labels = tm.read_data(data_file)

    # Define classifier
    if model_name in OPENAI_MODELS:
        classifier = GPTClassifier(
            labels_dict=tm.labels,
            label_dims=tm.label_dims,
            default_label=tm.default_label,
            instruction_file=instruction_file,
            prompt_suffix=prompt_suffix,
            model_name=model_name,
            max_len_model=max_len_model,
            output_dir=output_dir,
            gpt_system_role=gpt_system_role
            )

    else:
        classifier = HFClassifier(
            labels_dict=tm.labels,
            label_dims=tm.label_dims,
            default_label=tm.default_label,
            instruction_file=instruction_file,
            prompt_suffix=prompt_suffix,
            model_name=model_name,
            max_len_model=max_len_model,
            output_dir=output_dir,
            cache_dir=cache_dir
            )

    if evaluation_only:
        logger.info(f'Evaluation only. Loading raw predictions.')
        # Load raw predictions
        with open(os.path.join(output_dir, 'raw_predictions.txt'), 'r') as f:
            predictions = f.read().splitlines()
        prompts = None

    else:
        logger.info(f'Generating raw predictions.')
        # Generate raw predictions
        if model_name in OPENAI_MODELS:
            prompts, predictions = classifier.generate_predictions(input_texts, sleep_after_step=sleep_after_step)
        else:
            prompts, predictions = classifier.generate_predictions(input_texts)

        # Save raw predictions
        with open(os.path.join(output_dir, 'raw_predictions.txt'), 'w') as f:
            for prediction in predictions:
                f.write(prediction + "\n")

    if gold_labels is not None:
        logger.info(f'Gold labels found. Evaluating predictions.')

        # Retrieve predicted labels from raw predictions
        df_predicted_labels = classifier.retrieve_predicted_labels(
            predictions=predictions,
            prompts=prompts,
            only_dim=only_dim
            )

        # Evaluate predictions
        df_kappa, df_accuracy, df_f1 = classifier.evaluate_predictions(
            df=df_predicted_labels,
            gold_labels=gold_labels,
            aggregated_gold_name=aggregated_gold_name
            )

        # Save results
        df_predicted_labels.to_csv(os.path.join(output_dir, f'pred_dim3.tsv'), sep="\t", index=True)
        df_kappa.to_csv(os.path.join(output_dir, f'kap_dim3.tsv'), sep="\t", index=True)
        df_accuracy.to_csv(os.path.join(output_dir, f'acc_dim3.tsv'), sep="\t", index=True)
        df_f1.to_csv(os.path.join(output_dir, f'f1_dim3.tsv'), sep="\t", index=True)
    
    logger.info(f'Done!')

if __name__ == "__main__":
    fire.Fire(classify_and_evaluate)