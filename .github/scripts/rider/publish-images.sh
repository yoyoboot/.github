#!/usr/bin/env bash
set -euo pipefail

manifest="$(dirname -- "${BASH_SOURCE[0]}")/images.json"
references="${1:?Pass the directory of version tags.}"
repository="${IMAGE_REGISTRY}/${IMAGE_REPOSITORY}"
image_list=$(jq -ber 'keys_unsorted[]' "$manifest")
mapfile -t images <<< "$image_list"

updated=()
trap 'echo "updated_tags=${updated[*]}" >> "$GITHUB_OUTPUT"' EXIT
declare -A versions
for image in "${images[@]}"; do
    version=$(<"$references/$image.txt")
    if [[ ! "$version" =~ ^${image}_${SOURCE_SHA}-${GITHUB_RUN_ID}-[1-9][0-9]*$ ]]; then
        echo "::error::Invalid version reference for $image"
        exit 1
    fi
    versions[$image]="$repository:$version"
    docker buildx imagetools inspect "${versions[$image]}" >/dev/null
done

for image in "${images[@]}"; do
    fixed_tag="$repository:${image}_main"
    if ! docker buildx imagetools create --prefer-index=false --tag "$fixed_tag" "${versions[$image]}"; then
        printf 'failed_tag=%s_main\n' "$image" >> "$GITHUB_OUTPUT"
        exit 1
    fi
    updated+=("${image}_main")
    printf -- '- %s: fixed tag updated (`%s`)\n' "$image" "$fixed_tag" >> "$GITHUB_STEP_SUMMARY"
done
