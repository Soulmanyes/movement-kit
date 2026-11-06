#!/bin/sh
# SPDX-License-Identifier: CC0-1.0
# Prints the release notes written as the annotated tag's message (git tag -a <tag> -F notes.md),
# for gh release create --notes-file. Prints nothing for a lightweight tag or one whose message is
# only its own name; the release then falls back to GitHub's generated notes. The hub shows these
# notes in its "What's new" popup, so the release must carry them from the moment it exists.
tag=$1
# checkout may leave the tag as a plain ref to the commit: fetch the tag object itself
git fetch -q --force origin "refs/tags/$tag:refs/tags/$tag" || exit 0
[ "$(git cat-file -t "refs/tags/$tag")" = tag ] || exit 0
msg=$(git for-each-ref --format='%(contents)' "refs/tags/$tag" | sed '/^-----BEGIN PGP SIGNATURE-----/,$d')
[ "$(printf %s "$msg" | tr -d '[:space:]')" = "$tag" ] && exit 0
printf '%s\n' "$msg"
