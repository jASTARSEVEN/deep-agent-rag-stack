# Summary / Compare Benchmark

- Benchmark: `summary-compare-bilingual-curated-pilot-v1` `1.0.0`
- Dataset Count: `6`
- Item Count: `6`
- Summary Benchmark Score: `0.764864`
- Compare Benchmark Score: `1.0`
- Parallel Workers: `6`
- Judge Failed Count: `0`
- Partial Item Count: `0`

## Per Dataset Scores

- `qmsum-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.753233` partial=`False`
- `multinews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.727891` partial=`False`
- `cocotrip-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`1.0` partial=`False`
- `drcd-query-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.846113` partial=`False`
- `ttnews-multi-doc-summary-curated-pilot-v1`: metric=`bert_score_f1` value=`0.732217` partial=`False`
- `zh-compare-curated-pilot-v1`: metric=`pairwise_rubric_judge_win_rate` value=`1.0` partial=`False`

## Baseline Delta

```json
{
  "per_dataset": {
    "qmsum-query-summary-curated-pilot-v1": {
      "current": 0.753233,
      "reference": 0.0,
      "delta": 0.753233
    },
    "multinews-multi-doc-summary-curated-pilot-v1": {
      "current": 0.727891,
      "reference": 0.0,
      "delta": 0.727891
    },
    "cocotrip-compare-curated-pilot-v1": {
      "current": 1.0,
      "reference": 0.0,
      "delta": 1.0
    },
    "drcd-query-summary-curated-pilot-v1": {
      "current": 0.846113,
      "reference": 0.0,
      "delta": 0.846113
    },
    "ttnews-multi-doc-summary-curated-pilot-v1": {
      "current": 0.732217,
      "reference": 0.0,
      "delta": 0.732217
    },
    "zh-compare-curated-pilot-v1": {
      "current": 1.0,
      "reference": 0.0,
      "delta": 1.0
    }
  },
  "task_family": {
    "summary": {
      "current": 0.764864,
      "reference": 0.0,
      "delta": 0.764864
    },
    "compare": {
      "current": 1.0,
      "reference": 0.0,
      "delta": 1.0
    }
  }
}
```