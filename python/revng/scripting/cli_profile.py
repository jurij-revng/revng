#
# This file is distributed under the MIT License. See LICENSE.md for details.
#

from revng.scripting.projects import CLIProject


class CLIProfile:
    """
    This class is used to group CLIProjects that share the same
    executable.
    """

    def __init__(self, revng_executable: str | None = None):
        self.revng_executable = revng_executable

    def get_project(self, resume_dir: str | None = None) -> CLIProject:
        """
        Create the a new CLIProject and store the state in `resume_dir`
        for subsequent executions.
        """
        return CLIProject(resume_dir, self.revng_executable)
