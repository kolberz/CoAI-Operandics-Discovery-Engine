# Contributing to CoAI Operandics Discovery Engine

First off, thank you for considering contributing to the CoAI Operandics Discovery Engine! We welcome all contributions, from bug fixes to new theoretical extensions in the Lean 4 formalization.

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+**: For the core python algorithms and orchestration.
- **Lean 4**: Recommended to install via `elan`.

### 2. Local Setup

1. Fork the repository and clone your fork locally.
2. Set up a Python environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt # (if present, otherwise install pytest, numpy, scipy, sympy)
   ```

3. Ensure Lean 4 is working:

   ```bash
   cd coai_project_experimental
   lake build
   ```

### 3. Making Changes

- **Python**: Ensure your code is thoroughly tested in the `tests/` directory. If introducing new heuristics, ensure `baseline_experiment.py` completes without failure.
- **Lean 4**: Any new formalizations should be placed inside the `coai_project_experimental/coai/` structure. Be sure to run `lake build` to formally verify all proofs before submitting a pull request.

## 📝 Submitting a Pull Request

1. Create a feature branch: `git checkout -b feature-name`
2. Commit your changes with clear, descriptive messages.
3. Push your branch and open a Pull Request against the `master` branch.
4. Ensure the GitHub Actions CI pipelines pass (Python Tests, Lean Compilation, LaTeX Build).

We appreciate your time and effort in making this engine better!
