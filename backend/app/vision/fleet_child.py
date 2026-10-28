"""Linux owned fleet child; refuse orphan startup before importing native models."""
import ctypes
import os
import signal
import sys

if __name__=='__main__':
    expected=int(sys.argv[1])
    if ctypes.CDLL(None,use_errno=True).prctl(1,signal.SIGKILL)!=0 or os.getppid()!=expected:
        raise SystemExit(2)
    os.sched_setaffinity(0,{int(os.environ.pop('VISION_FLEET_CPU'))})
    from .__main__ import main
    raise SystemExit(main(sys.argv[2:]))
