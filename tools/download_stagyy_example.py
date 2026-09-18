#!/usr/bin/env python3
"""Download the CC0 Langemeyer et al. (2021) 3-D StagYY initial-condition files."""
import argparse
import hashlib
import http.cookiejar
from pathlib import Path
import shutil
import urllib.request

PREVIEW = 'https://borealisdata.ca/privateurl.xhtml?token=384a40c4-209a-4e00-8cd1-2bb8d8732080'
STEM = '3Dsph_f0.547_Ra2e8_Ea3.2e5_H30_J30_Pd2e7'
FILES = [
    (126611,STEM+'_t00035','ba13738f9a39319689f4d790247dd628'),
    (126608,STEM+'_eta00035','bc782e3588b2fd67292f5999cfd56f77'),
    (126610,STEM+'_vp00035','1bd54f6c3a4a4b3c17a440bf95be14c2'),
    (137812,'par_Ra2e8','2edef27501fdcd9e9acdf5598e429055'),
]


def md5(path):
    digest = hashlib.md5()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path.home()/'Downloads/stagyy-langemeyer2021')
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True,exist_ok=True)
    # The paper publishes this preview link. Visiting it establishes the
    # public preview session needed by the file API; no personal credentials.
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    initialized = False
    for fid,name,checksum in FILES:
        target = args.out/name
        if target.is_file() and md5(target) == checksum:
            print(name+': MD5 OK (already downloaded)',flush=True)
            continue
        if not initialized:
            print('Opening the public dataset preview linked by the paper...',flush=True)
            with opener.open(PREVIEW,timeout=120) as response:
                response.read()
            initialized = True
        temporary = target.with_name(target.name+'.part')
        print('Downloading '+name,flush=True)
        try:
            with opener.open(f'https://borealisdata.ca/api/access/datafile/{fid}',timeout=120) as src, temporary.open('wb') as dst:
                shutil.copyfileobj(src,dst,length=1024*1024)
            if md5(temporary) != checksum:
                raise ValueError(f'{name}: checksum mismatch; file was not installed. Dataset: {PREVIEW}')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print(name+': MD5 OK',flush=True)
    print(f'Download complete. These are raw binary files; no unzip is needed.\nTemperature input: {args.out/(STEM+"_t00035")}')


if __name__ == '__main__':
    main()
