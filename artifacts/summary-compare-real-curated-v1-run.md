# Summary / Compare Benchmark

- Benchmark: `summary-compare-real-curated-v1` `1.0.0`
- Dataset Count: `5`
- Item Count: `50`
- Summary Benchmark Score: `0.631198`
- Compare Benchmark Score: `0.0`
- Parallel Workers: `6`
- Judge Failed Count: `1`
- Partial Item Count: `21`

## Per Dataset Scores

- `qmsum-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`not_applicable` partial=`True`
- `multinews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`not_applicable` partial=`True`
- `cocotrip-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`0.0` partial=`False`
- `lcsts-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.645096` partial=`False`
- `cnewsum-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.6173` partial=`True`

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
      "current": 0.0,
      "reference": 0.0,
      "delta": 0.0
    },
    "lcsts-news-summary-curated-pilot-v1": {
      "current": 0.645096,
      "reference": 0.0,
      "delta": 0.645096
    },
    "cnewsum-news-summary-curated-pilot-v1": {
      "current": 0.6173,
      "reference": 0.0,
      "delta": 0.6173
    }
  },
  "task_family": {
    "summary": {
      "current": 0.631198,
      "reference": 0.0,
      "delta": 0.631198
    },
    "compare": {
      "current": 0.0,
      "reference": 0.0,
      "delta": 0.0
    }
  }
}
```