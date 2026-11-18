#!/usr/bin/env bash
set -euo pipefail

manifest="$(dirname -- "${BASH_SOURCE[0]}")/images.json"
selection="${1:?Pass an image name or all.}"
test "$(git -C source rev-parse HEAD)" = "$SOURCE_SHA"
rows=$(jq -ber --arg image "$selection" '
    if $image == "all" then to_entries[]
    else {key: $image, value: (.[$image] // error("Unknown Rider image: " + $image))}
    end | [.key, .value] | @tsv
' "$manifest")

build_id="${SOURCE_SHA}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
failed=0
while IFS=$'\t' read -r image dockerfile; do
    local_tag="rider-local/${image}:${SOURCE_SHA}"
    echo "::group::Build $image"
    if docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load \
        --file "source/$dockerfile" --tag "$local_tag" \
        --build-arg "SOURCE_REVISION=$SOURCE_SHA" --build-arg "RIDER_BUILD_ID=$build_id" source; then
        printf -- '- %s: built (`%s`)\n' "$image" "$local_tag" >> "$GITHUB_STEP_SUMMARY"
    else
        printf -- '- %s: build failed\n' "$image" >> "$GITHUB_STEP_SUMMARY"
        echo "::error::Image build failed: $image"
        failed=1
    fi
    echo '::endgroup::'
done <<< "$rows"

if (( failed )); then
    exit 1
fi
echo 'images_built=true' >> "$GITHUB_OUTPUT"
