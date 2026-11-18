#!/usr/bin/env bash
set -euo pipefail

manifest="$(dirname -- "${BASH_SOURCE[0]}")/images.json"
image="${1:?Pass an image name.}"
test "$(git -C source rev-parse HEAD)" = "$SOURCE_SHA"
dockerfile=$(jq -ber --arg image "$image" '.[$image] // error("Unknown Rider image: " + $image)' "$manifest")

build_id="${SOURCE_SHA}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
local_tag="rider-local/${image}:${SOURCE_SHA}"
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load \
    --file "source/$dockerfile" --tag "$local_tag" \
    --build-arg "SOURCE_REVISION=$SOURCE_SHA" --build-arg "RIDER_BUILD_ID=$build_id" source
printf -- '- %s: built (`%s`)\n' "$image" "$local_tag" >> "$GITHUB_STEP_SUMMARY"
printf 'local_tag=%s\nversion_tag=%s\n' "$local_tag" "${image}_${build_id}" >> "$GITHUB_OUTPUT"
