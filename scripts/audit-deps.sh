#!/usr/bin/env sh
set -eu
repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
docker build --target audit --output=type=cacheonly "$repo"
