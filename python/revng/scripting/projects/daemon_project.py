#
# This file is distributed under the MIT License. See LICENSE.md for details.
#

import json
from typing import Dict, List

import yaml
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

from .project import Project

from revng.model import Binary, Function, dump_diff_to_string, load_model_from_string, make_diff  # type: ignore[attr-defined] # noqa: E501 # isort: skip


class DaemonProject(Project):
    """
    This class is used to run revng analysis and artifact through the
    revng daemon vi GraphQL.
    """

    def __init__(self):
        super().__init__()
        self.transport: AIOHTTPTransport
        self.client: Client

    def setup_client(self, url):
        """
        Setup the `gql` client and connect to the server at the `url`.
        """
        self.transport: AIOHTTPTransport = AIOHTTPTransport(url=f"{url}/graphql/")
        self.client: Client = Client(
            transport=self.transport, fetch_schema_from_transport=True, execute_timeout=None
        )

    def import_binary(self, input_binary_path: str):
        query = gql(
            """
            mutation upload($file: Upload!) {
                uploadFile(file: $file, container: "input")
            }
        """
        )

        with open(input_binary_path, "rb") as binary_file:
            result = self.client.execute(
                query, variable_values={"file": binary_file}, upload_files=True
            )

        if not result["uploadFile"]:
            raise RuntimeError("File upload failed")

    def _get_artifact(self, artifact_name: str, targets_class: List[Function] = []) -> bytes | str:
        if not targets_class:
            targets_class = self.model.Functions
        targets = [tc.key() for tc in targets_class]

        result = self._get_artifact_internal(artifact_name, targets)
        return self._get_result_mime(artifact_name, result)

    def _get_artifact_internal(
        self, artifact_name: str, targets_class: List[str] = []
    ) -> bytes | str:
        query = gql(
            """
            query($step: String!, $paths: String!, $index: BigInt!) {
                produceArtifacts(step: $step, paths: $paths, index: $index) {
                    __typename
                    ... on Produced {
                        result
                    }
                }
            }
        """
        )
        variables = {
            "step": artifact_name,
            "paths": ",".join(targets_class),
            "index": self._get_content_commit_index(),
        }

        response = self.client.execute(query, variable_values=variables)
        assert response["produceArtifacts"]["__typename"] == "Produced"
        return response["produceArtifacts"]["result"].encode()

    def analyze(
        self, analysis_name: str, targets: Dict[str, List[str]], options: Dict[str, str] = {}
    ):
        step = self._get_step_name(analysis_name)

        variables = {
            "step": step,
            "analysis": analysis_name,
            "container": json.dumps(targets),
            "options": json.dumps(options),
            "index": self._get_content_commit_index(),
        }

        query = gql(
            """
            mutation($step: String!, $analysis: String!, $container: String!,
                $options: String!, $index: BigInt!)
            {
                runAnalysis(step: $step, analysis: $analysis, options: $options,
                    containerToTargets: $container, index: $index)
                {
                    __typename
                }
            }
        """
        )

        response = self.client.execute(query, variable_values=variables)
        assert response["runAnalysis"]["__typename"] == "Diff"
        self._set_model(self._get_model())

    def analyses_list(self, analysis_name: str):
        query = gql(
            """
            mutation($analysis: String!, $index: BigInt!) {
                runAnalysesList(name: $analysis, index: $index) {
                    __typename
                }
            }
        """
        )
        variables = {"analysis": analysis_name, "index": self._get_content_commit_index()}

        response = self.client.execute(query, variable_values=variables)
        assert response["runAnalysesList"]["__typename"] == "Diff"
        self._set_model(self._get_model())

    def commit(self):
        diff = make_diff(self.last_saved_model, self.model)
        if len(diff.changes) == 0:
            return

        diff_yaml = dump_diff_to_string(diff)

        query = gql(
            """
            mutation ($options: String!, $index: BigInt!) {
                runAnalysis(step: "initial", analysis: "apply-diff", index: $index,
                options: $options) {
                    __typename
                    ... on Diff {
                        diff
                    }
                }
            }
        """
        )
        variables = {
            "options": json.dumps(
                {"apply-diff-global-name": "model.yml", "apply-diff-diff-content": diff_yaml}
            ),
            "index": self._get_content_commit_index(),
        }

        response = self.client.execute(query, variable_values=variables)
        assert response["runAnalysis"]["__typename"] == "Diff"
        self.last_saved_model = self._get_model()

    def _get_pipeline_description(self):
        query = gql("{ pipelineDescription }")

        response = self.client.execute(query)
        self.pipeline_description = yaml.safe_load((response["pipelineDescription"]))

    def _get_model(self) -> Binary:
        query = gql("""{ getGlobal(name: "model.yml") }""")

        response = self.client.execute(query)
        return load_model_from_string(response["getGlobal"])

    def _get_content_commit_index(self) -> int:
        # TODO: Keep track of the commit index with websockets
        query = gql("{ contextCommitIndex }")

        response = self.client.execute(query)
        return int(response["contextCommitIndex"])
