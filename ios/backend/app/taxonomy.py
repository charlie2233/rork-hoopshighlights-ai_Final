from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Optional


@dataclass(frozen=True)
class TaxonomyMapping:
    research_label: str
    product_label: str
    canonical_label: str
    event_family: str
    event_subtype: str
    shot_subtype: Optional[str]
    outcome: str
    matched_alias: str
    taxonomy_version: str
    confidence_multiplier: float = 1.0


class BasketballTaxonomy:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._prompt_groups = payload.get("promptGroups") if isinstance(payload.get("promptGroups"), dict) else {}
        self.schema_version = str(payload.get("schemaVersion") or "basketball-detection-taxonomy-v1")
        default_payload = payload.get("default") if isinstance(payload.get("default"), dict) else {}
        self.default = TaxonomyMapping(
            research_label="highlight",
            product_label=str(default_payload.get("productLabel") or "Highlight"),
            canonical_label=str(default_payload.get("canonicalLabel") or "highlight"),
            event_family=str(default_payload.get("eventFamily") or "highlight"),
            event_subtype=str(default_payload.get("eventSubtype") or "generic_highlight"),
            shot_subtype=_optional_string(default_payload.get("shotSubtype")),
            outcome=str(default_payload.get("outcome") or "uncertain"),
            matched_alias="default",
            taxonomy_version=self.schema_version,
            confidence_multiplier=0.94,
        )
        self._mappings_by_key: dict[str, TaxonomyMapping] = {}
        for item in payload.get("labels", []):
            if not isinstance(item, dict):
                continue
            research_label = str(item.get("researchLabel") or "").strip()
            product_label = str(item.get("productLabel") or research_label or self.default.product_label).strip()
            canonical_label = str(item.get("canonicalLabel") or _slug(product_label)).strip()
            if not research_label or not product_label or not canonical_label:
                continue
            mapping = TaxonomyMapping(
                research_label=research_label,
                product_label=product_label,
                canonical_label=canonical_label,
                event_family=str(item.get("eventFamily") or self.default.event_family),
                event_subtype=str(item.get("eventSubtype") or self.default.event_subtype),
                shot_subtype=_optional_string(item.get("shotSubtype")),
                outcome=str(item.get("outcome") or "uncertain"),
                matched_alias=research_label,
                taxonomy_version=self.schema_version,
            )
            for alias in [research_label, *[str(alias) for alias in item.get("aliases", []) if isinstance(alias, str)]]:
                key = _normalize_label(alias)
                if key:
                    self._mappings_by_key[key] = mapping.__class__(**{**mapping.__dict__, "matched_alias": alias})

    def map_label(self, raw_label: str, confidence: float) -> TaxonomyMapping:
        normalized = _normalize_label(raw_label)
        if normalized in self._mappings_by_key:
            return self._mappings_by_key[normalized]

        for key, mapping in self._mappings_by_key.items():
            if key and key in normalized:
                return mapping.__class__(**{**mapping.__dict__, "matched_alias": key, "confidence_multiplier": 0.98})

        return self.default.__class__(
            **{
                **self.default.__dict__,
                "research_label": raw_label.strip() or self.default.research_label,
                "confidence_multiplier": 0.9 if confidence < 0.5 else self.default.confidence_multiplier,
            }
        )

    def prompt_labels(self) -> list[str]:
        labels = {mapping.product_label for mapping in self._mappings_by_key.values()}
        labels.update({mapping.canonical_label.replace("_", " ") for mapping in self._mappings_by_key.values()})
        for values in self._prompt_groups.values():
            if isinstance(values, list):
                labels.update(str(value).strip() for value in values if str(value).strip())
        return sorted(labels)


def load_default_taxonomy() -> BasketballTaxonomy:
    return BasketballTaxonomy(json.loads(_default_taxonomy_path().read_text(encoding="utf-8")))


def _default_taxonomy_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "basketball_taxonomy.json"


def _normalize_label(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _slug(value: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", value.lower())) or "highlight"


def _optional_string(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
