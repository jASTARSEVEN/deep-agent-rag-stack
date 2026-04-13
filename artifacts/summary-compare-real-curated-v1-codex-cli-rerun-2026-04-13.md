# Summary / Compare Benchmark

- Benchmark: `summary-compare-real-curated-v1` `1.0.0`
- Dataset Count: `5`
- Item Count: `50`
- Summary Benchmark Score: `0.672915`
- Compare Benchmark Score: `0.0`
- Parallel Workers: `1`
- Judge Failed Count: `0`
- Partial Item Count: `0`

## Per Dataset Scores

- `qmsum-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.729493` partial=`False`
- `multinews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.709775` partial=`False`
- `cocotrip-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`0.0` partial=`False`
- `lcsts-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.64238` partial=`False`
- `cnewsum-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.610011` partial=`False`

## Baseline Delta

```json
{
  "per_dataset": {
    "qmsum-query-summary-curated-pilot-v1": {
      "current": 0.729493,
      "reference": 0.0,
      "delta": 0.729493
    },
    "multinews-multi-doc-summary-curated-pilot-v1": {
      "current": 0.709775,
      "reference": 0.0,
      "delta": 0.709775
    },
    "cocotrip-compare-curated-pilot-v1": {
      "current": 0.0,
      "reference": 0.0,
      "delta": 0.0
    },
    "lcsts-news-summary-curated-pilot-v1": {
      "current": 0.64238,
      "reference": 0.0,
      "delta": 0.64238
    },
    "cnewsum-news-summary-curated-pilot-v1": {
      "current": 0.610011,
      "reference": 0.0,
      "delta": 0.610011
    }
  },
  "task_family": {
    "summary": {
      "current": 0.672915,
      "reference": 0.0,
      "delta": 0.672915
    },
    "compare": {
      "current": 0.0,
      "reference": 0.0,
      "delta": 0.0
    }
  }
}
```