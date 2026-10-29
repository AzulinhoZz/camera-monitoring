"""Offline Linux backup bundles, streamed AES-256-GCM; no DSN, network or key logging."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile

from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

MAGIC=b'CAMERA-BACKUP-1\0'
MAX_BYTES=100*1024**3


def private_directory(path):
    path=Path(path)
    if not path.is_absolute() or path.is_symlink():raise ValueError('private absolute directory required')
    info=path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('directory must be private and owned')
    return path


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def create_key(path):
    path=Path(path);private_directory(path.parent)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(os.urandom(32));stream.flush();os.fsync(stream.fileno())
    sync_directory(path.parent)


def read_key(path):
    path=Path(path);private_directory(path.parent)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('private owned regular key required')
        data=stream.read(33)
    if len(data)!=32:raise ValueError('AES-256 key length')
    return data


def encrypt(source,key_file,target):
    source=Path(source);target=Path(target);key_file=Path(key_file)
    private_directory(source);private_directory(target.parent)
    if source.resolve() in key_file.resolve().parents or source.resolve() in target.resolve().parents:
        raise ValueError('key and archive must be outside source')
    files=[];total=0
    for path in sorted(source.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):raise ValueError('regular files/directories only')
        if path.is_file():files.append(path);total+=path.stat().st_size
    if not files or len(files)>100000 or total>MAX_BYTES:raise ValueError('backup size/file budget')
    nonce=os.urandom(12);header=MAGIC+nonce
    cipher=Cipher(algorithms.AES(read_key(key_file)),modes.GCM(nonce)).encryptor();cipher.authenticate_additional_data(header)
    class Sink:
        def write(self,data):stream.write(cipher.update(data));return len(data)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as stream:
            temporary=Path(stream.name);stream.write(header)
            with tarfile.open(fileobj=Sink(),mode='w|',format=tarfile.PAX_FORMAT) as bundle:
                for path in files:bundle.add(path,arcname=path.relative_to(source).as_posix(),recursive=False)
            stream.write(cipher.finalize());stream.write(cipher.tag);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,target)  # Never replace any existing file/symlink.
    finally:
        if temporary:temporary.unlink(missing_ok=True)
        sync_directory(target.parent)
    return {'files':len(files),'plain_bytes':total,'format':'AES-256-GCM streamed tar v1'}


def publish_directory(source,target):
    # Linux atomic no-replace avoids overwriting even an empty destination that
    # appears between the initial check and publication.
    library=ctypes.CDLL(None,use_errno=True)
    rename=library.renameat2
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(source),-100,os.fsencode(target),1):raise OSError(ctypes.get_errno(),'restore publication refused')
    sync_directory(Path(target).parent)


def restore(archive,key_file,destination):
    archive=Path(archive);destination=Path(destination);private_directory(destination.parent)
    if destination.exists() or destination.is_symlink():raise ValueError('restore destination must not exist')
    size=archive.stat().st_size
    if not len(MAGIC)+28<size<=MAX_BYTES+512*1024*1024:raise ValueError('backup size')
    with tempfile.TemporaryDirectory(prefix='.camera-restore-',dir=destination.parent) as temporary:
        root=Path(temporary);plain=root/'authenticated.tar'
        with archive.open('rb') as source,os.fdopen(os.open(plain,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as output:
            header=source.read(len(MAGIC)+12)
            if header[:len(MAGIC)]!=MAGIC:raise ValueError('backup format')
            source.seek(-16,2);tag=source.read(16);source.seek(len(header))
            cipher=Cipher(algorithms.AES(read_key(key_file)),modes.GCM(header[-12:],tag)).decryptor();cipher.authenticate_additional_data(header)
            remaining=size-len(header)-16
            while remaining:
                data=source.read(min(1024*1024,remaining))
                if not data:raise ValueError('truncated backup')
                output.write(cipher.update(data));remaining-=len(data)
            output.write(cipher.finalize())
        # Authentication completed before any tar parsing or destination exists.
        payload=root/'payload';payload.mkdir(mode=0o700);count=total=0
        with tarfile.open(plain,mode='r|') as bundle:
            for member in bundle:
                path=Path(member.name)
                if not member.isfile() or path.is_absolute() or '..' in path.parts or not path.parts:raise ValueError('unsafe backup entry')
                count+=1;total+=member.size
                if count>100000 or total>MAX_BYTES:raise ValueError('restore budget')
                target=payload/path;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with target.open('xb') as output:
                    shutil.copyfileobj(bundle.extractfile(member),output,1024*1024);output.flush();os.fsync(output.fileno())
                target.chmod(0o600)
        for directory in sorted((path for path in payload.rglob('*') if path.is_dir()),key=lambda path:len(path.parts),reverse=True):sync_directory(directory)
        sync_directory(payload)
        publish_directory(payload,destination)
    return {'files':count,'plain_bytes':total,'authenticated':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['generate-key','encrypt','restore']);p.add_argument('--key-file',required=True);p.add_argument('--source');p.add_argument('--archive');p.add_argument('--destination');a=p.parse_args()
    try:
        if a.action=='generate-key':create_key(a.key_file);result={'key_created':True,'key_printed':False}
        elif a.action=='encrypt':result=encrypt(a.source,a.key_file,a.archive)
        else:result=restore(a.archive,a.key_file,a.destination)
    except Exception as error:
        print(json.dumps({'result':'FAILED','reason':type(error).__name__,'limits':'No credential or payload details logged; destination is never overwritten.'}));return 1
    print(json.dumps({'result':'PASS',**result}));return 0

if __name__=='__main__':raise SystemExit(main())
