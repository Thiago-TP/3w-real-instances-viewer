# Examples of what the viewer reads and writes

Every file format the viewer exchanges with the outside ships with one example here, and every
example says where it came from: what produced it, with which command and which choice, on which
dataset version, when. A file whose provenance is not written down is not an example.

## Toolkit file lists

The 3W Toolkit loads a dataset through `ParquetDatasetConfig`
(`ThreeWToolkit.dataset.parquet_dataset`); with `split="list"` it loads exactly the files named in
`file_list`, each a path relative to the dataset root such as `4/WELL-00014_20170918230000.parquet`.
The viewer writes the instances a page has on show in that form (*Export file list…* in the main
toolbar), and `scripts/export_file_list.py` writes the same from the command line, for a choice made
by fault class and by well. Both write two files: the configuration, holding the Toolkit's own
fields and nothing else so that it loads unchanged, and `<name>.provenance.json` beside it.

Load one with:

```python
import json
from ThreeWToolkit.dataset.parquet_dataset import ParquetDataset, ParquetDatasetConfig

config = ParquetDatasetConfig(**json.load(open("examples/file_list_severe_slugging_well14.json")))
dataset = ParquetDataset(config)
```

The `path` field is the dataset root the list was written against; point it at your own copy.

| File | What it lists | Produced by |
| ---- | ------------- | ----------- |
| `file_list_severe_slugging_well14.json` | the real instances of Severe Slugging (class 4) recorded on WELL-00014 in 3W 2.0.0 | `python scripts/export_file_list.py --raw-dir ../3W/dataset --fault 4 --well 14 -o examples/file_list_severe_slugging_well14.json` |

Its `.provenance.json` carries the dataset version, the count and the timestamp of the run.

## Model outputs

The viewer draws a model's verdicts onto the data when they come in its model-output format
(`src/overlap_viewer/backend/model_outputs.py`, and the *Model outputs* tab of the help): a folder
holding `model.json` — the model's `name`, its `kind` (`detection` or `classification`), the meaning
of its `labels`, a `description` and its `provenance` — beside one `<fault_class>/<instance>.parquet`
per instance scored, each indexed by `timestamp` with an integer `label` column and an optional
float `score`. *Load model outputs…* in the main toolbar opens such a folder.

| Folder | What it holds | Produced by |
| ------ | ------------- | ----------- |
| `model_outputs/pca_control_chart_well7/` | a PCA control chart over the 12 real instances of WELL-00007 in 3W 2.0.0: one model fitted on the well's 2 Normal Operation instances (21,570 samples, 10 analog sensors live in both, 6 components for 90 % of the variance), Hotelling's T² and Q followed along every instance, a sample labeled `1` (anomalous) beyond the 99th percentile of either statistic over the training samples, the `score` the larger of the two ratios to their limits | `python scripts/pca_control_chart.py --raw-dir ../3W/dataset --well 7 --fit well -o examples/model_outputs/pca_control_chart_well7` |

Its `model.json` carries the command, the parameters, the fitted limits per well and the timestamp of
the run. Against the experts' labels it agrees 98 % of the compared time on the two normal instances
and 100 % on the ten severe-slugging ones. The script scores any choice of wells and faults the same
way, per well or (`--fit instance`) per instance on its own normal stretch; it is one producer of the
format among many, and the model is not part of the viewer.

## What cannot come back from the Toolkit

The Toolkit's `ModelAssessment` exports `predictions_<timestamp>.csv` with the columns
`true_values`, `predictions`, `model_name`, `task_type` and `timestamp`: one row per window the
model scored, in the order the windows were fed. Nothing in that file says which instance, let alone
which second, a prediction belongs to, so the viewer cannot draw it back onto the data, and no
example of it is kept here. The model-output format above is what such an export would have to
carry: the instance's file and the timestamp of every label.
