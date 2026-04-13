# Summary / Compare Benchmark

- Benchmark: `summary-compare-real-curated-v1` `1.0.0`
- Dataset Count: `5`
- Item Count: `50`
- Summary Benchmark Score: `0.674332`
- Compare Benchmark Score: `0.0`
- Parallel Workers: `6`
- Judge Failed Count: `26`
- Partial Item Count: `26`

## Per Dataset Scores

- `qmsum-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.732717` partial=`True`
- `multinews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.709233` partial=`True`
- `cocotrip-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`0.0` partial=`True`
- `lcsts-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.64264` partial=`False`
- `cnewsum-news-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.612737` partial=`True`

## Baseline Delta

```json
{
  "per_dataset": {
    "qmsum-query-summary-curated-pilot-v1": {
      "current": 0.732717,
      "reference": 0.0,
      "delta": 0.732717
    },
    "multinews-multi-doc-summary-curated-pilot-v1": {
      "current": 0.709233,
      "reference": 0.0,
      "delta": 0.709233
    },
    "cocotrip-compare-curated-pilot-v1": {
      "current": 0.0,
      "reference": 0.0,
      "delta": 0.0
    },
    "lcsts-news-summary-curated-pilot-v1": {
      "current": 0.64264,
      "reference": 0.0,
      "delta": 0.64264
    },
    "cnewsum-news-summary-curated-pilot-v1": {
      "current": 0.612737,
      "reference": 0.0,
      "delta": 0.612737
    }
  },
  "task_family": {
    "summary": {
      "current": 0.674332,
      "reference": 0.0,
      "delta": 0.674332
    },
    "compare": {
      "current": 0.0,
      "reference": 0.0,
      "delta": 0.0
    }
  }
}
```