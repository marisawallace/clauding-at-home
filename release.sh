#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 <version>   e.g. $0 0.2.0" >&2
    exit 2
fi

version="$1"
tag="v${version#v}"

cd "$(dirname "$0")"

branch=$(git symbolic-ref --short HEAD)
if [[ "$branch" != "main" ]]; then
    echo "error: must be on main (currently on $branch)" >&2
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "error: working tree has uncommitted changes" >&2
    exit 1
fi

git fetch origin main
local_sha=$(git rev-parse main)
remote_sha=$(git rev-parse origin/main)
if [[ "$local_sha" != "$remote_sha" ]]; then
    echo "error: local main ($local_sha) does not match origin/main ($remote_sha)" >&2
    exit 1
fi

if git rev-parse "$tag" >/dev/null 2>&1; then
    echo "error: tag $tag already exists" >&2
    exit 1
fi

git tag -a "$tag" -m "$tag"
git push origin "$tag"

gh release create "$tag" --title "$tag"
