# Supplemental financial table evaluation

Eight supplemental financial allocation table questions; not included in the primary 32-query result. Requires both the tax amount and the control total from the designated order document.

| Configuration | Evidence recall@6 |
|---|---:|
| fixed | 1.000 |
| fixed_cross_encoder | 1.000 |
| structure | 1.000 |
| structure_cross_encoder | 1.000 |

This conservative source-specific probe can expose confusion between similarly worded allocation tables in order, payment, approval, and refund documents. It measures evidence retrieval, not generated arithmetic accuracy.
