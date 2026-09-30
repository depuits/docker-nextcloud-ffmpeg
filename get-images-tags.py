import requests
import urllib.parse
import re
import dateutil.parser
from datetime import datetime
from datetime import timezone
import json

source_registry = "library"
source_repository = "nextcloud"

target_registry = "depuits"
target_repository = "nextcloud-ffmpeg"

# Tags to build
tag_regex = re.compile(r"^(?:\d+(?:\.\d+)?(?:\.\d+)?|latest|stable)$")
only_newer_than = datetime(2025, 1, 1, tzinfo=timezone.utc)


def get_tags(registry="library", repository=None, search=None):
    if not repository:
        raise Exception("repository needs to be set")

    nextUrl = f"https://registry.hub.docker.com/v2/namespaces/{registry}/repositories/{repository}/tags?page=1&page_size=1000"
    if search:
        nextUrl += f"&{urllib.parse.urlencode({'name': search})}"
    images = []
    while nextUrl:
        try:
            res = requests.get(nextUrl)
            data = res.json()
            nextUrl = data["next"]
            images.extend(data["results"])
        except Exception:
            nextUrl = None
    return images


source_tags = get_tags(source_registry, source_repository)
target_tags = get_tags(target_registry, target_repository)


tags_to_build = []
for source_tag in source_tags:
    if not tag_regex.match(source_tag["name"]):
        continue

    last_pushed_source = dateutil.parser.parse(source_tag["tag_last_pushed"])
    if last_pushed_source.tzinfo is None:
        last_pushed_source = last_pushed_source.replace(tzinfo=timezone.utc)

    if last_pushed_source < only_newer_than:
        continue

    found = [
        target_tag
        for target_tag in target_tags
        if target_tag.get("name") == source_tag["name"]
    ]

    if len(found) == 0:
        tags_to_build.append(source_tag)
        continue

    last_pushed_target = dateutil.parser.parse(found[0]["tag_last_pushed"])
    if last_pushed_target.tzinfo is None:
        last_pushed_target = last_pushed_target.replace(tzinfo=timezone.utc)

    if last_pushed_target < last_pushed_source:
        tags_to_build.append(source_tag)
        continue

image_hash_to_tags = {}

for tag in tags_to_build:
    digest = tag["digest"]
    name = tag["name"]
    if digest not in image_hash_to_tags:
        image_hash_to_tags[digest] = []
    image_hash_to_tags[digest].append(f"{target_registry}/{target_repository}:{name}")


print(
    json.dumps(
        [
            {"digest": digest, "tags": names}
            for digest, names in image_hash_to_tags.items()
        ]
    )
)
