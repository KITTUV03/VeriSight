"""
Direct Preference Optimization (DPO) Loss & Reward Calculation.

Implements the Bradley-Terry preference objective under closed-form policy optimization
(Rafailov et al., NeurIPS 2023):
    L_DPO(pi_theta; pi_ref) = - E [ log sigma( beta * ( log(pi_theta(yw|x)/pi_ref(yw|x))
                                                      - log(pi_theta(yl|x)/pi_ref(yl|x)) ) ) ]
"""

import math
from typing import Dict, Tuple, Union, Any, List

try:
    import torch
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def dpo_loss_numpy(
    policy_chosen_logps: List[float],
    policy_rejected_logps: List[float],
    reference_chosen_logps: List[float],
    reference_rejected_logps: List[float],
    beta: float = 0.1,
    label_smoothing: float = 0.0,
) -> Tuple[float, Dict[str, float]]:
    """
    Pure Python / NumPy compatible DPO loss calculation.
    
    Args:
        policy_chosen_logps: Log probabilities of chosen responses under policy pi_theta
        policy_rejected_logps: Log probabilities of rejected responses under policy pi_theta
        reference_chosen_logps: Log probabilities of chosen responses under reference pi_ref
        reference_rejected_logps: Log probabilities of rejected responses under reference pi_ref
        beta: DPO temperature scaling factor (default: 0.1)
        label_smoothing: Conservative DPO label smoothing factor
        
    Returns:
        (loss, metrics_dict)
    """
    n = len(policy_chosen_logps)
    if n == 0:
        return 0.0, {}

    total_loss = 0.0
    chosen_rewards = []
    rejected_rewards = []
    margins = []
    accuracies = []

    for i in range(n):
        pi_logr_w = policy_chosen_logps[i] - reference_chosen_logps[i]
        pi_logr_l = policy_rejected_logps[i] - reference_rejected_logps[i]

        # Implicit rewards
        r_w = beta * pi_logr_w
        r_l = beta * pi_logr_l
        chosen_rewards.append(r_w)
        rejected_rewards.append(r_l)

        # Logit difference (margin)
        logits = r_w - r_l
        margins.append(logits)
        accuracies.append(1.0 if logits > 0 else 0.0)

        # Numerically stable log-sigmoid: -log(1 / (1 + exp(-logits)))
        # = softplus(-logits)
        if logits >= 0:
            loss_i = math.log1p(math.exp(-logits))
        else:
            loss_i = -logits + math.log1p(math.exp(logits))

        if label_smoothing > 0.0:
            # Conservative DPO with label smoothing
            if -logits >= 0:
                loss_rev = math.log1p(math.exp(logits))
            else:
                loss_rev = logits + math.log1p(math.exp(-logits))
            loss_i = (1.0 - label_smoothing) * loss_i + label_smoothing * loss_rev

        total_loss += loss_i

    avg_loss = total_loss / n
    metrics = {
        "loss": avg_loss,
        "chosen_reward_mean": sum(chosen_rewards) / n,
        "rejected_reward_mean": sum(rejected_rewards) / n,
        "reward_margin_mean": sum(margins) / n,
        "accuracy": sum(accuracies) / n,
    }
    return avg_loss, metrics


def compute_dpo_loss(
    policy_chosen_logps: Any,
    policy_rejected_logps: Any,
    reference_chosen_logps: Any,
    reference_rejected_logps: Any,
    beta: float = 0.1,
    label_smoothing: float = 0.0,
) -> Tuple[Any, Dict[str, float]]:
    """
    PyTorch implementation of DPO loss with automatic CPU/GPU acceleration.
    Falls back to pure numpy if PyTorch tensors are not provided.
    """
    if not HAS_TORCH or not isinstance(policy_chosen_logps, torch.Tensor):
        return dpo_loss_numpy(
            policy_chosen_logps,
            policy_rejected_logps,
            reference_chosen_logps,
            reference_rejected_logps,
            beta=beta,
            label_smoothing=label_smoothing,
        )

    # PyTorch Tensor Execution
    pi_logr_w = policy_chosen_logps - reference_chosen_logps
    pi_logr_l = policy_rejected_logps - reference_rejected_logps

    chosen_rewards = beta * pi_logr_w
    rejected_rewards = beta * pi_logr_l
    logits = chosen_rewards - rejected_rewards

    if label_smoothing > 0.0:
        losses = (
            -F.logsigmoid(logits) * (1.0 - label_smoothing)
            - F.logsigmoid(-logits) * label_smoothing
        )
    else:
        losses = -F.logsigmoid(logits)

    loss = losses.mean()
    chosen_reward_mean = chosen_rewards.detach().mean().item()
    rejected_reward_mean = rejected_rewards.detach().mean().item()
    reward_margin_mean = (chosen_rewards - rejected_rewards).detach().mean().item()
    accuracy = (logits > 0).float().mean().item()

    metrics = {
        "loss": loss.item(),
        "chosen_reward_mean": chosen_reward_mean,
        "rejected_reward_mean": rejected_reward_mean,
        "reward_margin_mean": reward_margin_mean,
        "accuracy": accuracy,
    }
    return loss, metrics

