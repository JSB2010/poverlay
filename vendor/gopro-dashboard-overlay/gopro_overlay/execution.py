from __future__ import annotations

import subprocess

from gopro_overlay.log import log


class InProcessExecution:

    def __init__(self, redirect=None, popen=subprocess.Popen):
        self.redirect = redirect
        self.popen = popen

    def execute(self, cmd):
        process = None
        had_error = False
        try:
            log(f"Executing {cmd}")
            if self.redirect:
                with open(self.redirect, "w") as std:
                    process = self.popen(cmd, stdin=subprocess.PIPE, stdout=std, stderr=std)
            else:
                process = self.popen(cmd, stdin=subprocess.PIPE, stdout=None, stderr=None)
        except FileNotFoundError:
            raise IOError(f"Unable to execute the process - is '{cmd[0]}' installed") from None

        try:
            yield process.stdin
        except BrokenPipeError:
            had_error = True
            if self.redirect:
                log("FFMPEG Output:")
                with open(self.redirect) as f:
                    log("".join(f.readlines()))
            raise IOError(f"Process {cmd[0]} failed") from None
        except Exception:
            had_error = True
            try:
                process.terminate()
            except Exception:
                pass
            raise
        finally:
            if process is not None:
                if not process.stdin.closed:
                    if not had_error:
                        process.stdin.flush()
                    process.stdin.close()
                # really long wait as FFMPEG processes all the mpeg input file - not sure how to prevent this atm
                log("Waiting for ffmpeg to complete...")
                returncode = process.wait(5 * 60)
                log(f"FFMPEG Exited with status code: {returncode}")
