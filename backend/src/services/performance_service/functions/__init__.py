from src.services.performance_service.functions.accuracy import (
    accuracy_metric,
    confusion_matrix_metric,
    confusion_matrix_analysis,
    equalized_odds_metric,
    equal_opportunity_metric
)

from src.services.performance_service.functions.fairness import (
    demographic_parity_metric,
    demographic_parity_detailed,
    statistical_parity_metric,
    statistical_parity_detailed,
    disparate_impact_ratio,
    calibration_metric,
)

from src.services.performance_service.functions.classification_metrics import (
    precision_metric,
    recall_metric,
    f1_metric,
    fbeta_metric,
    roc_auc_metric,
    pr_auc_metric,
    balanced_accuracy_metric,
    mcc_metric,
    cohen_kappa_metric,
    log_loss_metric,
    brier_score_metric,
    hamming_loss_metric,
    jaccard_metric,
    specificity_metric,
    classification_report_metric,
    performance_summary_metric
)

from src.services.performance_service.functions.regression_metrics import (
    mse_metric,
    rmse_metric,
    mae_metric,
    mape_metric,
    r2_metric,
    explained_variance_metric,
    max_error_metric,
    median_absolute_error_metric,
    regression_summary_metric
)

from src.services.performance_service.functions.ranking_metrics import (
    ndcg_metric,
    top_k_accuracy_metric
)

from src.services.performance_service.functions.calibration_metrics import (
    expected_calibration_error_metric
)

from src.services.performance_service.functions.generative_metrics import (
    bleu_score_metric,
    rouge_score_metric,
    perplexity_metric
)

from src.services.performance_service.functions.keyword_metrics import (
    keyword_accuracy_metric,
    batch_keyword_accuracy_metric
)


METRICS_REGISTRY = {
    # Original metrics
    'accuracy': confusion_matrix_analysis,
    'confusion_matrix': confusion_matrix_metric,
    'confusion_matrix_analysis': confusion_matrix_analysis,
    'equalized_odds': equalized_odds_metric,
    'equal_opportunity': equal_opportunity_metric,
    'demographic_parity': demographic_parity_detailed,
    'statistical_parity': statistical_parity_detailed,
    'disparate_impact': disparate_impact_ratio,
    'calibration': calibration_metric,

    # Classification metrics
    'precision': precision_metric,
    'recall': recall_metric,
    'f1': f1_metric,
    'f1_score': f1_metric,
    'fbeta': fbeta_metric,
    'roc_auc': roc_auc_metric,
    'pr_auc': pr_auc_metric,
    'average_precision': pr_auc_metric,
    'balanced_accuracy': balanced_accuracy_metric,
    'mcc': mcc_metric,
    'matthews_correlation': mcc_metric,
    'cohen_kappa': cohen_kappa_metric,
    'log_loss': log_loss_metric,
    'cross_entropy': log_loss_metric,
    'brier_score': brier_score_metric,
    'hamming_loss': hamming_loss_metric,
    'jaccard': jaccard_metric,
    'iou': jaccard_metric,
    'specificity': specificity_metric,
    'classification_report': classification_report_metric,

    # Regression metrics
    'mse': mse_metric,
    'mean_squared_error': mse_metric,
    'rmse': rmse_metric,
    'root_mean_squared_error': rmse_metric,
    'mae': mae_metric,
    'mean_absolute_error': mae_metric,
    'mape': mape_metric,
    'mean_absolute_percentage_error': mape_metric,
    'r2': r2_metric,
    'r_squared': r2_metric,
    'explained_variance': explained_variance_metric,
    'max_error': max_error_metric,
    'median_absolute_error': median_absolute_error_metric,

    # Ranking & Retrieval metrics
    'ndcg': ndcg_metric,
    'normalized_dcg': ndcg_metric,
    'top_k_accuracy': top_k_accuracy_metric,

    # Calibration metrics
    'ece': expected_calibration_error_metric,
    'expected_calibration_error': expected_calibration_error_metric,

    # Generative AI metrics
    'bleu': bleu_score_metric,
    'rouge': rouge_score_metric,
    'perplexity': perplexity_metric,

    # Keyword matching metrics (for ANNIF and text classification)
    'keyword_accuracy': keyword_accuracy_metric,
    'batch_keyword_accuracy': batch_keyword_accuracy_metric,

    # Composite/Summary metrics
    'performance_summary': performance_summary_metric,
    'classification_summary': performance_summary_metric,
    'regression_summary': regression_summary_metric
}