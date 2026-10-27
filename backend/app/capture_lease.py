"""Host/volume-local camera ownership, shared by legacy and vision processes.

The directory must be mounted into all capture services on this host. This is
not a distributed lease across hosts; deploy one capture host per camera.
"""
import fcntl
import hashlib
import os
import stat
from pathlib import Path


class CaptureLease:
    def __init__(self, camera_id):
        self.key = hashlib.sha256(str(camera_id).encode()).hexdigest()
        self._fd = None

    def acquire(self):
        directory = Path(os.getenv("CAMERA_LEASE_DIRECTORY", "/tmp/camera-monitoring-capture-leases"))
        directory.mkdir(parents=True, exist_ok=True)
        fd = os.open(directory / (self.key + ".lock"), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o666)
        try:
            # The dedicated volume is shared only by trusted capture containers.
            # Root legacy API and unprivileged decoder supervisor can both open it.
            if stat.S_IMODE(os.fstat(fd).st_mode) != 0o666:
                os.fchmod(fd, 0o666)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise RuntimeError("Camera capture is already owned or unavailable") from None
        self._fd = fd
        return self

    def release(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        # Never unlink a lock file: other processes may still have its inode open.
