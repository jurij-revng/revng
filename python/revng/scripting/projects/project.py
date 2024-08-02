#
# This file is distributed under the MIT License. See LICENSE.md for details.
#

import os
import shutil
from abc import ABC, abstractmethod
from copy import deepcopy
from tempfile import TemporaryDirectory
from typing import Dict, List

from revng.tupletree import TypedList

from revng.model import Binary, StructBase, get_element_by_path  # type: ignore[attr-defined] # noqa: E501 # isort: skip


class Project(ABC):
    """
    This class is the basis for building a project. It defines
    abstract methods that the inherited classes have to implement
    and it also implements some common methods.
    """

    def __init__(self):
        self.model: Binary = Binary()
        self.last_saved_model: Binary = Binary()
        self.pipeline_description: Dict = {}
        self.input_binary: str
        self.revng_executable: str
        self.resume_dir: str

    @abstractmethod
    def import_binary(self, input_binary: str):
        """
        Use this method to import the binary into the project. This method is a prerequisite
        before running any analyses or getting artifacts.
        """
        pass

    def get_artifact(self, artifact_name: str) -> bytes | str:
        """
        High level method that you can call to fetch an artifact without specifying targets.
        """
        return self._get_artifact(artifact_name)

    @abstractmethod
    def _get_artifact(
        self, artifact_name: str, targets_class: List[StructBase] = []
    ) -> bytes | str:
        """
        Resolves the target logic, performs MIME conversion and dispatches
        the work to the `_get_artifact_internal` to actually get the artifact.
        This method is a more advanced version of `get_artifact` for when you
        want more control of which artifact are processed.
        """
        pass

    @abstractmethod
    def _get_artifact_internal(
        self, artifact_name: str, targets_class: List[str] = []
    ) -> bytes | str:
        """
        The actual implementation of how to fetch the artifacts, eg: call subprocess or gql.
        This is the low-level method that actually calls `revng` and gets the artifact.
        """
        pass

    def get_artifacts(self, params: Dict[str, List[StructBase]]) -> Dict[str, str | bytes]:
        """
        Allows fetching multiple artifacts at once. The `params` is a dict containing
        the name of the artifact and a list of targets (it can be empty to fetch all the
        targets).
        Example `params`:
        params = {
            "disassemble": [Function_1, Function_2],
            "decompile": []
        }
        """
        result: Dict[str, str | bytes] = {}
        for artifact_name, targets in params.items():
            result[artifact_name] = self._get_artifact(artifact_name, targets)

        return result

    @abstractmethod
    def analyze(
        self, analysis_name: str, targets: Dict[str, List[str]], options: Dict[str, str] = {}
    ):
        """
        Run a single analysis. In addition to the `analysis_name` you need to specify a dict
        of targets, some analysis require you to also pass an `options` dict.
        """
        pass

    @abstractmethod
    def analyses_list(self, analysis_name: str):
        """
        Run analysis list, these are predefined list of analysis that run sequentially.
        """
        pass

    @abstractmethod
    def commit(self):
        """
        Persist the changes from `self.model` to the backend.
        """
        pass

    def revert(self):
        """
        Revert changes made to the `self.model` since the last call to `commit()`.
        """
        self._set_model(deepcopy(self.last_saved_model))

    @abstractmethod
    def _get_pipeline_description(self):
        """
        Define how to implement getting the pipeline description data, The method should parse the
        data as `yaml` and store it in the variable `self.pipeline_description`
        """
        pass

    def import_and_analyze(self, input_binary_path: str):
        """
        A helper method for setting up the project. This method imports
        the binary and runs the `revng` initial auto analysis.
        """
        self.import_binary(input_binary_path)
        self.analyses_list("revng-initial-auto-analysis")
        self.analyses_list("revng-c-initial-auto-analysis")
        self._get_pipeline_description()
        self._set_model_mixins()

    def get_analysis_inputs(self, analysis_name: str) -> Dict[str, List[str]]:
        """
        Get the analysis container inputs and the associate acceptable kinds from
        the `pipeline description`.
        """
        inputs: Dict[str, List[str]] = {}
        for step in self.pipeline_description["Steps"]:
            for analysis in step["Analyses"]:
                if analysis["Name"] == analysis_name:
                    for i in analysis["ContainerInputs"]:
                        inputs[i["Name"]] = i["AcceptableKinds"]
        return inputs

    def _set_revng_executable(self, revng_executable_path: str | None) -> str:
        """
        Check if the path of the user supplied or default revng executable
        is present on the system
        """
        if not revng_executable_path:
            revng_executable = shutil.which("revng")
        else:
            revng_executable = revng_executable_path
        assert revng_executable is not None
        assert os.access(revng_executable, os.F_OK | os.X_OK)
        return revng_executable

    def _set_resume_dir(self, resume_dir: str | None) -> str:
        """
        Use the user supplied resume dir or create a temp dir
        """
        if not resume_dir:
            self._tmp_dir = TemporaryDirectory()
            resume_dir = self._tmp_dir.name
        assert os.path.isdir(resume_dir)
        return resume_dir

    def _set_model(self, model: Binary):
        self.model = model
        self.last_saved_model = deepcopy(self.model)
        # We call this method in multiple places. During the initial auto
        # analysis for example we don't have the pipeline description yet
        # so we need to take that into account.
        if self.pipeline_description:
            self._set_model_mixins()

    def _set_model_mixins(self):
        for ct in self.pipeline_description["Ranks"]:
            model_path = ct.get("ModelPath")
            if not model_path:
                continue

            obj = get_element_by_path(model_path, self.model)
            if isinstance(obj, TypedList):
                for elem in obj:
                    elem._project = self
            else:
                obj._project = self

    def _get_artifact_kind(self, step_name: str) -> str:
        for step in self.pipeline_description["Steps"]:
            if step["Name"] == step_name:
                return step["Artifacts"]["Kind"]
        raise RuntimeError(f"Couldn't find step: {step_name}")

    def _get_artifact_container(self, step_name) -> str:
        for step in self.pipeline_description["Steps"]:
            if step["Name"] == step_name:
                return step["Artifacts"]["Container"]
        raise RuntimeError(f"Couldn't find step: {step_name}")

    def _get_step_name(self, analysis_name: str) -> str:
        for step in self.pipeline_description["Steps"]:
            for analysis in step["Analyses"]:
                if analysis["Name"] == analysis_name:
                    return step["Name"]
        raise RuntimeError(f"Couldn't find step for analysis: {analysis_name}")

    def _get_analyses_list_names(self) -> List[str]:
        analyses_names = []
        for analyses in self.pipeline_description["AnalysesLists"]:
            analyses_names.append(analyses["Name"])
        return analyses_names

    def _get_result_mime(self, artifact_name: str, result: str | bytes) -> bytes | str:
        container_mime = ""
        artifact_container = self._get_artifact_container(artifact_name)
        for container in self.pipeline_description["Containers"]:
            if container["Name"] == artifact_container:
                container_mime = container["MIMEType"]

        if not container_mime:
            raise RuntimeError(f"Couldn't find step name {artifact_name}")

        if not container_mime.endswith("tar+gz") and (
            container_mime.startswith("text") or container_mime == "image/svg"
        ):
            assert isinstance(result, bytes)
            return result.decode("utf-8")
        else:
            return result
