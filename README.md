# GitHub Fast Downloader

`github-fast-downloader` is a python library for quickly retriving files and directories from GitHub reposities by utilizing git's sparse checkout feature.

## Installation

```bash
pip install github-fast-downloader
```

or

```bash
uv add github-fast-downloader
```

## Usage

### Basic Usage of `GithubFastDownloader`

This example demonstrates how to use  GithubFastDownloader to clone a GitHub repository, perform
sparse checkouts of specific directories, and verify the existence of files and directories after checkouts.

```python
from github_fast_downloader import GithubFastDownloader

# Initialize the GithubFastDownloader with repository information
gfd = GithubFastDownloader("vtr-verilog-to-routing", "verilog-to-routing")
  
# Clone the repository (will be empty at first)
gfd.clone_repo()

# Enable sparse checkout to selectively fetch directories
gfd.enable_sparse_checkout()

# Checkout the "fpu" directory and verify its existence
gfd.checkout_stuff(["vtr_flow/benchmarks/fpu"], reset=False)
assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "fpu").exists()

# Checkout additional directories and files
gfd.checkout_stuff([
    "vtr_flow/benchmarks/blif", 
    "vtr_flow/benchmarks/vexriscv/VexRiscvSmallest.v"
], reset=False)

# Verify the existence of the newly checked out directories and files
assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "blif").exists()
assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "fpu").exists()
assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "vexriscv" / "VexRiscvSmallest.v").exists()

# Reset sparse checkout list
gfd.reset_sparse_checkout_list()

# Checkout only the "fpu" directory again and verify
gfd.checkout_stuff(["vtr_flow/benchmarks/fpu"], reset=False)
assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "fpu").exists()

# Ensure other directories were removed from checkout
assert not (gfd.repo_dir / "vtr_flow" / "benchmarks" / "blif").exists()
assert not (gfd.repo_dir / "vtr_flow" / "benchmarks" / "vexriscv" / "VexRiscvSmallest.v").exists()

# Reset sparse checkout list and clear checkout, by default reset=True for checkout_stuff
# This means that the sparse checkout list will cleared before checking out the new list
# The previous items on the sparse checkout list will also be removed from disk when cleared from the list
gfd.reset_sparse_checkout_list()
gfd.checkout_stuff([])

# Verify only the ".git" directory exists
stuff_in_dir = list(gfd.repo_dir.iterdir())
assert len(stuff_in_dir) == 1
assert stuff_in_dir[0].name == ".git"

# Cleanup resources after usage
gfd.cleanup()
```

### Using `GithubFastDownloader` as a Context Manager

This example demonstrates how to use  GithubFastDownloader as a context manager. This allows
the downloader to automatically handle resource cleanup when the context is exited.

```python
from github_fast_downloader import GithubFastDownloader

# Use the context manager to handle setup and cleanup automatically
with GithubFastDownloader("vtr-verilog-to-routing", "verilog-to-routing") as gfd:
    
    # Checkout the "fpu" directory and verify its existence
    gfd.checkout_stuff(["vtr_flow/benchmarks/fpu"])
    assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "fpu").exists()

    # Checkout additional directories and files
    gfd.checkout_stuff([
        "vtr_flow/benchmarks/blif", 
        "vtr_flow/benchmarks/vexriscv/VexRiscvSmallest.v"
    ], reset=False)

    # Verify the existence of the newly checked out directories and files
    assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "blif").exists()
    assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "fpu").exists()
    assert (gfd.repo_dir / "vtr_flow" / "benchmarks" / "vexriscv" /  "VexRiscvSmallest.v").exists()

    # Reset sparse checkout list and clear checkout
    gfd.reset_sparse_checkout_list()
    gfd.checkout_stuff([])

    # Verify only the ".git" directory exists
    stuff_in_dir = list(gfd.repo_dir.iterdir())
    assert len(stuff_in_dir) == 1
    assert stuff_in_dir[0].name == ".git"
```

## Dev and Testing

If you would like to contribute to the development of this library, you can clone the repository and install the development dependencies.

I have included two simple tests under `tests/`, which are just the two examples above. You can run the tests using the following command:

```bash
pytest
```

or

```bash
uv run pytest
```
