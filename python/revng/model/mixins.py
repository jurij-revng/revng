#
# This file is distributed under the MIT License. See LICENSE.md for details.
#


class AllMixin:
    """
    Base mixin for all the objects in the `Binary` that don support getting the artifacts.
    """

    _project = None


class BinaryMixin(AllMixin):
    """
    Mixin used to reference the `Project` class from the `Binary` class.
    """

    def get_artifact(self, artifact_name: str) -> bytes | str:
        """
        Fetch the artifacts form the `Binary`.
        """
        return self._project._get_artifact(artifact_name, [self])  # type: ignore[attr-defined]


class FunctionMixin(AllMixin):
    """
    Mixin used to reference the `Project` class from the `Function` class.
    """

    def get_artifact(self, artifact_name: str) -> bytes | str:
        """
        Fetch the artifacts from the `Function`.
        """
        return self._project._get_artifact(artifact_name, [self])  # type: ignore[attr-defined]


class TypeDefinitionMixin(AllMixin):
    """
    Mixin used to reference the `Project` class from the `TypeDefinition` class.
    """

    def get_artifact(self, artifact_name: str) -> bytes | str:
        """
        Fetch the artifacts from the `TypeDefinition`.
        """
        return self._project._get_artifact(artifact_name, [self])  # type: ignore[attr-defined]
