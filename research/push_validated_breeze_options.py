"""Publish only verified observed option artifacts, including explicit sparse coverage."""
import argparse
import sys
import urllib.parse

import fetch_breeze_options as options
from push_validated_breeze_data import git


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--push',action='store_true')
    args=p.parse_args()
    files=options.validated_files(options.ROOT)
    print(f'Validated {sum(x.startswith("data/breeze/metadata/options/") for x in files)} observed option contract-days ({len(files)} artifact paths). Sparse coverage remains flagged.')
    if not args.push:
        for name in files:
            print(name)
        return
    branch=git('symbolic-ref','--quiet','--short','HEAD')
    if branch in ('main','master') or git('diff','--cached','--name-only'):
        raise options.base.FetchError('Use a work branch with no other staged changes; existing work preserved.')
    remote=git('remote','get-url','origin')
    parsed=urllib.parse.urlparse(remote)
    expected='sadamanjaneyulu/algo-8-reverse-engineer'
    if not ((parsed.hostname=='github.com' and parsed.path.strip('/').removesuffix('.git').lower()==expected) or
            remote.lower().removesuffix('.git')==f'git@github.com:{expected}'):
        raise options.base.FetchError('Unexpected origin; no data staged or pushed.')
    for offset in range(0,len(files),100):
        git('add','--',*files[offset:offset+100])
    if git('diff','--cached','--name-only'):
        git('commit','-m','Add observed Breeze option minute data with explicit coverage')
    git('push','-u','origin','HEAD')
    print(f'Pushed observed options data on branch {branch}.')


if __name__=='__main__':
    try:
        main()
    except (options.base.FetchError,ValueError,KeyError,TypeError,OSError) as exc:
        print(str(exc) if isinstance(exc,options.base.FetchError) else f'Option publication stopped: {type(exc).__name__}; details suppressed.',file=sys.stderr)
        sys.exit(1)
