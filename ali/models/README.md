# Models

This directory holds local model artifacts used by ALI modules.

- Place downloaded or trained model files here.
- Keep models small and task-specific where possible.
- Avoid any cloud-only dependencies.

## Model Formats

- Prefer lightweight formats (ONNX, GGUF, or TorchScript).
- Keep metadata in a sidecar JSON/YAML file with:
  - `name`
  - `version`
  - `input_schema`
  - `output_schema`
  - `license`

## Loading Conventions

- Modules should load models lazily on first use.
- Store absolute paths in memory, never hardcode paths.
- Favor CPU-friendly defaults and allow overrides via environment variables:
  - `ALI_MODEL_PATH`
  - `ALI_MODEL_CACHE`

## Default Model

- `google/gemma-3-270m` is used as the default local text model.
- Download it with `python scripts/install_ali.py`.
