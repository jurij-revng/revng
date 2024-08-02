#
# This file is distributed under the MIT License. See LICENSE.md for details.
#

import os
import socket
import subprocess
from signal import SIGINT
from time import sleep

import requests

from revng.scripting.projects import DaemonProject


class LocalDaemonProject(DaemonProject):
    """
    This class extends the DaemonProject. When initialized it starts the revng daemon
    server and setups the DaemonProject client used to connect to the server.
    """

    def __init__(self, resume_dir: str | None = None, revng_executable: str | None = None):
        super().__init__()
        self.port: int = self._get_port()
        self.daemon_process: subprocess.Popen | None = None
        self.resume_dir = self._set_resume_dir(resume_dir)
        self.revng_executable = self._set_revng_executable(revng_executable)
        self.start_daemon()
        self.setup_client(f"http://127.0.0.1:{self.port}")

    def __del__(self):
        self.stop_daemon()

    def start_daemon(self, connection_retries: int = 10):
        """
        Start the `revng` daemon and wait for it to be ready.
        """
        env = os.environ
        env["REVNG_DATA_DIR"] = self.resume_dir

        cli_args = [self.revng_executable, "daemon", "-b", f"tcp:127.0.0.1:{self.port}"]
        self.daemon_process = subprocess.Popen(
            cli_args, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=env
        )

        failed_retries = 0
        while failed_retries <= connection_retries:
            if self._is_server_running():
                return
            failed_retries += 1
            sleep(1)
        raise RuntimeError(f"Couldn't connect to daemon server at http://127.0.0.1:{self.port}")

    def stop_daemon(self) -> int:
        """
        Stop the daemon server.
        """
        if self.daemon_process:
            self.daemon_process.send_signal(SIGINT)
            status_code = self.daemon_process.wait(30.0)
            self.daemon_process = None
            return status_code
        return 0

    def _is_server_running(self) -> bool:
        try:
            requests.get(f"http://127.0.0.1:{self.port}/status", timeout=5)
            return True
        except requests.exceptions.ConnectionError:
            return False

    def _get_port(self) -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        free_socket = s.getsockname()[1]
        s.close()
        return int(free_socket)


class DaemonProfile:
    """
    This class is used to group DaemonProjects that share the same
    executable.
    """

    def __init__(self, revng_executable: str | None = None):
        self.revng_executable = revng_executable

    def get_project(self, resume_dir: str | None = None) -> LocalDaemonProject:
        """
        Start a new revng daemon process, create the client that connect to the
        daemon and return it. Store the state in `resume_dir` for subsequent executions.
        """
        return LocalDaemonProject(resume_dir, self.revng_executable)
