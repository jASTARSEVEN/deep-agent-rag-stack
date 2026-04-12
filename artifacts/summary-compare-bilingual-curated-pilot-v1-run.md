# Summary / Compare Benchmark

- Benchmark: `summary-compare-bilingual-curated-pilot-v1` `1.0.0`
- Dataset Count: `6`
- Item Count: `6`
- Summary Benchmark Score: `not_applicable`
- Compare Benchmark Score: `1.0`
- Parallel Workers: `6`
- Judge Failed Count: `0`
- Partial Item Count: `4`

## Per Dataset Scores

- `qmsum-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`not_applicable` partial=`True`
- `multinews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`not_applicable` partial=`True`
- `cocotrip-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`1.0` partial=`False`
- `drcd-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`not_applicable` partial=`True`
- `ttnews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`not_applicable` partial=`True`
- `zh-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`1.0` partial=`False`

## Baseline Delta

```json
{
  "per_dataset": {
    "qmsum-query-summary-curated-pilot-v1": {
      "current": null,
      "reference": 0.0,
      "delta": null
    },
    "multinews-multi-doc-summary-curated-pilot-v1": {
      "current": null,
      "reference": 0.0,
      "delta": null
    },
    "cocotrip-compare-curated-pilot-v1": {
      "current": 1.0,
      "reference": 0.0,
      "delta": 1.0
    },
    "drcd-query-summary-curated-pilot-v1": {
      "current": null,
      "reference": 0.0,
      "delta": null
    },
    "ttnews-multi-doc-summary-curated-pilot-v1": {
      "current": null,
      "reference": 0.0,
      "delta": null
    },
    "zh-compare-curated-pilot-v1": {
      "current": 1.0,
      "reference": 0.0,
      "delta": 1.0
    }
  },
  "task_family": {
    "summary": {
      "current": null,
      "reference": null,
      "delta": null
    },
    "compare": {
      "current": 1.0,
      "reference": 0.0,
      "delta": 1.0
    }
  }
}
```