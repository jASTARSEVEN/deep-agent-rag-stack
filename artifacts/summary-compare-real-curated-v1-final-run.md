# Summary / Compare Benchmark

- Benchmark: `summary-compare-real-curated-v1` `1.0.0`
- Dataset Count: `5`
- Item Count: `50`
- Summary Benchmark Score: `0.675264`
- Compare Benchmark Score: `0.1`
- Parallel Workers: `6`
- Judge Failed Count: `7`
- Partial Item Count: `7`

## Per Dataset Scores

- `qmsum-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.729926` partial=`False`
- `multinews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.708835` partial=`True`
- `cocotrip-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`0.1` partial=`True`
- `lcsts-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.645837` partial=`False`
- `cnewsum-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.616456` partial=`True`

## Baseline Delta

```json
{
  "per_dataset": {
    "qmsum-query-summary-curated-pilot-v1": {
      "current": 0.729926,
      "reference": 0.0,
      "delta": 0.729926
    },
    "multinews-multi-doc-summary-curated-pilot-v1": {
      "current": 0.708835,
      "reference": 0.0,
      "delta": 0.708835
    },
    "cocotrip-compare-curated-pilot-v1": {
      "current": 0.1,
      "reference": 0.0,
      "delta": 0.1
    },
    "lcsts-news-summary-curated-pilot-v1": {
      "current": 0.645837,
      "reference": 0.0,
      "delta": 0.645837
    },
    "cnewsum-news-summary-curated-pilot-v1": {
      "current": 0.616456,
      "reference": 0.0,
      "delta": 0.616456
    }
  },
  "task_family": {
    "summary": {
      "current": 0.675264,
      "reference": 0.0,
      "delta": 0.675264
    },
    "compare": {
      "current": 0.1,
      "reference": 0.0,
      "delta": 0.1
    }
  }
}
```