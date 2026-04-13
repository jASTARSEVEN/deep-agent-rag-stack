# summary-compare-real-curated-v1

This suite contains only packages extracted from real external datasets.

Each package records upstream source, split, row index, and original example id so the benchmark can be independently reconstructed.

This suite is the current tuning and observability lane for summary/compare work.

It is not the product gate. `phase8a-summary-compare-v1` remains the only product gate dataset.

Current baseline usage rule:

- use the package-level consolidated baseline as the suite's current baseline
- do not replace that baseline with a newly generated aggregate artifact unless the docs explicitly promote it
