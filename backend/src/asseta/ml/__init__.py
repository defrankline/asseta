"""Pure-Python ML core for governed anomaly detection (ADR-007). No database, no web framework.

Import from the submodules (`asseta.ml.features`, `.datasets`, `.models`, `.baseline`, `.evaluation`, `.drift`,
`.tracking`, `.training`, `.synthetic`); this package root deliberately imports nothing heavy so that importing
`asseta.ml.features` from a request path does not load scikit-learn or MLflow.
"""
