#
# This file is distributed under the MIT License. See LICENSE.md for details.
#

import subprocess
from tempfile import NamedTemporaryFile
from typing import List

import yaml

from .project import Project

from revng.model import Function, dump_diff, load_model_from_string, make_diff  # type: ignore[attr-defined] # noqa: E501 # isort:skip


class CLIProject(Project):
    """
    This class is used to run revng analysis and artifact through
    the CLI with subprocess.
    """

    def __init__(self, resume_dir: str | None = None, revng_executable: str | None = None):
        super().__init__()
        self.resume_dir = self._set_resume_dir(resume_dir)
        self.revng_executable = self._set_revng_executable(revng_executable)

    def import_binary(self, input_binary_path: str):
        self.input_binary = input_binary_path

    def _get_artifact(self, artifact_name: str, targets_class: List[Function] = []) -> bytes | str:
        targets = []
        if targets_class:
            kind = self._get_artifact_kind(artifact_name)
            targets.extend([f"{tc.key()}:{kind}" for tc in targets_class])

        result = self._get_artifact_internal(artifact_name, targets)
        return self._get_result_mime(artifact_name, result)

    def _get_artifact_internal(self, artifact_name: str, targets: List[str] = []) -> bytes | str:
        args = [
            self.revng_executable,
            "artifact",
            f"--resume={self.resume_dir}",
            artifact_name,
            self.input_binary,
        ]
        args.extend(targets)

        return subprocess.run(args, capture_output=True, check=True).stdout

    def analyze(self, analysis_name: str, targets={}, options={}):
        # TODO: add `targets` when `revng`` allows it
        args = [self.revng_executable, "analyze", f"--resume={self.resume_dir}", analysis_name]
        if options:
            for name, value in options.items():
                args.append(f"--{analysis_name}-{name}={value}")
        args.append(self.input_binary)

        result = subprocess.run(args, capture_output=True, check=True).stdout
        model = load_model_from_string(result.decode("utf-8"))
        self._set_model(model)

    def analyses_list(self, analysis_name: str):
        return self.analyze(analysis_name)

    def commit(self):
        diff = make_diff(self.last_saved_model, self.model)
        if len(diff.changes) == 0:
            return

        with NamedTemporaryFile(mode="w") as tmp_diff_file:
            dump_diff(tmp_diff_file.name, diff)

            args = [
                self.revng_executable,
                "analyze",
                f"--resume={self.resume_dir}",
                "apply-diff",
                "--apply-diff-global-name=model.yml",
                f"--apply-diff-diff-content-path={tmp_diff_file.name}",
                self.input_binary,
            ]

            model = subprocess.run(args, capture_output=True, check=True).stdout
            self.last_saved_model = load_model_from_string(model.decode("utf-8"))

    def _get_pipeline_description(self):
        with open(f"{self.resume_dir}/pipeline-description.yml") as pd:
            self.pipeline_description = yaml.safe_load(pd)
