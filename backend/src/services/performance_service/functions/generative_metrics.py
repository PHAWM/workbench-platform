"""
Generative AI and NLP metrics.
"""

import numpy as np


def bleu_score_metric(references, predictions, **kwargs):
    """
    Calculate BLEU score for text generation.
    Requires nltk library.

    Args:
        references: List of reference texts
        predictions: List of predicted texts
        **kwargs: Additional arguments

    Returns:
        float: BLEU score
    """
    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

        smooth = SmoothingFunction().method1
        scores = []

        for ref, pred in zip(references, predictions):
            ref_tokens = [ref.split()]
            pred_tokens = pred.split()
            score = sentence_bleu(ref_tokens, pred_tokens, smoothing_function=smooth)
            scores.append(score)

        return np.mean(scores)
    except ImportError:
        return {'error': 'nltk library required for BLEU score', 'metric': 'bleu'}


def rouge_score_metric(references, predictions, rouge_type='rouge-l', **kwargs):
    """
    Calculate ROUGE score for text generation.
    Requires rouge-score library.

    Args:
        references: List of reference texts
        predictions: List of predicted texts
        rouge_type: Type of ROUGE ('rouge-1', 'rouge-2', 'rouge-l')
        **kwargs: Additional arguments

    Returns:
        dict: ROUGE scores (precision, recall, f1)
    """
    try:
        from rouge_score import rouge_scorer

        scorer = rouge_scorer.RougeScorer([rouge_type], use_stemmer=True)

        precisions = []
        recalls = []
        fscores = []

        for ref, pred in zip(references, predictions):
            scores = scorer.score(ref, pred)
            precisions.append(scores[rouge_type].precision)
            recalls.append(scores[rouge_type].recall)
            fscores.append(scores[rouge_type].fmeasure)

        return {
            'precision': np.mean(precisions),
            'recall': np.mean(recalls),
            'f1': np.mean(fscores)
        }
    except ImportError:
        return {'error': 'rouge-score library required for ROUGE score', 'metric': 'rouge'}


def perplexity_metric(loss_values, **kwargs):
    """
    Calculate perplexity from loss values.
    Common metric for language models.

    Args:
        loss_values: List of loss values (e.g., cross-entropy)
        **kwargs: Additional arguments

    Returns:
        float: Perplexity value
    """
    avg_loss = np.mean(loss_values)
    return np.exp(avg_loss)
