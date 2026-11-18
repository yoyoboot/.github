#!/usr/bin/env bash
set -euo pipefail

manifest="$(dirname -- "${BASH_SOURCE[0]}")/images.json"
[[ "$IMAGE_REGISTRY" =~ ^[a-z0-9.-]+(:[0-9]+)?$ ]] || { echo 'Invalid RIDER_IMAGE_REGISTRY.' >&2; exit 1; }
[[ "$IMAGE_REPOSITORY" =~ ^[a-z0-9._-]+(/[a-z0-9._-]+)+$ ]] || { echo 'Invalid RIDER_IMAGE_REPOSITORY.' >&2; exit 1; }
repository="${IMAGE_REGISTRY}/${IMAGE_REPOSITORY}"
build_id="${SOURCE_SHA}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
image_list=$(jq -ber 'keys_unsorted[]' "$manifest")
mapfile -t images <<< "$image_list"

updated=()
trap 'echo "updated_tags=${updated[*]}" >> "$GITHUB_OUTPUT"' EXIT
for image in "${images[@]}"; do
    docker image inspect "rider-local/${image}:${SOURCE_SHA}" >/dev/null
done

for image in "${images[@]}"; do
    version_tag="$repository:${image}_${build_id}"
    docker tag "rider-local/${image}:${SOURCE_SHA}" "$version_tag"
    docker push "$version_tag"
    printf -- '- %s: trace tag pushed (`%s`)\n' "$image" "$version_tag" >> "$GITHUB_STEP_SUMMARY"
done

for image in "${images[@]}"; do
    version_tag="$repository:${image}_${build_id}"
    fixed_tag="$repository:${image}_main"
    docker tag "$version_tag" "$fixed_tag"
    docker push "$fixed_tag"
    updated+=("${image}_main")
    printf -- '- %s: fixed tag updated (`%s`)\n' "$image" "$fixed_tag" >> "$GITHUB_STEP_SUMMARY"
done
