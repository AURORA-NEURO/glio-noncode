"""Small benchmark harness emphasizing calibration and abstention behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import CaseManifest, Dossier
from .runtime import CaseRuntime


@dataclass(frozen=True, slots=True)
class BenchmarkExample:
    example_id: str
    manifest: CaseManifest
    expected_element_id: str | None
    expected_gene_id: str | None
    max_review_candidates: int = 3


@dataclass(frozen=True, slots=True)
class ExampleResult:
    example_id: str
    top_element_id: str
    top_gene_id: str
    top_support: float
    top_uncertainty: float
    element_match: bool
    gene_match: bool
    abstained: bool
    candidate_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "example_id": self.example_id,
            "top_element_id": self.top_element_id,
            "top_gene_id": self.top_gene_id,
            "top_support": self.top_support,
            "top_uncertainty": self.top_uncertainty,
            "element_match": self.element_match,
            "gene_match": self.gene_match,
            "abstained": self.abstained,
            "candidate_count": self.candidate_count,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    name: str
    examples: tuple[ExampleResult, ...]
    element_precision_at_one: float
    gene_precision_at_one: float
    abstention_rate: float
    mean_uncertainty: float
    review_burden: float

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "examples": [item.to_dict() for item in self.examples],
            "element_precision_at_one": self.element_precision_at_one,
            "gene_precision_at_one": self.gene_precision_at_one,
            "abstention_rate": self.abstention_rate,
            "mean_uncertainty": self.mean_uncertainty,
            "review_burden": self.review_burden,
        }


class BenchmarkRunner:
    """Evaluate exact supported workflows without treating metrics as validation."""

    def run(self, name: str, examples: Iterable[BenchmarkExample], *, data_root: str = ".glio-benchmark") -> BenchmarkReport:
        results: list[ExampleResult] = []
        for example in examples:
            dossier = CaseRuntime(data_root).evaluate(example.manifest)
            results.append(self._score(example, dossier))
        total = max(1, len(results))
        return BenchmarkReport(
            name=name,
            examples=tuple(results),
            element_precision_at_one=round(sum(item.element_match for item in results) / total, 6),
            gene_precision_at_one=round(sum(item.gene_match for item in results) / total, 6),
            abstention_rate=round(sum(item.abstained for item in results) / total, 6),
            mean_uncertainty=round(sum(item.top_uncertainty for item in results) / total, 6),
            review_burden=round(sum(item.candidate_count for item in results) / total, 6),
        )

    @staticmethod
    def _score(example: BenchmarkExample, dossier: Dossier) -> ExampleResult:
        top = dossier.hypotheses[0]
        return ExampleResult(
            example_id=example.example_id,
            top_element_id=top.element_id,
            top_gene_id=top.gene_id,
            top_support=top.support,
            top_uncertainty=top.uncertainty,
            element_match=example.expected_element_id is None or top.element_id == example.expected_element_id,
            gene_match=example.expected_gene_id is None or top.gene_id == example.expected_gene_id,
            abstained=top.support == 0.0 or top.element_id == "unresolved",
            candidate_count=min(len(dossier.hypotheses), example.max_review_candidates),
        )
