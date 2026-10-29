"""
Unit tests for Direct Preference Optimization (DPO) with LoRA module in VeriSight.
"""

import json
from pathlib import Path
import pytest

from verisight.dpo.dpo_loss import dpo_loss_numpy, compute_dpo_loss
from verisight.dpo.preference_miner import VerificationPreferenceMiner
from verisight.dpo.dpo_trainer import (
    validate_preference_dataset,
    run_dry_run_validation,
    train_dpo_lora,
)
from verisight.config import get_config, DPOConfig


def test_dpo_loss_mathematical_properties():
    """Verify DPO loss behaves monotonically and accurately aligns with Bradley-Terry preferences."""
    # Scenario: Policy assigns higher probability to chosen than rejected
    policy_chosen = [-10.0, -8.0]
    policy_rejected = [-15.0, -14.0]
    ref_chosen = [-12.0, -12.0]
    ref_rejected = [-12.0, -12.0]

    loss, metrics = dpo_loss_numpy(
        policy_chosen,
        policy_rejected,
        ref_chosen,
        ref_rejected,
        beta=0.1,
    )

    # Since policy preferred chosen over rejected relative to ref, implicit reward margin must be positive
    assert metrics["chosen_reward_mean"] > metrics["rejected_reward_mean"]
    assert metrics["reward_margin_mean"] > 0.0
    assert metrics["accuracy"] == 1.0
    assert loss > 0.0


def test_dpo_loss_label_smoothing():
    """Verify label smoothing regularizes loss."""
    policy_chosen = [-10.0]
    policy_rejected = [-15.0]
    ref_chosen = [-12.0]
    ref_rejected = [-12.0]

    loss_plain, _ = dpo_loss_numpy(policy_chosen, policy_rejected, ref_chosen, ref_rejected, beta=0.1, label_smoothing=0.0)
    loss_smooth, _ = dpo_loss_numpy(policy_chosen, policy_rejected, ref_chosen, ref_rejected, beta=0.1, label_smoothing=0.1)

    assert loss_smooth != loss_plain
    assert loss_smooth > 0.0


def test_preference_dataset_schema():
    """Verify the golden preference dataset has valid prompts, chosen responses, and rejected responses."""
    dataset_path = Path("data/preferences/workflow2_dpo.jsonl")
    assert dataset_path.exists(), "Dataset file data/preferences/workflow2_dpo.jsonl must exist"

    results = validate_preference_dataset(dataset_path)
    assert results["valid_count"] >= 5, f"Expected at least 5 preference pairs, got {results['valid_count']}"
    assert results["error_count"] == 0, f"Found errors in preference dataset: {results['errors']}"


def test_preference_miner_syntax_evaluation(tmp_path):
    """Test automated compiler/syntax oracle for choosing valid SVA over broken SVA."""
    miner = VerificationPreferenceMiner(preference_path=tmp_path / "test_prefs.jsonl")

    # Valid SVA property
    valid_sva = (
        "property p_test;\n"
        "  @(posedge clk)\n"
        "  disable iff (!rst_n)\n"
        "  psel |=> penable;\n"
        "endproperty\n"
        "assert property (p_test);"
    )

    # Broken SVA property with unbalanced parens and illegal syntax
    broken_sva = "property p_test; @(posedge clk) psel |-> (penable; endproperty"

    pair = miner.evaluate_and_mine_candidates(
        prompt="Generate APB assertion",
        candidate_a=valid_sva,
        candidate_b=broken_sva,
        category="sva_test",
        feature_id="TEST_REQ_001",
    )

    assert pair is not None
    assert pair["chosen"] == valid_sva.strip()
    assert pair["rejected"] == broken_sva.strip()

    stats = miner.get_statistics()
    assert stats["total_pairs"] == 1
    assert stats["categories"]["sva_test"] == 1


def test_dpo_dry_run_and_adapter_export(tmp_path):
    """Test dry-run training loop and adapter metadata generation."""
    dataset_path = Path("data/preferences/workflow2_dpo.jsonl")
    output_dir = tmp_path / "dpo_adapter"

    summary = train_dpo_lora(
        base_model_name="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
        dataset_path=dataset_path,
        output_dir=output_dir,
        lora_r=8,
        lora_alpha=16,
        beta=0.1,
        dry_run=True,
    )

    assert summary["status"] == "dry_run_verified"
    assert (output_dir / "adapter_config.json").exists()

    with open(output_dir / "adapter_config.json") as f:
        data = json.load(f)
        assert data["lora_r"] == 8
        assert data["beta"] == 0.1
        assert "metrics" in data


def test_config_dpo_integration():
    """Verify DPOConfig is integrated into global VeriSightConfig."""
    cfg = get_config()
    assert hasattr(cfg, "dpo")
    assert isinstance(cfg.dpo, DPOConfig)
    assert cfg.dpo.beta == 0.1
    assert cfg.dpo.lora_r == 16
