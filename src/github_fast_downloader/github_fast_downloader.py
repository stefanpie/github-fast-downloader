import atexit
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class GithubFastDownloader:
    """A class for efficiently downloading specific files and directories from GitHub repositories.

    This class uses git's sparse checkout feature to selectively download only the files
    and directories you need from a GitHub repository, rather than cloning the entire repository.

    Attributes:
        repo_name: The name of the GitHub repository.
        repo_owner: The owner (user or organization) of the GitHub repository.
        repo_url: The full HTTPS URL to the git repository.
        repo_branch: The branch to checkout (defaults to repository's default branch).
        git_bin: Path to the git binary executable.
        temp_dir: Temporary directory object for storing the repository.
        repo_dir: Path to the cloned repository within the temporary directory.
    """

    def __init__(
        self,
        repo_name: str,
        repo_owner: str,
        repo_branch: str | None = None,
        git_bin: str | None = "git",
    ) -> None:
        """Initialize the GithubFastDownloader.

        Args:
            repo_name: The name of the GitHub repository.
            repo_owner: The owner (user or organization) of the repository.
            repo_branch: The branch to checkout. If None, uses the repository's default branch.
            git_bin: Path to git binary. If None, searches for 'git' in PATH.

        Raises:
            ValueError: If git_bin is None and git cannot be found in PATH.
        """
        if git_bin is None:
            git_bin_match = shutil.which("git")
            if git_bin_match is None:
                raise ValueError("git binary not found in PATH")
            self.git_bin = git_bin_match
        else:
            self.git_bin = git_bin

        self.repo_name = repo_name
        self.repo_owner = repo_owner
        self.repo_url = f"https://github.com/{self.repo_owner}/{self.repo_name}.git"
        self.repo_branch = repo_branch
        self.temp_dir = tempfile.TemporaryDirectory(prefix="github_fast_downloader__")
        self.repo_dir = Path(self.temp_dir.name) / "repo"
        self._cleaned_up = False

        # Register the cleanup function for various terminations
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)

    def clone_repo(self) -> None:
        """Clone the GitHub repository with sparse checkout enabled.

        This performs a shallow clone (depth=1) without checking out files initially,
        and uses blob filtering to minimize data transfer.

        Raises:
            RuntimeError: If the git clone operation fails.
        """
        if not self.repo_branch:
            self.repo_branch = self.get_default_branch()

        try:
            # Shallow clone the repository (depth=1)
            subprocess.run(
                [
                    self.git_bin,
                    "clone",
                    "--depth",
                    "1",  # shallow clone (only latest commit)
                    "--branch",
                    self.repo_branch,
                    "--no-checkout",  # don't check out files initially
                    "--filter=blob:none",  # Don't fetch file data
                    self.repo_url,
                    str(self.repo_dir),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to clone repository {self.repo_url} (branch: {self.repo_branch}): {e.stderr}"
            ) from e

    def get_default_branch(self) -> str:
        """Retrieve the default branch name for the repository.

        Returns:
            The name of the default branch (e.g., 'main', 'master').

        Raises:
            RuntimeError: If unable to query the repository or parse the default branch.
        """
        try:
            result = subprocess.run(
                [
                    self.git_bin,
                    "ls-remote",
                    "--symref",
                    self.repo_url,
                    "HEAD",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            for line in result.stdout.splitlines():
                if line.startswith("ref:"):
                    branch = line.split()[1].split("/")[-1]
                    return branch
            raise RuntimeError(
                f"Unable to detect the default branch for {self.repo_url}. "
                "The repository may not exist or may not be accessible."
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to query default branch for {self.repo_url}: {e.stderr}"
            ) from e

    def enable_sparse_checkout(self) -> None:
        """Enable sparse checkout for the repository.

        This configures git to only checkout files that are explicitly specified
        in the sparse-checkout configuration.

        Raises:
            RuntimeError: If the git config operation fails.
        """
        try:
            subprocess.run(
                [
                    self.git_bin,
                    "-C",
                    str(self.repo_dir),
                    "config",
                    "core.sparseCheckout",
                    "true",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to enable sparse checkout: {e.stderr}") from e

    def checkout_stuff(self, files_or_dirs: list[str], reset: bool = True) -> None:
        """Checkout specific files or directories from the repository.

        Args:
            files_or_dirs: List of file or directory paths to checkout, relative to repository root.
            reset: If True, clears the sparse-checkout list before adding new items.
                   If False, appends to the existing sparse-checkout list.

        Raises:
            RuntimeError: If the git checkout operation fails.
            IOError: If unable to write to the sparse-checkout configuration file.
        """
        sparse_checkout_file = Path(self.repo_dir) / ".git" / "info" / "sparse-checkout"

        try:
            mode = "w" if reset else "a"
            with sparse_checkout_file.open(mode, encoding="utf-8") as f:
                for item in files_or_dirs:
                    f.write(f"{item}\n")
        except IOError as e:
            raise IOError(f"Failed to write sparse-checkout configuration: {e}") from e

        try:
            subprocess.run(
                [self.git_bin, "-C", str(self.repo_dir), "checkout"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to checkout files/directories: {e.stderr}"
            ) from e

    def reset_sparse_checkout_list(self) -> None:
        """Clear the sparse-checkout configuration file.

        This removes all entries from the sparse-checkout list, which will cause
        subsequent checkouts to remove previously checked out files.

        Raises:
            IOError: If unable to write to the sparse-checkout configuration file.
        """
        sparse_checkout_file = Path(self.repo_dir) / ".git" / "info" / "sparse-checkout"
        try:
            sparse_checkout_file.write_text("", encoding="utf-8")
        except IOError as e:
            raise IOError(f"Failed to reset sparse-checkout configuration: {e}") from e

    def get_path_on_disk(self, item_path: str) -> Path:
        """Get the absolute path on disk for a file or directory in the repository.

        Args:
            item_path: The relative path to the file or directory within the repository.

        Returns:
            The absolute Path object pointing to the item on disk.

        Raises:
            ValueError: If the repository directory doesn't exist or the item hasn't been checked out.
        """
        if not self.repo_dir.exists():
            raise ValueError("Repository directory does not exist")
        full_path = self.repo_dir / item_path
        if not full_path.exists():
            raise ValueError(
                f"File or directory '{item_path}' does not exist in the repository. "
                "Make sure it has been checked out using checkout_stuff()."
            )
        return full_path

    def signal_handler(self, _signum: int, _frame: Any) -> None:
        """Handle interrupt signals (e.g., Ctrl+C) by cleaning up and exiting.

        Args:
            _signum: The signal number.
            _frame: The current stack frame.
        """
        self.cleanup()
        sys.exit(0)

    def cleanup(self) -> None:
        """Clean up the temporary directory containing the cloned repository.

        This method is safe to call multiple times; subsequent calls after the first
        cleanup will have no effect.
        """
        if not self._cleaned_up:
            try:
                self.temp_dir.cleanup()
                self._cleaned_up = True
            except Exception:
                # Ignore cleanup errors to prevent issues during shutdown
                pass

    def __del__(self) -> None:
        """Destructor that ensures cleanup when the object is garbage collected."""
        self.cleanup()

    def __enter__(self) -> "GithubFastDownloader":
        """Enter the context manager, cloning the repository and enabling sparse checkout.

        Returns:
            The GithubFastDownloader instance.
        """
        self.clone_repo()
        self.enable_sparse_checkout()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the context manager, cleaning up the temporary directory.

        Args:
            exc_type: The type of exception that occurred, if any.
            exc_val: The exception instance that occurred, if any.
            exc_tb: The traceback object, if any.
        """
        self.cleanup()
