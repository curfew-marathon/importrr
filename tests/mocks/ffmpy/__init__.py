class FFmpeg:
    def __init__(
        self, inputs=None, outputs=None, global_options=None, executable="ffmpeg"
    ):
        self.inputs = inputs
        self.outputs = outputs
        self.global_options = global_options
        self.executable = executable
        self.cmd = "ffmpeg mock command"

    def run(self, input_data=None, stdout=None, stderr=None):
        pass


class FFRuntimeError(Exception):
    def __init__(self, cmd, exit_code, stdout, stderr):
        self.cmd = cmd
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Command '{cmd}' terminated with exit code {exit_code}")


class FFExecutableNotFoundError(Exception):
    pass
