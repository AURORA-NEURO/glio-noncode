"""Deterministic replay helpers."""

from .validation_beta_frontier_governance import ValidationBetaFrontierReplayReceipt, replay_validation_beta_frontier


def validation_beta_frontier_replay_is_deterministic(receipt: ValidationBetaFrontierReplayReceipt) -> bool:
    return receipt.deterministic and receipt.original_address == receipt.replay_address


__all__ = ["ValidationBetaFrontierReplayReceipt", "replay_validation_beta_frontier", "validation_beta_frontier_replay_is_deterministic"]
